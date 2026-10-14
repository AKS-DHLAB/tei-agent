"""Offline generality probe (no API calls): for every benchmark item, what one version of tei_agent would send to the
model (exemplar fit, Korean/KNoTE-specific text in the rules, prompt length) and whether its text-preservation check
wrongly rejects the correct gold encoding.

  python scripts/probe_prompts.py <package_root> <bench_root>  > probe.json
  e.g. python scripts/probe_prompts.py ../tei-agent-0.1.2 .   and   python scripts/probe_prompts.py . .
Needs bench/data (scripts/fetch_bench.py)."""
import json, re, sys
from pathlib import Path
pkg, bench = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(pkg)); sys.path.insert(0, str(bench / "scripts"))
from tei_agent.config import Settings
from tei_agent.pipeline import Session
from tei_agent.profiles import GENRES
from tei_agent.xmlutils import check_preservation
from tei_agent import exemplars as EX
import importlib.util
spec = importlib.util.spec_from_file_location("eg", bench / "scripts" / "eval_gold.py")  # gold parsing only (v0.1.3 helper)
HANGUL = re.compile(r"[가-힣]")
items = json.loads((bench / "bench" / "manifest.json").read_text())["items"]
out = []
for it in items:
    eg = importlib.util.module_from_spec(spec); spec.loader.exec_module(eg)
    xml = (bench / "bench" / "data" / f"{it['id']}.xml").read_text(encoding="utf-8")
    blocks = [b for b in eg.gold_blocks(xml, it.get("container", "")) if eg.raw_of_block(b)]
    # 1) text-preservation check of THIS version on correct gold encodings (all blocks of the item, no length cut)
    rejected = sum(1 for b in blocks if not check_preservation(eg.raw_of_block(b), b)["ok"])
    # 2) the tagging prompt this version would send for this language/genre
    s = Session("x", Settings()); s.genre = it["genre"]; s.langs = [it["lang"]]; s.tagset = list(GENRES[it["genre"]]["core"])
    prompt = s._tag_system()
    rules = prompt.split("3. Use ONLY these markup categories now:")[1].split("4. Use ONLY attributes")[0]
    ex = EX.select(it["genre"], [it["lang"]], GENRES[it["genre"]].get("exemplars", []), k=2)
    out.append({"id": it["id"], "lang": it["lang"], "genre": it["genre"], "gold_blocks": len(blocks), "gold_rejected": rejected,
                "exemplars": [(d["id"], d["lang"], d["genre"]) for d in ex],
                "ex_genre_match": sum(d["genre"] == it["genre"] for d in ex), "ex_lang_match": sum(d["lang"] == it["lang"] for d in ex),
                "ex_mismatch_both": sum(d["genre"] != it["genre"] and d["lang"] != it["lang"] for d in ex),
                "hangul_in_rules": len(HANGUL.findall(rules)), "knote_in_rules": rules.count("KNoTE"),
                "prompt_chars": len(prompt)})
print(json.dumps(out, ensure_ascii=False))
