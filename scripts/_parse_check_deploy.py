from pathlib import Path

lines = Path("scripts/deploy_production.ps1").read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines, 1):
    if any(ch in l for ch in ["\u2019", "\u2018", "\u201c", "\u201d", "\u00a0"]):
        print("smart", i, repr(l[:120]))

depth = 0
mode = None
for n, line in enumerate(lines, 1):
    j = 0
    while j < len(line):
        c = line[j]
        if mode is None:
            if c == "#":
                break
            if c == "'":
                mode = "sq"
            elif c == '"':
                mode = "dq"
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
        elif mode == "sq":
            if c == "'":
                mode = None
        elif mode == "dq":
            if c == "`":
                j += 1
            elif c == '"':
                mode = None
        j += 1
    interesting = n in (92, 108, 187, 198, 202, 206, 222, 301, 305, 309, 317, 319, 350, 361, 392, 424, 427)
    if interesting or mode is not None or depth < 0:
        safe = line[:100].encode("ascii", "backslashreplace").decode()
        print(f"{n} depth={depth} mode={mode} {safe}")
print("END", depth, mode)
