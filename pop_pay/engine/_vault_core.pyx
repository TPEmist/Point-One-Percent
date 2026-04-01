# pop_pay/engine/_vault_core.pyx
# cython: language_level=3
"""
Cython-compiled key derivation core for pop-pay vault.

Security model (v0.6.1+):
- Salt is never stored as a plaintext byte string in the binary.
- CI injects the salt as two XOR-paired integer lists (_SALT_XOR, _SALT_MASK).
  Neither list alone reveals the salt; reconstruction happens only inside
  derive_key() at runtime. This defeats `strings` static scanning.
- derive_key() returns only the derived AES-256 key — salt never crosses the
  Python boundary as a recoverable object.
- OSS/source builds: both lists are None → derive_key() returns None →
  vault.py falls back to the public OSS salt.
"""

# CI replaces these two None placeholders with XOR-paired int lists.
# _SALT_XOR  = list of ints = salt XOR mask
# _SALT_MASK = list of ints = random mask (same length as salt)
# Salt is reconstructed inside derive_key() only — never stored as bytes.
_SALT_XOR  = None  # Replaced by CI
_SALT_MASK = None  # Replaced by CI


def derive_key(machine_id: bytes, username: bytes):
    """Derive AES-256 key. Salt is reconstructed from XOR pairs inside this
    function and immediately consumed — never returned or stored.

    Returns None if running from OSS source (no compiled salt), signalling
    vault.py to use the public fallback salt instead.
    """
    if _SALT_XOR is None or _SALT_MASK is None:
        return None
    import hashlib
    # Reconstruct salt from XOR pair — no plaintext salt in binary
    salt = bytes(a ^ b for a, b in zip(_SALT_XOR, _SALT_MASK))
    password = machine_id + b":" + username
    return hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1, dklen=32)


def is_hardened():
    """Return True if this is a PyPI/Cython hardened build."""
    return _SALT_XOR is not None
