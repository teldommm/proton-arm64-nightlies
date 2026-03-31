#!/usr/bin/env python3
"""
Make the GE ntsync patch auto-enable on systems that expose /dev/ntsync.

The imported patch series currently enables ntsync only when WINENTSYNC=1.
For these packaged builds we want ntsync to activate automatically where the
kernel device exists, with WINENTSYNC=0 remaining an escape hatch.
"""
from __future__ import annotations

import os
import sys


OLD = """static int get_enabled(void)
{
    static int enabled = -1;

    if (enabled == -1)
    {
        const char *env = getenv("WINENTSYNC");
        enabled = (env && !strcmp(env, "1"));
    }

    return enabled;
}
"""

NEW = """static int get_enabled(void)
{
    static int enabled = -1;

    if (enabled == -1)
    {
        const char *env = getenv("WINENTSYNC");
        enabled = !(env && !strcmp(env, "0"));
    }

    return enabled;
}
"""


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: fix_ntsync.py <wine-source-dir>")
        return 1

    path = os.path.join(sys.argv[1], "server", "inproc_sync.c")
    if not os.path.exists(path):
        print(f"SKIP: {path} not found")
        return 0

    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    if NEW in text:
        print("OK: ntsync auto-enable fix already present")
        return 0

    if OLD not in text:
        print("WARN: ntsync enable block not found; no change made")
        return 0

    text = text.replace(OLD, NEW, 1)

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print("FIXED: ntsync now auto-enables unless WINENTSYNC=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
