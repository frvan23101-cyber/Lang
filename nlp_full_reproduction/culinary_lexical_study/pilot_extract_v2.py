"""A focused revision of v1 based on the 30 development instructions.

Keeps v1 files intact; evaluation is diagnostic because the same assistant
could see all sample texts. No independent language expert validation.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

from pilot_extract import LEXICON, TOKEN

ROOT = Path(__file__).resolve().parent
ADD = {
    "en": {},
    "fr": {"cutting": {"séparer": r"sépar(?:er|ez|é|ée|és|ées|ant|ent|ons|e)"},
           "heating": {"brûler": r"brûl(?:er|ez|é|ée|és|ées|ant|ent|ons|e)"}},
    "de": {"mixing": {"versprudeln": r"versprudl\w*"},
           "heating": {"aufkochen": r"aufkoch\w*",
                       "anschwitzen": r"anschwitz\w*"}},
}


def wrong_sense(lang, form, before, after, lemma):
    left = before.lower()
    right = after.lower()
    word = form.lower()
    if lang == "en":
        if lemma == "heat" and word == "heat" and re.search(
                r"\b(?:the|a|low|high|medium|gentle)\s+$", left):
            return True
        if lemma == "fold" and re.match(r"\s+in\s+(?:this|the)\s+(?:border|edge)", right):
            return True
        if lemma == "brown" and (re.search(r"\b(?:golden|pale|dark)\s+$", left)
                                 or re.match(r"\s+in\s+(?:colour|color)\b", right)):
            return True
    if lang == "fr" and lemma == "préchauffer" and word.startswith("préchauff"):
        if re.search(r"\bfour\s+$", left) and word.endswith(("é", "ée", "és", "ées")):
            return True
    if lang == "de" and lemma == "kochen" and word.startswith("kochend"):
        if re.match(r"\s+(?:wasser|milch|brühe|flüssigkeit)\b", right):
            return True
    return False


def main():
    with (ROOT / "instructions.csv").open(encoding="utf-8", newline="") as stream:
        instructions = list(csv.DictReader(stream))
    rules = {}
    for lang, domains in LEXICON.items():
        rules[lang] = [(domain, lemma, re.compile(pattern, re.I))
                       for domain, stems in domains.items()
                       for lemma, pattern in stems.items()]
        rules[lang].extend((domain, lemma, re.compile(pattern, re.I))
                           for domain, stems in ADD[lang].items()
                           for lemma, pattern in stems.items())
    result = []
    for instruction in instructions:
        text, lang = instruction["original_text"], instruction["language"]
        for match in TOKEN.finditer(text):
            for domain, lemma, pattern in rules[lang]:
                if not pattern.fullmatch(match.group()):
                    continue
                if wrong_sense(lang, match.group(), text[:match.start()],
                               text[match.end():], lemma):
                    break
                result.append({
                    "expression_id": f"EX2-{len(result)+1:05d}",
                    "recipe_id": instruction["recipe_id"],
                    "instruction_id": instruction["instruction_id"],
                    "source_line": instruction["source_line"],
                    "character_start": match.start(), "character_end": match.end(),
                    "surface_text": match.group(), "tentative_lemma": lemma,
                    "semantic_domain": domain, "extraction_method": "lexicon_v2",
                    "verification_status": "assistant_diagnostic_only",
                })
                break
    with (ROOT / "expressions_v2.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    counts = Counter(row["recipe_id"][:2] for row in result)
    print("action-head candidates (full corpus):", dict(counts))


if __name__ == "__main__":
    main()
