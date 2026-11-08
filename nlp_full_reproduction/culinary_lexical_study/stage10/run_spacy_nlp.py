"""Exploratory spaCy-assisted re-analysis of the 130 included recipe articles.

Requires installed en_core_web_sm, fr_core_news_sm and de_core_news_sm.
The cutting-verb and geometric-cue inventories remain explicit research choices;
POS, lemmatization, sentence structure and dependency links come from NLP models.
Results are new exploratory estimates, not human-validated ground truth.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

import spacy

HERE = Path(__file__).resolve().parent
MODELS = {"en": "en_core_web_sm", "fr": "fr_core_news_sm", "de": "de_core_news_sm"}
                                                                           
                                                                        
CUT_LEMMAS = {
    "en": {"cut", "chop", "dice", "slice", "mince", "grate", "shred", "snip", "tear", "quarter"},
    "fr": {"couper", "émincer", "hacher", "râper", "trancher", "découper", "tailler", "concasser"},
    "de": {"schneiden", "hacken", "würfeln", "reiben", "zerkleinern", "vierteln", "kleinschneiden"},
}
GEOMETRY = {
    "en": re.compile(r"\b(?:into\s+(?:halves|quarters|slices|strips|cubes|squares|pieces|wedges)|(?:small|large|thin|thick|fine|coarse|even|uniform|tiny|rough|bite[- ]sized)\s+(?:pieces|slices|chunks|strips|cubes|squares|wedges)|\d+(?:[.\-– ]\d+)?\s*(?:cm|mm)\b)", re.I),
    "fr": re.compile(r"\b(?:en\s+(?:deux|quatre|filets|tranches?|morceaux|rondelles|lamelles|carrés|cubes|dés)|(?:petits?|gross?es?|fines?|épaiss?es?|réguliers?|uniformes?)\s+(?:morceaux|tranches|carrés|cubes|dés|rondelles|lamelles)|\d+(?:[.,–\-]\d+)?\s*(?:cm|mm)\b)", re.I),
    "de": re.compile(r"\b(?:in\s+(?:Würfel|Scheiben|Streifen|Stücke|Ringe|Viertel)|(?:fein|grob|dünn|dick|klein(?:e|en|er|es)?)\s+(?:Würfel|Scheiben|Streifen|Stücke|Ringe)|\d+(?:[.,–\-]\d+)?\s*(?:cm|mm)\b)", re.I),
}


def is_cutting_verb(token, lang):
    if token.pos_ not in ("VERB", "AUX"):
        return False
    lemma = token.lemma_.casefold()
    surface = token.text.casefold()
    if lemma in CUT_LEMMAS[lang]:
        return True
                                                                            
    return lang == "de" and any(lemma.endswith(x) or surface.endswith(x) for x in ("schneiden", "hacken", "würfeln"))


def ancestor_distance(a, b):
    """Short path in the dependency tree, or a high penalty across clauses."""
    aa = {x.i: k for k, x in enumerate((a, *a.ancestors))}
    return min((aa[x.i] + k for k, x in enumerate((b, *b.ancestors)) if x.i in aa), default=999)


def process():
    models = {lang: spacy.load(name) for lang, name in MODELS.items()}
    for name, nlp in models.items():
        if "parser" not in nlp.pipe_names:
            raise RuntimeError(f"{name} model has no dependency parser")
    decisions = [r for r in csv.DictReader((HERE / "article_decisions.csv").open(encoding="utf-8")) if r["decision"] == "included"]
    assert len(decisions) == 130
    instructions = [json.loads(s) for s in (HERE / "nlp_instructions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["recipe_id"] for r in instructions} == {r["recipe_id"] for r in decisions}
    counts = {r["recipe_id"]: [0, 0] for r in decisions}
    audit = []
    for row in instructions:
        lang = row["language"]
        doc = models[lang](row["text"])
        for sent in doc.sents:
            heads = [t for t in sent if is_cutting_verb(t, lang)]
            if not heads:
                continue
            attached = defaultdict(list)
            for m in GEOMETRY[lang].finditer(sent.text):
                start = sent.start_char + m.start()
                end = sent.start_char + m.end()
                span = doc.char_span(start, end, alignment_mode="expand")
                if span is None:
                    continue
                                                                             
                                                                             
                owner = min(heads, key=lambda h: (ancestor_distance(span.root, h), abs(h.idx - start)))
                distance = ancestor_distance(span.root, owner)
                if distance <= 4 and abs(owner.idx - start) <= 110:
                    attached[owner.i].append(m.group(0))
            for head in heads:
                counts[row["recipe_id"]][0] += 1
                matched = attached.get(head.i, [])
                counts[row["recipe_id"]][1] += bool(matched)
                audit.append({"recipe_id": row["recipe_id"], "language": lang,
                              "instruction_id": row["instruction_id"], "source_line": row["source_line"],
                              "sentence": sent.text, "verb": head.text, "lemma": head.lemma_,
                              "pos": head.pos_, "dep": head.dep_, "linked_geometry": " | ".join(matched),
                              "E_flag": int(bool(matched))})
    article = []
    for d in decisions:
        A, E = counts[d["recipe_id"]]
        article.append({"recipe_id": d["recipe_id"], "language": d["language"], "title": d["title"],
                        "old_A": d["eligible_cutting_A"], "old_E": d["cues_E"],
                        "old_g": d["index_alpha1"], "nlp_A": A, "nlp_E": E,
                        "nlp_g": (E + 1) / (A + 2), "nlp_A_zero": int(A == 0)})
    summary = []
    for lang in ("fr", "de", "en"):
        group = [r for r in article if r["language"] == lang]
        summary.append({"language": lang, "n": len(group), "nlp_A": sum(r["nlp_A"] for r in group),
                        "nlp_E": sum(r["nlp_E"] for r in group),
                        "nlp_A_zero_articles": sum(r["nlp_A_zero"] for r in group),
                        "nlp_mean": statistics.mean(r["nlp_g"] for r in group),
                        "nlp_sample_sd": statistics.stdev(r["nlp_g"] for r in group),
                        "old_mean": statistics.mean(float(r["old_g"]) for r in group)})
    for filename, rows in (("nlp_cutting_audit.csv", audit), ("nlp_article_scores.csv", article), ("nlp_country_summary.csv", summary)):
        if not rows:
            raise RuntimeError(f"no data for {filename}; check models and lexicon")
        with (HERE / filename).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    for r in summary:
        print(f"{r['language']} n={r['n']} A={r['nlp_A']} E={r['nlp_E']} "
              f"mean={r['nlp_mean']:.4f} sd={r['nlp_sample_sd']:.4f} old={r['old_mean']:.4f}")
    print("MODEL-ASSISTED EXPLORATORY SCORES; no independent manual validation")


if __name__ == "__main__":
    process()
