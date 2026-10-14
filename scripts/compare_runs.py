"""Compare two benchmark runs of scripts/eval_gold.py item by item (e.g. v0.1.2 vs v0.1.3).

  python scripts/compare_runs.py bench/results/v012 bench/results/v013
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(d: str) -> dict:
    return {r["id"]: r for r in json.loads((Path(d) / "summary.json").read_text(encoding="utf-8")) if "error" not in r}


def f1(r, key, kind="exact_PRF"):
    t = r.get(key) or {}
    return t[kind][2] if t.get("gold") else None


def main(a: str, b: str) -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles (cp949): print ✓/→ as "?" instead of crashing
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    A, B = load(a), load(b)
    fmt = lambda x: "  –  " if x is None else f"{x:.2f}"  # noqa: E731
    d = lambda x, y: "" if x is None or y is None else f"{y - x:+.2f}"  # noqa: E731
    print(f"{'item':26s} {'text kept':>10s} {'valid':>8s} {'entities F1':>18s} {'structure F1':>18s} {'@who':>14s}")
    sums = {"ent": [], "str": []}
    for k in [k for k in A if k in B]:
        x, y = A[k], B[k]
        e1, e2, s1, s2 = f1(x, "micro_entities"), f1(y, "micro_entities"), f1(x, "micro_structure"), f1(y, "micro_structure")
        w1, w2 = x["who"]["acc"], y["who"]["acc"]
        if e1 is not None and e2 is not None:
            sums["ent"].append(e2 - e1)
        if s1 is not None and s2 is not None:
            sums["str"].append(s2 - s1)
        print(f"{k:26s} {('✓' if x['text_identical'] else '✗') + ' → ' + ('✓' if y['text_identical'] else '✗'):>10s} "
              f"{('✓' if x['valid'] else '✗') + ' → ' + ('✓' if y['valid'] else '✗'):>8s} "
              f"{fmt(e1)} → {fmt(e2)} {d(e1, e2):>6s} {fmt(s1)} → {fmt(s2)} {d(s1, s2):>6s} {fmt(w1)} → {fmt(w2)}")
    for name, v in (("entities", sums["ent"]), ("structure", sums["str"])):
        if v:
            print(f"mean Δ {name} F1 (exact): {sum(v) / len(v):+.3f} over {len(v)} items")


if __name__ == "__main__":
    main(*sys.argv[1:3])
