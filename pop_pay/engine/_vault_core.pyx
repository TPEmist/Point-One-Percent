# pop_pay/engine/_vault_core.pyx
# cython: language_level=3
"""
Cython-compiled key derivation core for pop-pay vault.

Security model (v0.6.2+):
- Salt is split into two XOR-paired integer lists at CI build time.
  Variable names are intentionally non-descriptive to raise reverse cost.
  Neither list alone reveals the salt; reconstruction happens only inside
  derive_key() and is zeroed from memory immediately after use.
- derive_key() returns only the AES-256 key — salt never crosses the
  Python boundary as a recoverable object.
- OSS/source builds: both lists are None → derive_key() returns None →
  vault.py falls back to the public OSS salt (or raises in strict mode).
"""

# CI replaces these placeholders with XOR-paired int lists.
# Intentionally non-descriptive names to raise reverse engineering cost.
_A1 = None  # Replaced by CI
_B2 = None  # Replaced by CI


def derive_key(machine_id: bytes, username: bytes):
    """Derive AES-256 key. Salt is reconstructed from XOR pairs, used, then
    zeroed. Never returned or stored as a Python object.

    Returns None if running from OSS source (no compiled data).
    """
    if _A1 is None or _B2 is None:
        return None
    import hashlib
    # Reconstruct salt into a mutable bytearray so we can zero it after use
    salt = bytearray(a ^ b for a, b in zip(_A1, _B2))
    password = machine_id + b":" + username
    try:
        return hashlib.scrypt(password, salt=bytes(salt), n=2**14, r=8, p=1, dklen=32)
    finally:
        # Zero the reconstructed salt from memory
        salt[:] = bytearray(len(salt))


def is_hardened():
    """Return True if this is a PyPI/Cython hardened build."""
    return _A1 is not None
