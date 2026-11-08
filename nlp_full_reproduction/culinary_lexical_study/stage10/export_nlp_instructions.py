"""Export the same 130 included articles' method segments for NLP analysis."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from stage10.prepare_corpus import load_pages, body, parse_page

OUT = ROOT / "stage10"
decisions = {r["recipe_id"]: r for r in csv.DictReader((OUT / "article_decisions.csv").open(encoding="utf-8"))}
frame, pages = load_pages()
lines = []
for (lang, title), (rank, _) in frame.items():
    rid = f"B{lang.upper()}-{rank:03d}"
    if decisions[rid]["decision"] != "included":
        continue
    page = pages[(lang, title)]
    assert page is not None
    _, steps, _ = parse_page({**page, "candidate_id": rid, "capture_complete": True, "lines": body(page)})
    assert steps, rid
    for step in steps:
        lines.append({"recipe_id": rid, "language": lang, "title": title,
                      "source_url": decisions[rid]["source_url"],
                      "revision_id": decisions[rid]["revision_id"],
                      "source_line": step["source_line"], "instruction_id": step["instruction_id"],
                      "text": step["original_text"]})
assert len({r["recipe_id"] for r in lines}) == 130
path = OUT / "nlp_instructions.jsonl"
path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in lines), encoding="utf-8")
print(f"exported {len(lines)} instructions from 130 articles to {path}")
