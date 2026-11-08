"""Freeze a fresh page-level validation sample and evaluate independent labels.

Usage: python validation_stage4.py prepare|check|compare|score
Prediction files live in stage04_internal, separate from annotator packets.
This script does not produce human annotations or infer their independence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from build_corpus import clean, parse_page
from pilot_extract import LEXICON, TOKEN
from pilot_extract_v2 import ADD, wrong_sense

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "stage04"
PACK = OUT / "annotator_packet"
INTERNAL = OUT / "internal"
SELECTED = {"en": [1, 2, 3, 4], "fr": [1, 2, 3, 4], "de": [1, 3, 4, 5]}
ROLE_COLS = ["annotator", "recipe_id", "language", "source_line", "normalized_text", "line_role", "comment"]
ACTION_COLS = ["annotator", "recipe_id", "language", "source_line", "surface_text", "occurrence_index", "semantic_domain", "full_expression_optional", "dimension_optional", "comment"]
PRED_COLS = ["recipe_id", "language", "source_line", "character_start", "character_end", "surface_text", "semantic_domain", "tentative_lemma"]
ROLES = {"instruction", "mixed", "ingredients", "context", "heading", "other"}
DOMAINS = {"cutting", "heating", "mixing"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def pages():
    all_pages = {r["candidate_id"]: r for r in map(json.loads, (ROOT / "validation_candidates.jsonl").read_text(encoding="utf-8").splitlines())}
    for r in map(json.loads, (ROOT / "validation_english_corrected.jsonl").read_text(encoding="utf-8").splitlines()):
        all_pages[r["candidate_id"]] = r
    selected = []
    frame = json.loads((ROOT / "validation_sampling_frame.json").read_text(encoding="utf-8"))
    existing = {(r["language"], r["title"]) for r in frame["previous_development_titles"]}
    for lang, ranks in SELECTED.items():
        for rank in ranks:
            p = all_pages[f"V{lang.upper()}-{rank:02d}"]
            assert p["capture_complete"] and p["observed_revid"]
            assert (lang, p["title"]) not in existing, p["title"]
            heading = next((x["t"] for x in p["lines"] if x["t"].startswith("# ")), "")
            assert heading.casefold() == ("# " + p["title"]).casefold(), (p["candidate_id"], heading)
            selected.append(p)
    assert len(selected) == 12
    return selected


def body_lines(page):
    """Only remove the surrounding navigation/footer, preserving ALL page body text."""
    anchors = {"VFR-03": "La recette", "VDE-01": "## 【32†Sonneberger",
               "VDE-03": "## Westfälisches Blindhuhn I", "VDE-05": "Zutaten:"}
    first = next(i for i, x in enumerate(page["lines"])
                 if x["t"].startswith(anchors.get(page["candidate_id"], "## Ingredients" if page["language"] == "en" else
                                     "## Ingrédients" if page["language"] == "fr" else "## Zutaten")))
    lines = page["lines"][first:]
    end = next((i for i, x in enumerate(lines)
                if x["t"].startswith(("Retrieved from", "Récupérée de", "【"))
                and ("†Image" in x["t"] or x["t"].startswith(("Retrieved from", "Récupérée de")))), len(lines))
    rows = []
    for x in lines[:end]:
        t = x["t"]
        if not t.strip() or re.match(r"^\s*(?:\[【.*(?:edit|modifier|Bearbeiten).*】\]|\* \* \*)\s*$", t, re.I):
            continue
        if t.startswith("【") and "†Image" in t:
            break
        rows.append({"annotator": "", "recipe_id": page["candidate_id"], "language": page["language"],
                     "source_line": str(x["n"]), "normalized_text": clean(t), "line_role": "", "comment": ""})
    return [r for r in rows if r["normalized_text"]]


def rules():
    merged = {}
    for lang, domains in LEXICON.items():
        merged[lang] = [(domain, lemma, re.compile(pattern, re.I))
                        for domain, stems in domains.items() for lemma, pattern in stems.items()]
        merged[lang] += [(domain, lemma, re.compile(pattern, re.I))
                         for domain, stems in ADD[lang].items() for lemma, pattern in stems.items()]
    return merged


def predictions(page, source):
                                                                                
                                                                            
    allowed = {int(line) for rid, line in source if rid == page["candidate_id"]}
    body_page = {**page, "lines": [x for x in page["lines"] if x["n"] in allowed]}
    _, steps, _ = parse_page(body_page)
    rows = []
    used_step_positions = defaultdict(int)
    lex = rules()[page["language"]]
    for step in steps:
        key = (step["recipe_id"], str(step["source_line"]))
        raw_line = source.get(key)
        if raw_line is None:
            raise ValueError(f"parser step outside frozen body: {key}")
        line = raw_line["normalized_text"]
        segment = step["original_text"]
        pos = line.find(segment, used_step_positions[key])
        if pos < 0:
            pos = line.find(segment)
        if pos < 0:
            raise ValueError(f"parser step fails to map to frozen text: {key}, {segment!r}")
        used_step_positions[key] = pos + len(segment)
        for token in TOKEN.finditer(segment):
            for domain, lemma, pattern in lex:
                if not pattern.fullmatch(token.group()):
                    continue
                if wrong_sense(page["language"], token.group(), segment[:token.start()], segment[token.end():], lemma):
                    break
                a, b = pos + token.start(), pos + token.end()
                assert line[a:b] == token.group()
                rows.append({"recipe_id": page["candidate_id"], "language": page["language"],
                             "source_line": key[1], "character_start": str(a), "character_end": str(b),
                             "surface_text": token.group(), "semantic_domain": domain,
                             "tentative_lemma": lemma})
                break
    return steps, rows


def packet_zip(name, roles, pages_by_id):
    target = OUT / f"validation_packet_{name}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in (PACK / "annotation_guide.md", PACK / "source_pages.jsonl", PACK / "frozen_lines.csv"):
            z.write(file, file.name)
        file = PACK / f"{name}_roles.csv"
        z.write(file, "line_roles.csv")
        file = PACK / f"{name}_actions.csv"
        z.write(file, "action_heads.csv")
    return target


def prepare():
    OUT.mkdir(exist_ok=True)
    PACK.mkdir(exist_ok=True)
    INTERNAL.mkdir(exist_ok=True)
    selected = pages()
    bodies = [r for p in selected for r in body_lines(p)]
    lookup = {(r["recipe_id"], r["source_line"]): r for r in bodies}
    assert len(lookup) == len(bodies)
    write_csv(PACK / "frozen_lines.csv", ROLE_COLS[1:-2],
              [{k: r[k] for k in ROLE_COLS[1:-2]} for r in bodies])
    (PACK / "source_pages.jsonl").write_text("\n".join(json.dumps({
        "recipe_id": p["candidate_id"], "language": p["language"], "title": p["title"],
        "source_url": p["source_url"], "source_revision_id": p["observed_revid"],
        "capture_date": p["capture_date"], "license": "Wikibooks CC BY-SA: see source page",
    }, ensure_ascii=False) for p in selected) + "\n", encoding="utf-8")
    steps, predicted, summary = [], [], []
    for p in selected:
        s, a = predictions(p, lookup)
        steps.extend(s); predicted.extend(a)
        summary.append({"recipe_id": p["candidate_id"], "language": p["language"], "title": p["title"],
                        "source_url": p["source_url"], "source_revision_id": p["observed_revid"],
                        "body_lines": len(body_lines(p)), "parser_instruction_segments": len(s),
                        "predicted_action_heads": len(a)})
    write_csv(INTERNAL / "frozen_predictions.csv", PRED_COLS, predicted)
    write_csv(INTERNAL / "parser_steps.csv", ["instruction_id", "recipe_id", "step_index", "language", "source_line", "original_text", "source_url", "source_revision_id"], steps)
    write_csv(INTERNAL / "selected_pages.csv", list(summary[0]), summary)
    write_csv(INTERNAL / "adjudicated_roles_BLANK.csv", ROLE_COLS, [{**r, "annotator": "ADJ"} for r in bodies])
    write_csv(INTERNAL / "adjudicated_actions_BLANK.csv", ACTION_COLS, [])
    for name in ("A", "B"):
        write_csv(PACK / f"{name}_roles.csv", ROLE_COLS, [{**r, "annotator": name} for r in bodies])
        write_csv(PACK / f"{name}_actions.csv", ACTION_COLS, [])
        packet_zip(name, bodies, selected)
    checks = [ROOT / x for x in ("validation_candidates.jsonl", "validation_english_corrected.jsonl",
                               "validation_sampling_frame.json", "build_corpus.py", "pilot_extract.py",
                               "pilot_extract_v2.py", "validation_stage4.py")]
    checks += [PACK / "frozen_lines.csv", PACK / "source_pages.jsonl", INTERNAL / "frozen_predictions.csv"]
    manifest = {"status": "AWAITING_INDEPENDENT_HUMAN_LABELS", "selection": SELECTED,
                "annotation_units": "entire content of 12 new recipe pages, not single sentences",
                "reference_labels": "none yet", "sample_frame": "validation_sampling_frame.json",
                "frozen_sha256": {str(p.relative_to(ROOT)): sha(p) for p in checks},
                "per_recipe": summary}
    (INTERNAL / "validation_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"recipe_count": len(selected), "body_lines": len(bodies), "parser_segments": len(steps),
                      "predictions": len(predicted), "summary": summary}, ensure_ascii=False, indent=2))


def frozen():
    m = json.loads((INTERNAL / "validation_manifest.json").read_text(encoding="utf-8"))
    for relative, value in m["frozen_sha256"].items():
        path = ROOT / relative
        if sha(path) != value:
            raise ValueError("Frozen evaluation input changed: " + relative)
    return m


def labels(name):
    roles = read_csv(OUT / f"{name}_roles.csv")
    actions = read_csv(OUT / f"{name}_actions.csv")
    frozen_rows = read_csv(PACK / "frozen_lines.csv")
    ref = {(r["recipe_id"], r["source_line"]): r for r in frozen_rows}
    keyed = {}
    for r in roles:
        k = (r["recipe_id"], r["source_line"])
        if k in keyed or k not in ref or (r["recipe_id"], r["language"], r["source_line"], r["normalized_text"]) != tuple(ref[k][c] for c in ROLE_COLS[1:-2]):
            raise ValueError(f"Invalid or duplicated role row {name}: {k}")
        if r["annotator"] != name or r["line_role"] not in ROLES:
            raise ValueError(f"Missing/invalid role or annotator in {name}: {k}")
        keyed[k] = r["line_role"]
    if set(keyed) != set(ref):
        raise ValueError(f"Incomplete role file for {name}: missing {len(set(ref)-set(keyed))}")
    spans = set()
    for r in actions:
        k = (r["recipe_id"], r["source_line"])
        if r["annotator"] != name or k not in ref or r["language"] != ref[k]["language"]:
            raise ValueError(f"Invalid action row identity for {name}: {k}")
        if keyed[k] not in {"instruction", "mixed"}:
            raise ValueError(f"Action on noninstruction line for {name}: {k}")
        if (r["semantic_domain"] not in DOMAINS or not TOKEN.fullmatch(r["surface_text"])
                or not r["occurrence_index"].isdigit() or int(r["occurrence_index"]) < 1):
            raise ValueError(f"Invalid span/domain/occurrence for {name}: {k}")
        value = ref[k]["normalized_text"]
        start = -1
        for _ in range(int(r["occurrence_index"])):
            start = value.find(r["surface_text"], start+1)
            if start < 0:
                raise ValueError(f"Absent surface in {name}: {k}, {r['surface_text']!r}")
        span = (*k, start, start + len(r["surface_text"]), r["semantic_domain"])
        if span in spans:
            raise ValueError(f"Duplicate span in {name}: {span}")
        spans.add(span)
    return keyed, spans


def check():
    frozen()
    for name in ("A", "B", "ADJ"):
        r, a = labels(name)
        print(name, len(r), len(a))


def compare():
    frozen()
    ar, aa = labels("A")
    br, ba = labels("B")
    rows = []
    for k in sorted(ar):
        if ar[k] != br[k]:
            rows.append({"recipe_id": k[0], "source_line": k[1], "difference": "role", "A": ar[k], "B": br[k]})
    for span in sorted(aa ^ ba):
        rows.append({"recipe_id": span[0], "source_line": span[1], "difference": "action_span",
                     "A": str(span[2:]) if span in aa else "", "B": str(span[2:]) if span in ba else ""})
    write_csv(INTERNAL / "validation_disagreements.csv", ["recipe_id", "source_line", "difference", "A", "B"], rows)
    agreements = Counter()
    for k in ar:
        lang = k[0][1:3].lower()
        agreements[lang, "total"] += 1
        agreements[lang, "same"] += ar[k] == br[k]
    result = {lang: {"same_line_roles": agreements[lang, "same"], "total_line_roles": agreements[lang, "total"],
                      "observed_agreement": agreements[lang, "same"] / agreements[lang, "total"]}
              for lang in ("en", "fr", "de")}
    (INTERNAL / "annotation_agreement.json").write_text(json.dumps({"line_roles": result,
        "matching_action_spans": len(aa & ba), "A_action_spans": len(aa), "B_action_spans": len(ba),
        "unresolved_disagreements": len(rows)}, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"unresolved_disagreements": len(rows), "agreement": result}, indent=2))


def score():
    frozen()
    if not (INTERNAL / "validation_disagreements.csv").exists():
        raise ValueError("Run 'compare' and adjudicate every disagreement before 'score'")
    a_roles, a_actions = labels("A")
    b_roles, b_actions = labels("B")
    gold_roles, gold = labels("ADJ")
    raw = read_csv(INTERNAL / "frozen_predictions.csv")
    source = {(r["recipe_id"], r["source_line"]): r["normalized_text"] for r in read_csv(PACK / "frozen_lines.csv")}
    pred = set()
    for r in raw:
        k = (r["recipe_id"], r["source_line"])
        s, e = int(r["character_start"]), int(r["character_end"])
        assert source[k][s:e] == r["surface_text"]
        pred.add((*k, s, e, r["semantic_domain"]))
    predicted_lines = {(r["recipe_id"], r["source_line"]) for r in read_csv(INTERNAL / "parser_steps.csv")}
    counts, errors = {}, []
    for lang in ("en", "fr", "de"):
        for domain in (*sorted(DOMAINS), "all"):
            sub = lambda s: {x for x in s if x[0].startswith("V"+lang.upper()+"-") and (domain == "all" or x[-1] == domain)}
            p, g = sub(pred), sub(gold)
            tp, fp, fn = len(p & g), len(p-g), len(g-p)
            counts[f"{lang}.{domain}"] = {"TP": tp, "FP": fp, "FN": fn,
                "precision": tp/(tp+fp) if tp+fp else None,
                "recall": tp/(tp+fn) if tp+fn else None}
            if domain == "all":
                for kind, collection in (("FP", p-g), ("FN", g-p)):
                    for rid, line, s, e, dom in sorted(collection):
                        errors.append({"kind": kind, "recipe_id": rid, "source_line": line,
                            "surface_text": source[rid, line][s:e], "semantic_domain": dom,
                            "parser_selected_line": str((rid, line) in predicted_lines)})
    linescore = {}
    for lang in ("en", "fr", "de"):
        ps = {k for k in predicted_lines if k[0].startswith("V"+lang.upper()+"-")}
        gs = {k for k, role in gold_roles.items() if k[0].startswith("V"+lang.upper()+"-") and role in {"instruction", "mixed"}}
        linescore[lang] = {"gold_instruction_lines": len(gs), "parser_instruction_lines": len(ps),
            "matched": len(gs & ps), "missed": len(gs-ps), "extra": len(ps-gs)}
    write_csv(INTERNAL / "validation_errors.csv", list(errors[0]) if errors else ["kind", "recipe_id", "source_line", "surface_text", "semantic_domain", "parser_selected_line"], errors)
    result = {"status": "evaluated_against_supplied_human_labels", "human_independence_not_machine_verifiable": True,
        "A_action_spans": len(a_actions), "B_action_spans": len(b_actions),
        "adjudicated_action_spans": len(gold), "action_head_scores": counts,
        "instruction_line_coverage": linescore,
        "scope": "12 Wikibooks pages, only cutting/heating/mixing action heads"}
    (INTERNAL / "validation_scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"prepare": prepare, "check": check, "compare": compare, "score": score}.get(command, lambda: sys.exit("usage: python validation_stage4.py prepare|check|compare|score"))()
