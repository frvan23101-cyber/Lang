"""Deliberately incomplete multilingual action-candidate lexicon.

Outputs candidates for manual review, not a validated semantic analysis.
Every observed span points to one saved instruction and source line.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

                                                                             
                                                                                
                                                                                     
LEXICON = {
    "en": {
        "cutting": {
            "cut": r"cut(?:s|ting)?", "chop": r"chopp?(?:ed|ing|s)?",
            "dice": r"dic(?:e|ed|es|ing)", "slice": r"slic(?:e|ed|es|ing)",
            "mince": r"minc(?:e|ed|es|ing)", "peel": r"peel(?:ed|ing|s)?",
            "grate": r"grat(?:e|ed|es|ing)", "shred": r"shred(?:ded|ding|s)?",
            "snip": r"snip(?:ped|ping|s)?", "tear": r"tear|tears|tearing|torn",
        },
        "heating": {
            "preheat": r"preheat(?:ed|ing|s)?", "heat": r"heat(?:ed|ing|s)?",
            "bake": r"bak(?:e|ed|es|ing)", "boil": r"boil(?:ed|ing|s)?",
            "simmer": r"simmer(?:ed|ing|s)?", "fry": r"fr(?:y|ies|ied|ying)",
            "roast": r"roast(?:ed|ing|s)?", "grill": r"grill(?:ed|ing|s)?",
            "brown": r"brown(?:ed|ing|s)?", "cook": r"cook(?:ed|ing|s)?",
            "melt": r"melt(?:ed|ing|s)?",
        },
        "mixing": {
            "mix": r"mix(?:ed|es|ing)?", "stir": r"stir(?:red|ring|s)?",
            "whisk": r"whisk(?:ed|ing|s)?", "beat": r"beat(?:en|ing|s)?",
            "knead": r"knead(?:ed|ing|s)?", "fold": r"fold(?:ed|ing|s)?",
            "blend": r"blend(?:ed|ing|s)?", "combine": r"combin(?:e|ed|es|ing)",
            "incorporate": r"incorporat(?:e|ed|es|ing)",
        },
    },
    "fr": {
        "cutting": {
            "couper": r"coup(?:er|ez|é|ée|és|ées|ant|ent|ons|ait|e)",
            "émincer": r"éminc(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "hacher": r"hach(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "peler": r"p(?:eler|elez|elé|elée|elés|elées|elant|èlent)",
            "éplucher": r"épluch(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "râper": r"râp(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "trancher": r"tranch(?:er|ez|é|ée|és|ées|ant|ent|ons)",
            "découper": r"découp(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "écraser": r"écras(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
        },
        "heating": {
            "préchauffer": r"préchauff(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "chauffer": r"chauff(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "cuire": r"cuire|cuis(?:ez|ent|ons)|cuit(?:e|s|es)?",
            "bouillir": r"bouill(?:ir|ez|i|ie|is|ies|ant|ent|ons|e)",
            "mijoter": r"mijot(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "dorer": r"dor(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "griller": r"grill(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "frire": r"frire|frit(?:e|s|es)?|fris",
            "rôtir": r"rôt(?:ir|i|ie|is|ies|ant|ent|ons)",
            "enfourner": r"enfourn(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "fondre": r"fondre|fond(?:u|ue|us|ues|ant|ent)",
        },
        "mixing": {
            "mélanger": r"mélang(?:er|ez|é|ée|és|ées|eant|ent|eons|e)",
            "remuer": r"remu(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "fouetter": r"fouett?(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
            "battre": r"battre|bat(?:tez|tent|tons)|batt(?:u|ue|us|ues|ant)",
            "pétrir": r"pétr(?:ir|i|ie|is|ies|issant|issent|issez)",
            "incorporer": r"incorpor(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
        },
    },
    "de": {
        "cutting": {
            "schneiden": r"(?:ab)?schneid(?:e|en|et|est|end\w*|t|te|ten)|geschnitten\w*",
            "hacken": r"hack(?:e|en|t|te|ten|end\w*)|gehack\w*|kleingehack\w*",
            "würfeln": r"würfel(?:n|t|te|ten|st|nd\w*)|gewürfel\w*",
            "schälen": r"schäl(?:e|en|t|te|ten|end\w*)|geschäl\w*",
            "reiben": r"reib(?:e|en|t|st|end\w*)|gerieb\w*",
            "zerkleinern": r"zerkleiner\w*|zerkleinert\w*",
        },
        "heating": {
            "vorheizen": r"vorheiz\w*|vorgeheiz\w*",
            "backen": r"back(?:e|en|t|te|ten|end\w*)|gebacken\w*",
            "braten": r"brat(?:e|en|t|te|ten|end\w*)|gebrat\w*|anbrat\w*|kurzgebrat\w*",
            "kochen": r"koch(?:e|en|t|te|ten|end\w*)|gekoch\w*|köchel(?:n|t|te|ten|nd\w*)",
            "rösten": r"röst\w*|geröst\w*",
            "erhitzen": r"erhitz\w*|erhitzt\w*",
            "schmoren": r"schmor\w*|geschmor\w*",
            "schmelzen": r"schmelz\w*|geschmolz\w*",
        },
        "mixing": {
            "mischen": r"misch\w*|gemisch\w*",
            "rühren": r"rühr(?:e|en|t|te|ten|end\w*)|gerühr\w*|verrühr\w*|umrühr\w*",
            "kneten": r"knet(?:e|en|t|te|ten|end\w*)|geknet\w*",
            "schlagen": r"schlag(?:e|en|t|te|ten|end\w*)|geschlag\w*|schläg\w*",
            "vermengen": r"vermeng\w*|vermengt\w*",
            "unterheben": r"unterheb\w*|untergehob\w*",
            "verarbeiten": r"verarbeit\w*|verarbeitet\w*",
        },
    },
}
FEATURES = {
    "en": {"size": r"small|large|tiny", "thickness": r"thin|thinly|thick|thickly",
           "length": r"short|long", "granularity": r"finely|coarsely",
           "uniformity": r"evenly|uniformly"},
    "fr": {"size": r"petit\w*|grand\w*", "thickness": r"fin(?:e|es|ement)?|épais\w*",
           "length": r"court\w*|long\w*", "granularity": r"finement|grossièrement",
           "uniformity": r"uniformément|régulièrement"},
    "de": {"size": r"klein\w*|groß\w*", "thickness": r"dünn\w*|dick\w*",
           "length": r"kurz\w*|lang\w*", "granularity": r"fein\w*|grob\w*",
           "uniformity": r"gleichmäßig\w*"},
}


def main():
    with (ROOT / "instructions.csv").open(encoding="utf-8", newline="") as f:
        instructions = list(csv.DictReader(f))
    compiled = {lang: [(domain, lemma, re.compile(pattern, re.I))
                       for domain, variants in domains.items()
                       for lemma, pattern in variants.items()]
                for lang, domains in LEXICON.items()}
    cues = {lang: [(feature, re.compile(pattern, re.I))
                   for feature, pattern in attributes.items()]
            for lang, attributes in FEATURES.items()}
    expressions, feature_rows = [], []
    for row in instructions:
        lang, text = row["language"], row["original_text"]
        for match in TOKEN.finditer(text):
            form = match.group()
            for domain, lemma, pattern in compiled[lang]:
                if pattern.fullmatch(form):
                    expressions.append({
                        "expression_id": f"EX-{len(expressions)+1:05d}",
                        "recipe_id": row["recipe_id"], "instruction_id": row["instruction_id"],
                        "source_line": row["source_line"],
                        "character_start": match.start(), "character_end": match.end(),
                        "surface_text": form, "tentative_lemma": lemma,
                        "semantic_domain": domain, "extraction_method": "lexicon_v1",
                        "verification_status": "unverified",
                    })
                    break
            for feature, pattern in cues[lang]:
                if pattern.fullmatch(form):
                    feature_rows.append({
                        "recipe_id": row["recipe_id"], "instruction_id": row["instruction_id"],
                        "source_line": row["source_line"], "character_start": match.start(),
                        "character_end": match.end(), "surface_text": form,
                        "candidate_dimension": feature, "verification_status": "unverified",
                    })
    for file, rows in (("expressions.csv", expressions), ("feature_cues.csv", feature_rows)):
        with (ROOT / file).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
    language = {r["instruction_id"]: r["language"] for r in instructions}
    stats = {
        "scope": "unverified candidate matches on 59 category-listed recipes; no cross-language claim",
        "instructions_by_language": dict(Counter(r["language"] for r in instructions)),
        "candidate_actions_by_language": dict(Counter(language[r["instruction_id"]] for r in expressions)),
        "action_types_by_language": {lang: len({r["tentative_lemma"] for r in expressions
                                               if language[r["instruction_id"]] == lang})
                                     for lang in ("en", "fr", "de")},
        "candidate_action_domain_counts": {lang: dict(Counter(r["semantic_domain"] for r in expressions
                                                              if language[r["instruction_id"]] == lang))
                                           for lang in ("en", "fr", "de")},
        "feature_cues_by_language": dict(Counter(language[r["instruction_id"]] for r in feature_rows)),
    }
    (ROOT / "pilot_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
