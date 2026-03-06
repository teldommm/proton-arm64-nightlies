#!/usr/bin/env python3
"""
Applies the Wow64SuspendLocalThread addition to dlls/wow64/process.c.

The upstream GameNative patch (test-bylaws/dlls_wow64_process_c.patch) is
corrupt/drifted against bleeding-edge, so we apply the change directly.

The patch also changed NtSuspendThread -> RtlWow64SuspendThread in
wow64_NtSuspendThread, but bleeding-edge already has that change.

What we add: Wow64SuspendLocalThread exported function at end of file.

Usage: fix_wow64_process_c.py <wine-source-dir>
"""
import sys
import os


ADDITION = '''

/**********************************************************************
 *           Wow64SuspendLocalThread  (wow64.@)
 */
NTSTATUS WINAPI Wow64SuspendLocalThread( HANDLE thread, ULONG *count )
{
    return NtSuspendThread( thread, count );
}
'''


def main():
    if len(sys.argv) < 2:
        print("Usage: fix_wow64_process_c.py <wine-source-dir>")
        sys.exit(1)

    wine_src = sys.argv[1]
    process_c = os.path.join(wine_src, "dlls", "wow64", "process.c")

    if not os.path.exists(process_c):
        print(f"ERROR: {process_c} not found")
        sys.exit(1)

    with open(process_c) as f:
        src = f.read()

    if "Wow64SuspendLocalThread" in src:
        print("Wow64SuspendLocalThread already present, skipping")
        return

    # Also ensure wow64_NtSuspendThread uses RtlWow64SuspendThread (already in bleeding-edge,
    # but guard against old versions just in case)
    if "return NtSuspendThread( handle, count );" in src:
        # Check it's inside wow64_NtSuspendThread
        idx = src.find("wow64_NtSuspendThread")
        if idx != -1:
            snippet = src[idx:idx+200]
            if "return NtSuspendThread( handle, count );" in snippet:
                src = src.replace(
                    "return NtSuspendThread( handle, count );",
                    "return RtlWow64SuspendThread( handle, count );",
                    1
                )
                print("  Replaced NtSuspendThread with RtlWow64SuspendThread in wow64_NtSuspendThread")

    src = src.rstrip() + "\n" + ADDITION

    with open(process_c, "w") as f:
        f.write(src)

    print("Added Wow64SuspendLocalThread to dlls/wow64/process.c")


if __name__ == "__main__":
    main()
