# GDB Python script — lists variables in scope at the current PC.
#
# Walks the lexical block chain from the current frame and filters
# by declaration line (symbol.line <= current line).  This correctly
# excludes variables declared after the current stop point even when
# GCC -O0 gives them function-wide DWARF scope.
#
# Output: single line  "ZENSCOPE:name1 name2 name3"
# On error: "ZENSCOPE:" (empty — caller treats this as "show all")
# Sourced from GdbClient via  -interpreter-exec console "source <path>"

try:
    import gdb

    f = gdb.selected_frame()
    b = f.block()
    stop_line = f.find_sal().line

    names = set()
    while b is not None and not b.is_global and not b.is_static:
        for s in b:
            if (s.is_variable or s.is_argument) and s.line <= stop_line:
                names.add(s.name)
        b = b.superblock

    print("ZENSCOPE:" + " ".join(sorted(names)))
except Exception:
    print("ZENSCOPE:")
