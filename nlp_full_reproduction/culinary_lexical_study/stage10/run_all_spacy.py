"""Rebuild inputs from captured pages, run both NLP analyses, verify outputs.

Execute: python run_all_spacy.py (from any working directory).
Model downloads must already be installed. Does not overwrite cutting baseline.
"""
import csv
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = ("en_core_web_sm", "fr_core_news_sm", "de_core_news_sm")
INPUT = HERE / "nlp_instructions.jsonl"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(script):
    print("RUN", script, flush=True)
    subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, check=True)


def rows(filename):
    with (HERE / filename).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    old_sha = sha(INPUT)
    run("export_nlp_instructions.py")
    assert sha(INPUT) == old_sha, "Regenerated instructions differ from frozen input"
    instructions = [json.loads(x) for x in INPUT.read_text(encoding="utf-8").splitlines()]
    assert len(instructions) == 1534 and len({x["recipe_id"] for x in instructions}) == 130
    run("run_spacy_nlp.py")
    run("run_spacy_other_actions.py")
    assert len(rows("nlp_article_scores.csv")) == 130
    assert len(rows("nlp_country_summary.csv")) == 3
    assert len(rows("other_actions_articles.csv")) == 260
    assert len(rows("other_actions_summary.csv")) == 6
    import spacy
    nlp = {name: spacy.load(name) for name in MODELS}
    outputs = ["nlp_cutting_audit.csv", "nlp_article_scores.csv", "nlp_country_summary.csv",
               "other_actions_audit.csv", "other_actions_articles.csv", "other_actions_summary.csv"]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "spacy_version": importlib.metadata.version("spacy"),
        "models": {name: {"version": pipe.meta.get("version"), "pipeline": pipe.pipe_names}
                   for name, pipe in nlp.items()},
        "input_sha256": old_sha,
        "instruction_count": len(instructions),
        "article_count": 130,
        "output_sha256": {f: sha(HERE / f) for f in outputs},
        "code_sha256": {f: sha(HERE / f) for f in
                        ("export_nlp_instructions.py", "run_spacy_nlp.py", "run_spacy_other_actions.py")},
        "note": "Both analyses use NLP predicted linguistic features and researcher-defined lexicons/cues. No independent human validation."
    }
    (HERE / "nlp_reproduction_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE: 130 articles; six CSV files; nlp_reproduction_manifest.json")


if __name__ == "__main__":
    main()
