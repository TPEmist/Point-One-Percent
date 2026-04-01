# pop_pay/engine/_vault_core_fallback.py
"""Pure-Python fallback when Cython .so is not compiled."""

_SALT_XOR  = None
_SALT_MASK = None

def derive_key(machine_id: bytes, username: bytes):
    """OSS fallback: no compiled salt, returns None to trigger public salt path."""
    return None

def is_hardened():
    return False
