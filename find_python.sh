# Shared helper: echoes the path of the first Python that can actually open a
# Tk window, or nothing at all.
#
# The check must happen in a throwaway subprocess. A Tk built against a newer
# macOS SDK aborts the entire process on import ("macOS 15 (1507) or later
# required"), which no try/except inside Python can catch.

find_working_python() {
    _can_run() { "$1" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; }

    _candidates=""
    for _v in 3.13 3.12 3.11 3.10 3.9; do
        _candidates="$_candidates /Library/Frameworks/Python.framework/Versions/$_v/bin/python3"
        _candidates="$_candidates /opt/homebrew/bin/python$_v /usr/local/bin/python$_v python$_v"
    done
    _candidates="$_candidates /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3"

    for _c in $_candidates; do
        if command -v "$_c" >/dev/null 2>&1 && _can_run "$_c"; then
            echo "$_c"
            return 0
        fi
    done
    return 1
}
