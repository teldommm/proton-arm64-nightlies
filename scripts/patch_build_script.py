#!/usr/bin/env python3
"""
Patches build-step-arm64ec.sh to use forgiving git apply options
so patches that don't apply cleanly to bleeding-edge are skipped
instead of aborting the build.
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'build-scripts/build-step-arm64ec.sh'

with open(path) as f:
    txt = f.read()

txt = txt.replace(
    'git apply ./android/patches/$patch',
    # Try applying; if it fails, check if it's already applied (reverse check).
    # If already applied, skip silently. Otherwise log a warning but continue.
    'git apply --ignore-whitespace -C1 ./android/patches/$patch 2>/dev/null'
    ' || git apply --ignore-whitespace -C1 -R --check ./android/patches/$patch 2>/dev/null'
    ' && echo "ALREADY APPLIED (skipped): $patch"'
    ' || echo "WARNING: $patch did not apply and is not already present"'
)

with open(path, 'w') as f:
    f.write(txt)

print(f"Patched {path}")
