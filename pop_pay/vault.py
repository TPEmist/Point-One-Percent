"""
pop-pay credential vault — AES-256-GCM encrypted credential storage.

Security model:
- Credentials are encrypted at rest using AES-256-GCM with a machine-derived key.
- The key is derived from a stable machine identifier using scrypt.
- Plaintext credentials never touch disk after init-vault completes.
- OSS version uses a public salt (documented limitation: protects against
  file-read-only agents, not against agents with shell execution).
  PyPI/Cython version will use a compiled-in secret salt.
"""
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

# AES-256-GCM via cryptography library (pip install cryptography)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None

VAULT_DIR = Path.home() / ".config" / "pop-pay"
VAULT_PATH = VAULT_DIR / "vault.enc"

# OSS public salt — intentionally documented as a security limitation.
# PyPI/Cython builds will replace this with a compiled-in secret.
_OSS_SALT = b"pop-pay-oss-v1-public-salt-2026"

OSS_WARNING = (
    "\n⚠️  pop-pay SECURITY NOTICE: Running from source build (OSS mode).\n"
    "   Vault encryption uses a public salt. An agent with shell execution\n"
    "   tools could derive the vault key from public information.\n"
    "   For stronger security: install via PyPI (`pip install pop-pay`)\n"
    "   or use `pop-pay init-vault --passphrase` (coming in v0.6.x).\n"
)


def _get_machine_id() -> bytes:
    """Return a stable machine identifier. Falls back through platform-specific sources."""
    # Linux: /etc/machine-id (stable across reboots, not affected by network changes)
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        mid = machine_id_path.read_text().strip()
        if mid:
            return mid.encode()

    # macOS: IOPlatformUUID via ioreg
    if sys.platform == "darwin":
        import subprocess
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    uid = line.split('"')[-2]
                    return uid.encode()
        except Exception:
            pass

    # Windows: MachineGuid from registry
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return guid.encode()
        except Exception:
            pass

    # Fallback: generate a random ID and store it alongside the vault
    fallback_path = VAULT_DIR / ".machine_id"
    if fallback_path.exists():
        return fallback_path.read_bytes()
    import secrets
    fallback_id = secrets.token_bytes(32)
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(fallback_id)
    fallback_path.chmod(0o600)
    return fallback_id


def _get_username() -> bytes:
    """Return a stable username, avoiding os.getlogin() which fails in non-login shells."""
    import pwd
    try:
        return pwd.getpwuid(os.getuid()).pw_name.encode()
    except Exception:
        pass
    return os.environ.get("USER", os.environ.get("USERNAME", "unknown")).encode()


def _derive_key(salt: bytes = None) -> bytes:
    """Derive AES-256 key from machine identity using scrypt."""
    import hashlib
    if salt is None:
        salt = _OSS_SALT
    machine_id = _get_machine_id()
    try:
        username = _get_username()
    except Exception:
        username = b"unknown"
    password = machine_id + b":" + username
    # n=2**14 (16MB) — well within OpenSSL default maxmem (32MB).
    # Higher n is bounded by machine_id:username entropy (~40-50 bits), not KDF cost.
    return hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1, dklen=32)


def encrypt_credentials(creds: dict, salt: bytes = None) -> bytes:
    """Encrypt credentials dict to bytes (nonce + ciphertext + GCM tag)."""
    if AESGCM is None:
        raise ImportError("cryptography package required: pip install 'pop-pay[vault]'")
    import os as _os
    key = _derive_key(salt)
    nonce = _os.urandom(12)  # 96-bit random nonce
    aesgcm = AESGCM(key)
    plaintext = json.dumps(creds).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # nonce prepended; GCM tag is appended by library


def decrypt_credentials(blob: bytes, salt: bytes = None) -> dict:
    """Decrypt vault blob to credentials dict. Raises ValueError on wrong key/corruption."""
    if AESGCM is None:
        raise ImportError("cryptography package required: pip install 'pop-pay[vault]'")
    if len(blob) < 28:  # 12 nonce + at least 16 GCM tag
        raise ValueError("vault.enc is corrupted or too small")
    key = _derive_key(salt)
    nonce, ciphertext = blob[:12], blob[12:]
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError(
            "Failed to decrypt vault — wrong key (machine changed?) or corrupted vault.\n"
            "Re-run: pop-pay init-vault"
        )
    return json.loads(plaintext)


def vault_exists() -> bool:
    return VAULT_PATH.exists()


def load_vault() -> dict:
    """Load and decrypt vault. Returns dict with card credentials."""
    blob = VAULT_PATH.read_bytes()
    return decrypt_credentials(blob)


def save_vault(creds: dict):
    """Encrypt and atomically write credentials to vault.enc."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    blob = encrypt_credentials(creds)
    # Atomic write: tmp → fsync → rename
    tmp_path = VAULT_PATH.with_suffix(".enc.tmp")
    tmp_path.write_bytes(blob)
    tmp_path.chmod(0o600)
    with tmp_path.open("rb") as _f:
        os.fsync(_f.fileno())
    tmp_path.rename(VAULT_PATH)
    VAULT_PATH.chmod(0o600)
    VAULT_DIR.chmod(0o700)
    # Verify the vault is readable before wiping anything
    try:
        decrypt_credentials(VAULT_PATH.read_bytes())
    except ValueError as e:
        raise RuntimeError(f"Vault write verification failed: {e}")


def secure_wipe_env(env_path: Path):
    """Overwrite .env with zeros then delete. Note: SSD wear-leveling may retain data."""
    if not env_path.exists():
        return
    size = env_path.stat().st_size
    with open(env_path, "r+b") as f:
        f.write(b"\x00" * size)
        f.flush()
        os.fsync(f.fileno())
    env_path.unlink()
