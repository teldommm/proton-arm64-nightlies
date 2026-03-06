#!/usr/bin/env python3
"""
Applies Android-specific changes to dlls/winex11.drv/window.c that cannot
be applied via patch due to line-number drift against bleeding-edge.

Changes applied:
1. Wrap x11drv_xinput2_enable calls with #ifdef HAVE_X11_EXTENSIONS_XINPUT2_H
2. Add #ifdef __ANDROID__ branch for class_hints->res_name/res_class in set_initial_wm_hints
3. Guard _NET_WM_PID/XdndAware block with #ifndef __ANDROID__ in set_initial_wm_hints
4. Add _NET_WM_PID via NtUserGetWindowThread in set_net_active_window (Android only)

Usage: fix_window_c.py <wine-source-dir>
"""
import sys
import os
import re


def is_guarded_xinput2(lines, idx):
    """Return True if line at idx is already inside HAVE_X11_EXTENSIONS_XINPUT2_H."""
    depth = 0
    for j in range(idx - 1, -1, -1):
        s = lines[j].strip()
        if s.startswith("#endif"):
            depth += 1
        elif s.startswith("#ifdef") or s.startswith("#if "):
            if depth == 0:
                return "HAVE_X11_EXTENSIONS_XINPUT2_H" in s
            depth -= 1
    return False


def apply_xinput2_guards(lines):
    """Wrap bare x11drv_xinput2_enable calls with #ifdef HAVE_X11_EXTENSIONS_XINPUT2_H."""
    result = []
    changes = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if "x11drv_xinput2_enable" in line:
            if not is_guarded_xinput2(result + [line], len(result)):
                result.append("#ifdef HAVE_X11_EXTENSIONS_XINPUT2_H\n")
                result.append(line)
                result.append("#endif\n")
                changes += 1
                print(f"  [xinput2 guard] {line.rstrip()}")
                i += 1
                continue
        result.append(line)
        i += 1
    return result, changes


def apply_android_class_hints(lines):
    """
    In set_initial_wm_hints, replace the class_hints block:
      class_hints->res_name = steam_proton / proton_app_class;
      class_hints->res_class = steam_proton / proton_app_class;
    with an #ifdef __ANDROID__ branch that sets process_name,
    and an #else branch with the original steam_proton logic.
    """
    src = "".join(lines)

    # Already patched?
    if "#ifdef __ANDROID__" in src and "process_name" in src:
        print("  [android class_hints] already applied, skipping")
        return lines, 0

    # Match the class_hints block inside set_initial_wm_hints
    # Pattern: if ((class_hints = XAllocClassHint())) { ... XSetClassHint ... XFree ... }
    pattern = re.compile(
        r'(    if \(\(class_hints = XAllocClassHint\(\)\)\)\n'
        r'    \{\n)'
        r'(        static char steam_proton\[\].*?'
        r'        XSetClassHint\( display, window, class_hints \);\n'
        r'        XFree\( class_hints \);\n'
        r'    \}\n)',
        re.DOTALL
    )

    android_block = (
        '    if ((class_hints = XAllocClassHint()))\n'
        '    {\n'
        '#ifdef __ANDROID__\n'
        '        class_hints->res_name = process_name;\n'
        '        class_hints->res_class = process_name;\n'
        '#else\n'
    )

    def replacer(m):
        inner = m.group(2)
        # Strip the opening "    {\n" that's now in android_block
        inner_body = inner[len("    {\n"):]
        # Close the #else before XSetClassHint
        # inner_body ends with "        XSetClassHint...\n        XFree...\n    }\n"
        # Insert #endif before XSetClassHint
        inner_body = inner_body.replace(
            "        XSetClassHint( display, window, class_hints );\n",
            "#endif\n        XSetClassHint( display, window, class_hints );\n",
            1
        )
        return android_block + inner_body

    new_src, n = pattern.subn(replacer, src)
    if n == 0:
        print("  [android class_hints] pattern not found, skipping")
        return lines, 0

    print(f"  [android class_hints] applied Android #ifdef to class_hints block")
    return new_src.splitlines(keepends=True), n


def apply_android_net_wm_pid(lines):
    """
    In set_initial_wm_hints, guard the _NET_WM_PID + XdndAware block
    with #ifndef __ANDROID__ ... #endif.
    """
    src = "".join(lines)

    if "#ifndef __ANDROID__" in src and "_NET_WM_PID" in src:
        print("  [android _NET_WM_PID] already applied, skipping")
        return lines, 0

    # Match: XSetWMProperties call, then getpid block, then XdndAware
    pattern = re.compile(
        r'(    XSetWMProperties\(display, window, NULL, NULL, NULL, 0, NULL, NULL, NULL\);\n)'
        r'(    /\* set the pid.*?'
        r'    XChangeProperty\( display, window, x11drv_atom\(XdndAware\),\n'
        r'                     XA_ATOM, 32, PropModeReplace, \(unsigned char\*\)&dndVersion, 1 \);\n)',
        re.DOTALL
    )

    def replacer(m):
        return (
            m.group(1) +
            "#ifndef __ANDROID__\n" +
            m.group(2) +
            "#endif\n"
        )

    new_src, n = pattern.subn(replacer, src)
    if n == 0:
        print("  [android _NET_WM_PID] pattern not found, skipping")
        return lines, 0

    print("  [android _NET_WM_PID] guarded _NET_WM_PID/XdndAware with #ifndef __ANDROID__")
    return new_src.splitlines(keepends=True), n


def apply_android_set_net_active_window(lines):
    """
    In set_net_active_window, add Android-only _NET_WM_PID update via
    NtUserGetWindowThread after the XFlush call.
    """
    src = "".join(lines)

    if "NtUserGetWindowThread" in src and "set_net_active_window" in src:
        print("  [android set_net_active] already applied, skipping")
        return lines, 0

    android_addition = (
        "\n#ifdef __ANDROID__\n"
        "    DWORD pid = 0;\n"
        "\n"
        "    NtUserGetWindowThread( hwnd, &pid );\n"
        "\n"
        "    XChangeProperty(data->display, window, x11drv_atom(_NET_WM_PID),\n"
        "                    XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&pid, 1);\n"
        "#endif\n"
    )

    # Match the end of set_net_active_window: XFlush then closing brace
    pattern = re.compile(
        r'(    XFlush\( data->display \);\n)'
        r'(\})\n'
        r'\n'
        r'(BOOL window_has_pending_wm_state)',
        re.DOTALL
    )

    def replacer(m):
        return m.group(1) + android_addition + m.group(2) + "\n\n" + m.group(3)

    new_src, n = pattern.subn(replacer, src)
    if n == 0:
        print("  [android set_net_active] pattern not found, skipping")
        return lines, 0

    print("  [android set_net_active] added Android _NET_WM_PID to set_net_active_window")
    return new_src.splitlines(keepends=True), n


def main():
    if len(sys.argv) < 2:
        print("Usage: fix_window_c.py <wine-source-dir>")
        sys.exit(1)

    wine_src = sys.argv[1]
    window_c = os.path.join(wine_src, "dlls", "winex11.drv", "window.c")

    if not os.path.exists(window_c):
        print(f"ERROR: {window_c} not found")
        sys.exit(1)

    with open(window_c) as f:
        lines = f.readlines()

    total = 0

    lines, n = apply_xinput2_guards(lines)
    total += n

    lines, n = apply_android_class_hints(lines)
    total += n

    lines, n = apply_android_net_wm_pid(lines)
    total += n

    lines, n = apply_android_set_net_active_window(lines)
    total += n

    with open(window_c, "w") as f:
        f.writelines(lines)

    print(f"\nDone. Applied {total} fix(es) to window.c")


if __name__ == "__main__":
    main()
