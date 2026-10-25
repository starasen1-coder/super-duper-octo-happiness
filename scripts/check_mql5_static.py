#!/usr/bin/env python3
"""Conservative static sanity checks for MQL5 source; not a compiler."""
from __future__ import annotations
import re
import sys
from pathlib import Path

def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)

def strip_comments_and_strings(source: str) -> str:
    # Remove comments and string literals so delimiters inside them are ignored.
    token = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"')
    return token.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), source)

def main() -> None:
    if len(sys.argv) != 2:
        fail("Usage: check_mql5_static.py <source.mq5>")
    path = Path(sys.argv[1])
    if not path.is_file():
        fail(f"Source file not found: {path}")
    src = path.read_text(encoding="utf-8-sig")
    code = strip_comments_and_strings(src)

    for left, right, name in [("{", "}", "braces"), ("(", ")", "parentheses"), ("[", "]", "brackets")]:
        depth = 0
        for pos, char in enumerate(code):
            if char == left:
                depth += 1
            elif char == right:
                depth -= 1
                if depth < 0:
                    fail(f"Unmatched {right} in {name} near character {pos}")
        if depth != 0:
            fail(f"Unbalanced {name}: depth={depth}")

    required = [
        "#property strict",
        "int OnInit()",
        "void OnTick()",
        "void OnTradeTransaction(",
        "CalculateVolumeByRisk(isBuy, entry, sl)",
        "DailyGuardAllowed()",
        "TRADE_RETCODE_DONE",
    ]
    for token in required:
        if token not in src:
            fail(f"Required safety/entry token missing: {token}")

    functions = re.findall(
        r"(?m)^\s*(?:void|int|bool|double|string|long|ulong)\s+([A-Za-z_]\w*)\s*\(",
        code,
    )
    seen = set()
    duplicates = set()
    for fn in functions:
        if fn in seen:
            duplicates.add(fn)
        seen.add(fn)
    if duplicates:
        fail("Duplicate function definitions detected: " + ", ".join(sorted(duplicates)))

    if "BOS/OB/FVG logic is not implemented" not in src:
        fail("Expected limitation disclosure is missing")
    if "MathFloor(sl / step" not in src or "MathCeil(sl / step" not in src:
        fail("Stop-price directional rounding checks are missing")

    print(f"PASS: {path}; delimiters balanced; {len(functions)} unique function definitions; required guard checks present.")
    print("NOTE: Static checks only. MetaEditor compilation and Strategy Tester backtest are not performed by this workflow.")

if __name__ == "__main__":
    main()
