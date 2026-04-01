"""
Hatchling build hook for compiling Cython extensions.

The salt is injected as two XOR-paired integer lists (_SALT_XOR, _SALT_MASK)
so no plaintext salt byte string appears in the compiled .so binary.
`strings` scanning cannot reconstruct the salt from either list alone.

If POP_VAULT_COMPILED_SALT is not set, both lists remain None and vault.py
falls back to the public OSS salt at runtime.
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        compiled_salt = os.environ.get("POP_VAULT_COMPILED_SALT", "").encode()
        pyx_path = Path("pop_pay/engine/_vault_core.pyx")
        if not pyx_path.exists():
            return

        # Tell hatchling this wheel contains a compiled extension (platform-specific)
        build_data['pure_python'] = False
        build_data['infer_tag'] = True

        if compiled_salt:
            # Split salt into XOR pair — neither part alone reveals the salt.
            # Stored as int lists so no contiguous byte string appears in binary.
            mask = secrets.token_bytes(len(compiled_salt))
            xor_data = bytes(a ^ b for a, b in zip(compiled_salt, mask))
            xor_list  = list(xor_data)   # salt XOR mask
            mask_list = list(mask)        # random mask

            source = pyx_path.read_text()
            patched = source.replace(
                "_SALT_XOR  = None  # Replaced by CI",
                f"_SALT_XOR  = {xor_list}  # CI-injected"
            ).replace(
                "_SALT_MASK = None  # Replaced by CI",
                f"_SALT_MASK = {mask_list}  # CI-injected"
            )
            pyx_path.write_text(patched)

        # Compile the Cython extension
        try:
            result = subprocess.run(
                [sys.executable, "setup_cython.py", "build_ext", "--inplace"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print("Cython compilation stdout:")
                print(result.stdout[-3000:] if result.stdout else "(none)")
                print("Cython compilation stderr:")
                print(result.stderr[-3000:] if result.stderr else "(none)")
                raise RuntimeError(f"setup_cython.py exited with code {result.returncode}")
            print("Cython compilation succeeded.")
            print(result.stdout[-1000:] if result.stdout else "")
        except Exception as e:
            print(f"ERROR: Cython compilation failed: {e}. Falling back to pure Python.")
        finally:
            if compiled_salt:
                # Restore original .pyx (don't commit secrets)
                pyx_path.write_text(source)
