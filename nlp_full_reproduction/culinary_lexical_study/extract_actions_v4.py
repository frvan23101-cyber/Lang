"""Diagnostic action-head candidate revision for the 12 development pages.

Keeps the frozen v2 extractor and stage04/05 artifacts intact. The same AI
inspected these pages and wrote these rules; no independent evaluation is made.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from pilot_extract import LEXICON, TOKEN
from pilot_extract_v2 import ADD, wrong_sense

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "stage06"
EXTRA = {
    "en": {
        "cutting": {"break": r"break(?:s|ing)?|broke|broken", "crack": r"crack(?:s|ed|ing)?",
                    "purée": r"purée(?:s|d|ing)?"},
        "heating": {"stew": r"stew(?:s|ed|ing)?", "reheat": r"reheat(?:s|ed|ing)?"},
        "mixing": {"whip": r"whip(?:s|ped|ping)?"},
    },
    "fr": {
        "cutting": {"casser": r"cass(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "tailler": r"taill(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "concasser": r"concass(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "plumer": r"plum(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "enlever_la_peau": r"enlev(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "vider_le_gibier": r"vid(?:er|ez|é|ée|és|ées|ant|ent|ons|e)"},
        "heating": {"rissoler": r"rissol(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "saisir": r"sais(?:ir|issez|i|ie|is|ies|issant|issent)",
                    "réduire": r"réduire|rédui(?:t|te|s|tes|sez|sent|sons|sant)",
                    "pocher": r"poch(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "flétrir": r"flétr(?:ir|i|ie|is|ies|issant|issent)",
                    "amener_à_ébullition": r"amen(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                    "passer_sur_plaque": r"pass(?:er|ez|é|ée|és|ées|ant|ent|ons|e)"},
        "mixing": {"monter": r"mont(?:er|ez|é|ée|és|ées|ant|ent|ons|e)",
                   "dissoudre": r"dissou(?:dre|s|t|sant)|dissol(?:v(?:ez|ent)|u|ue|us|ues)"},
    },
    "de": {
        "cutting": {"brechen": r"brech(?:en|e|t|end\w*)|brich(?:t|st)",
                    "vierteln": r"viertel(?:n|t|te|ten|nd\w*)",
                    "entkernen": r"entkern\w*", "bröckeln": r"bröckel\w*",
                    "stampfen": r"stampf\w*|gestampf\w*",
                    "kleinschneiden": r"kleingeschnitt\w*",
                    "abziehen": r"ab(?:zu)?zieh\w*", "häuten": r"häut\w*"},
        "heating": {"verkochen": r"verkoch\w*", "weichkochen": r"weichkoch\w*",
                    "mitkochen": r"mitkoch\w*", "durchkochen": r"durchkoch\w*",
                    "dünsten": r"dünst\w*", "brühen": r"brüh\w*|gebrüh\w*",
                    "überbrühen": r"überbrüh\w*", "blanchieren": r"blanchier\w*",
                    "erwärmen": r"erwärm\w*", "mitgaren": r"mitgar\w*",
                    "ziehen_im_Wasser": r"zieh(?:en|t|st)"},
        "mixing": {"unterrühren": r"unterrühr\w*", "einrühren": r"einrühr\w*",
                   "verschlagen": r"verschlag\w*", "verkneten": r"verknet\w*",
                   "kneten_variant": r"knetet", "auflösen": r"auflös\w*",
                   "verreiben": r"verreib\w*"},
    },
}


def compile_rules(include_extra: bool):
    result = {}
    for lang in LEXICON:
        rows = []
        for group in (LEXICON[lang], ADD[lang], EXTRA[lang] if include_extra else {}):
            for domain, lemmas in group.items():
                rows.extend((domain, lemma, re.compile(pattern, re.I)) for lemma, pattern in lemmas.items())
        result[lang] = rows
    return result


def suppression(lang, text, match, domain, lemma):
    """Conservative lexical context checks; ambiguous usages stay unverified."""
    before = text[:match.start()]
    after = text[match.end():]
    lower = match.group().lower()
    left = before.lower()
    right = after.lower()
    if wrong_sense(lang, match.group(), before, after, lemma):
        return "previous_v2_context_filter"
    if lang == "en":
        if lemma == "brown" and re.match(r"\s+sugar\b", right):
            return "brown_sugar_ingredient"
        if lower in {"mixing", "baking", "cooked", "whipped", "broken", "preheated"}:
            if re.match(r"\s+(?:bowl|paper|tray|pan|rhubarb|cream|pieces|oven)\b", right):
                return "adjectival_ingredient_or_tool"
        if lower in {"incorporated", "combined", "mixed", "beaten"} and re.search(
                r"\b(?:until|just until|already|previously)\s+$", left):
            return "result_state_not_action"
        if lemma == "purée" and re.match(r"\s+(?:soup|potato)\b", right) and re.search(r"\b(?:the|a)\s+$", left):
            return "noun_not_action"
        if re.search(r"\b(?:not\s+to|avoid\s+)\s*$", left):
            return "negated_action"
    if lang == "fr":
        if lemma == "tailler" and lower == "taille" and re.search(r"\b(?:la|une|de)\s+$", left):
            return "size_noun_not_cutting_action"
        if lemma == "cuire" and lower.startswith("cuit") and (re.match(r"\s+à\s+cœur\b", right)
                                                       or re.search(r"\bêtre\s+$", left)):
            return "already_cooked_state"
        if lemma == "enlever_la_peau" and not re.search(r"\b(?:peau|écorce)\b", right[:75]):
            return "enlever_without_peeling_context"
        if lemma == "vider_le_gibier" and not re.search(r"\b(?:pièces|gibier|poisson)\b", right[:75]):
            return "vider_without_gutting_context"
        if lemma == "rôtir" and re.search(r"\bservi\s+à\s+$", left):
            return "past_equipment_use_not_current_action"
        if lemma == "amener_à_ébullition" and not re.search(r"\bà\s+ébullition\b", right[:100]):
            return "amener_without_boiling_context"
        if lemma == "passer_sur_plaque" and not re.search(r"\bsur\s+plaque\s+chauffante\b", right[:90]):
            return "passer_without_hotplate_context"
        if lemma == "mélanger" and lower == "mélange" and re.search(r"\b(?:le|ce|un|du|au|d'un)\s+$", left):
            return "noun_mixture"
        if lower == "fondue" and re.search(r"\b(?:la|une)\s+$", left):
            return "dish_name"
                                                                             
                                                                           
        if re.search(r"(?:é|ée|és|ées|i|ie|is|ies|u|ue|us|ues)$", lower):
            if not re.search(r"\b(?:avoir|ayant|avait|a|ont|est|sont|été)\s+(?:bien\s+)?$", left):
                if not (lemma == "cuire" and re.match(r"\s+à\s+feu\b", right)):
                    return "completed_ingredient_state"
    if lang == "de":
        if lemma == "brühen" and match.group() == "Brühe":
            return "broth_noun_not_heating"
        if lemma == "ziehen_im_Wasser" and not re.search(r"\b(?:wasser|hitze|topf|heiße?|brühe|siedend|kochend)\b", (left[-130:]+" "+right[:110]).lower()):
            return "ziehen_without_cooking_heat_context"
        if lower.startswith("kochend"):
            return "hot_state_not_heat_action"
        if match.group()[0].isupper() and (re.search(r"\b(?:zum|des|das|dem|der|unter|während|des)\s+$", left)
                                             or re.search(r"\bnennt man\s+[\"“]?\s*$", left)):
            if not (lemma == "kochen" and lower == "kochen" and re.search(r"\bzum\s+$", left)):
                return "nominalized_process_not_verb_head"
                                                                          
                                                                          
        if lower.startswith(("ge", "vor", "klein")) and (lower.startswith(("gesch", "gerieb", "geröst", "gekoch", "geback", "gehack", "gewürfel", "gemisch", "geschmolz", "geknet", "gebrat", "vorheiz", "vorgeheiz", "kleingeschnitt"))):
            if (re.search(r"(?:e|en|em|er|es)$", lower) and
                    re.match(r"\s+(?!und\s+(?:die|der|das|den|dem)\b)(?:(?:und\s+)?[a-zäöüß-]+\s+)?[A-ZÄÖÜ]\w*\b", after)):
                return "attributive_participle"
            clause = re.split(r"[.!?;]", left)[-1]
            passive = bool(re.search(r"\b(?:werden|wird|wurde|wurden|worden)\b", clause, re.I))
            perfect = bool(re.match(r"\s+haben\b", right))
            if not (passive or perfect):
                return "completed_ingredient_state"
        if lemma == "verarbeiten" and re.match(r"\s+(?:von|aus)\b", right):
            return "nonmixing_processing"
        if lemma == "kochen" and re.search(r"\bnicht\s+$", left) and re.match(r"\s+(?:dürfen|lassen)\b", right):
            return "prohibited_action"
    return ""


def extract(instructions, improved):
    compiled = compile_rules(improved)
    out, rejected = [], []
    for step in instructions:
        phrase = step["original_text"]
        for token in TOKEN.finditer(phrase):
            for domain, lemma, pattern in compiled[step["language"]]:
                if not pattern.fullmatch(token.group()):
                    continue
                entry = {"recipe_id": step["recipe_id"], "language": step["language"],
                         "source_line": step["source_line"], "instruction_id": step["instruction_id"],
                         "character_start": token.start(), "character_end": token.end(),
                         "surface_text": token.group(), "semantic_domain": domain,
                         "tentative_lemma": lemma}
                reason = suppression(step["language"], phrase, token, domain, lemma) if improved else (
                    "previous_v2_context_filter" if wrong_sense(step["language"], token.group(),
                          phrase[:token.start()], phrase[token.end():], lemma) else "")
                if reason:
                    rejected.append({**entry, "reason": reason})
                else:
                    out.append(entry)
                break
    return out, rejected


def save(path, rows, cols):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def main():
    from validation_stage4 import frozen
    frozen()
    steps = list(csv.DictReader((ROOT / "stage05/instructions_v3.csv").open(encoding="utf-8", newline="")))
    baseline, _ = extract(steps, False)
    new, rejected = extract(steps, True)
    cols = ["recipe_id", "language", "source_line", "instruction_id", "character_start", "character_end",
            "surface_text", "semantic_domain", "tentative_lemma"]
    save(STAGE / "action_candidates_v2_on_v3_steps.csv", baseline, cols)
    save(STAGE / "action_candidates_v4.csv", new, cols)
    save(STAGE / "rejected_matches_v4.csv", rejected, cols + ["reason"])
    key = lambda x: (x["instruction_id"], x["character_start"], x["character_end"], x["semantic_domain"])
    before = {key(x): x for x in baseline}; after = {key(x): x for x in new}
    changes = []
    for label, entries in (("newly_detected", after.keys()-before.keys()), ("previous_candidate_removed", before.keys()-after.keys())):
        for k in sorted(entries):
            row = after.get(k, before.get(k))
            changes.append({"change": label, **row,
                            "reason": next((r["reason"] for r in rejected if key(r) == k),
                                           "lexicon_or_context_revision")})
    save(STAGE / "action_changes.csv", changes, ["change"]+cols+["reason"])
    grouped = Counter((r["language"], version) for version, rows in (("v2",baseline),("v4",new)) for r in rows)
    stats = {"scope": "same 182 developer-inspected instruction segments from 12 new pages",
             "status": "AI-authored diagnostic; rule-development data, not independent test",
             "instruction_segments": len(steps), "baseline_candidates": len(baseline),
             "revised_candidates": len(new), "newly_detected": len(after.keys()-before.keys()),
             "previous_candidates_removed": len(before.keys()-after.keys()),
             "by_language": {lang:{version:grouped[lang,version] for version in ("v2","v4")} for lang in ("en","fr","de")}}
    (STAGE / "action_diagnostic_v4.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
