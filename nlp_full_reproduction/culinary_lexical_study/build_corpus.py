"""Convert the saved, line-numbered Wikibooks view captures to an exploratory corpus.

No network access is used. Page provenance is retained; this is a rendered-view
transcription, not a byte-exact dump of source HTML/wikitext.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAPTURES = ("web_capture_en.jsonl", "web_capture_fr_v2.jsonl", "web_capture_de.jsonl")
EXCLUDED = {"DE-06": "page contains Canadian pancakes and Palatschinken as separate subrecipes"}
LINK = re.compile(r"【\d+†([^†】]+)(?:†[^】]+)?】")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÜŒÄÖÜ])")
HEAD = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
EDIT = re.compile(r"\[(?:edit|modifier|Bearbeiten|Quelltext bearbeiten|modifier le wikicode)", re.I)
INGREDIENT = re.compile(r"^(?:ingredients?|ingrédients?(?: de | pour |$)|zutaten(?: |$))", re.I)
METHOD = re.compile(r"^(?:procedure|method|préparation|zubereitung|herstellung|vorbereitungen)(?:\s|$)", re.I)
PRIMARY_END = re.compile(r"^(?:variante|autre recette|method (?:2|ii)|préparation avec un four|conseil|notes?|tipps|références|quellen|voir aussi|warnings|web+links|beilagen)(?:\s|$)", re.I)


def clean(text: str) -> str:
    text = LINK.sub(lambda m: m.group(1), text)
    text = re.sub(r"\^\{[^}]*\}", "", text)
    text = re.sub(r"^\s*(?:\d+\.\s*|\*\s*)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sentences(text: str) -> list[str]:
    protected = re.sub(r"\b(?:evtl|ggf|ca|z\.B|u\.a|i\.d\.R|Min|etc)\.(?=\s+[A-ZÀ-Ü])",
                       lambda m: m.group().replace(".", "∯"), text, flags=re.I)
    return [p.replace("∯", ".").strip() for p in SENTENCE.split(protected)
            if len(p.strip()) > 2]


def parse_page(page: dict) -> tuple[list[dict], list[dict], str]:
    lang, rid = page["language"], page["candidate_id"]
    if rid in EXCLUDED:
        return [], [], EXCLUDED[rid]
    if not page["capture_complete"] or not page["lines"]:
        return [], [], "incomplete page capture"
    ingredients, steps = [], []
    state, began_method, stop = "", False, False
    fallback_ingredient_tail = False
    list_continuation = False
    for line in page["lines"]:
        raw = line["t"]
        heading = HEAD.match(raw)
        if heading:
            level, label = len(heading.group(1)), clean(heading.group(2)).lower()
            if began_method and (PRIMARY_END.match(label) or (level <= 2 and INGREDIENT.match(label))):
                stop = True
                break
            if INGREDIENT.match(label):
                state = "ingredients"
            elif METHOD.match(label):
                state = "method"
                began_method = True
            elif label.startswith("recette"):
                state = "recipe_container"
            elif level <= 2 and state == "method":
                break
            elif level <= 2 and state == "ingredients":
                state = ""
            continue
        if stop or not raw.strip() or EDIT.search(raw) or raw.lstrip().startswith(("【", "[", "Image")):
            continue
        value = clean(raw)
        if value.startswith(("Erfasst von", "Retrieved from", "Récupérée de")):
            continue                                     
        if not value or value.startswith(("↑", "Pour 6 personnes", "Pour 6 à 8 personnes")):
            continue
        if state == "recipe_container":
            if re.match(r"^\s*\*", raw) and not began_method:
                ingredients.append({"recipe_id": rid, "source_line": line["n"], "original_text": value})
                continue
            if re.match(r"^\s*\d+\.\s+", raw):
                state = "method"
                began_method = True
        if state == "ingredients":
            if re.match(r"^\s*\*", raw):
                ingredients.append({"recipe_id": rid, "source_line": line["n"], "original_text": value})
            elif lang == "de" and not began_method and ingredients and len(value) > 70 and re.search(r"[.!?]", value):
                                                                               
                fallback_ingredient_tail = True
                for item in split_sentences(value):
                    steps.append({"recipe_id": rid, "source_line": line["n"], "original_text": item})
        elif state == "method":
            if value.lower().startswith(("temps de préparation", "temps de cuisson")):
                continue
            if re.match(r"^\s*\d+\.\s+", raw):
                list_continuation = value.endswith(":")
            elif list_continuation and re.match(r"^\s*\*", raw):
                continue                                                      
            else:
                list_continuation = False
            if value.endswith(":") and len(value) < 70:
                continue                                          
            if (lang == "de" and not steps and re.match(r"^\s*\*", raw)
                    and re.match(r"^\d+(?:[/.,]\d+)?\s+", value)):
                ingredients.append({"recipe_id": rid, "source_line": line["n"],
                                    "original_text": value})
                continue                                                    
            if re.match(r"^\s*(?:\d+\.|\*)\s+", raw) or (len(value) > 35 and re.search(r"[.!?]", value)):
                for item in split_sentences(value):
                    steps.append({"recipe_id": rid, "source_line": line["n"], "original_text": item})
    for k, row in enumerate(steps, 1):
        row["instruction_id"] = f"{rid}-S{k:03d}"
        row["step_index"] = k
        row["language"] = lang
        row["source_url"] = page["source_url"]
        row["source_revision_id"] = page["observed_revid"]
    return ingredients, steps, ("inline method under ingredients" if fallback_ingredient_tail else "")


def write_csv(filename: str, columns: list[str], rows: list[dict]):
    with (ROOT / filename).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    captures = [json.loads(line) for file in CAPTURES for line in
                (ROOT / file).read_text(encoding="utf-8").splitlines() if line]
    recipes, all_ingredients, instructions = [], [], []
    for page in captures:
        ingredients, steps, reason = parse_page(page)
        recipes.append({
            "recipe_id": page["candidate_id"],
            "language": page["language"],
            "title": page["title"],
            "source_url": page["source_url"],
            "source_revision_id": page["observed_revid"],
            "capture_date": page["capture_date"],
            "recipe_category_basis": "Wikibooks country/region category",
            "instruction_count": len(steps),
            "ingredient_line_count": len(ingredients),
            "inclusion_status": "exploratory" if steps else "excluded",
            "quality_note": reason,
        })
        all_ingredients.extend(ingredients)
        instructions.extend(steps)
    write_csv("recipes.csv", list(recipes[0]), recipes)
    write_csv("ingredients.csv", ["recipe_id", "source_line", "original_text"], all_ingredients)
    write_csv("instructions.csv",
              ["instruction_id", "recipe_id", "step_index", "language", "source_line",
               "original_text", "source_url", "source_revision_id"], instructions)
    from collections import Counter
    print("recipes:", Counter((r["language"], r["inclusion_status"]) for r in recipes))
    print("instruction sentences:", Counter(r["language"] for r in instructions))
    print("ingredient lines:", Counter(r["recipe_id"][:2] for r in all_ingredients))


if __name__ == "__main__":
    main()
