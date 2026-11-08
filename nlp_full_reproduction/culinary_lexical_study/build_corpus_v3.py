"""Page-level procedure parser revision; preserves the earlier frozen v2 files.

Accepts the same capture dictionaries as build_corpus.parse_page. In particular,
it scans multiple methods per page, colon headings, inline labels, and numbered
steps. Output is exploratory and has not been independently human-labelled.
"""
from __future__ import annotations

import re

from build_corpus import EDIT, HEAD, clean, split_sentences

ING = re.compile(r"^(?:ingredients?|ingrédients?|zutaten)(?:\b|\s|$)", re.I)
METHOD = re.compile(r"^(?:procedure|preparation|préparation|method|feuille de route|zubereitung|herstellung|vorbereitungen)(?:\b|\s|$)", re.I)
SECTION = re.compile(r"^(?:rezepte?\b|noch ein rezept\b|autre recette\b)", re.I)
NON_METHOD = re.compile(r"^(?:notes?|tipps|références|quellenangaben|voir aussi|see also|references|beilagen|vorbemerkung|abkürzungen|conseils?)(?:\b|\s|$)", re.I)
INLINE = re.compile(r"^\s*(ingredients?|ingrédients?|zutaten|procedure|preparation|préparation|method|feuille de route|zubereitung)\s*:\s*(.*)$", re.I)
NUMBERED = re.compile(r"^\s*(?:\d+\s*(?:[.)]|[–-])\s+)")
BULLET = re.compile(r"^\s*\*\s+")
AMOUNT = re.compile(r"^\d+(?:\s*/\s*\d+)?(?:[.,]\d+)?\s+\S+")
NOISE = re.compile(r"^(?:\[|【|Retrieved from|Récupérée de|Erfasst von|Siehe auch\b|\* \* \*)", re.I)
COOKING = re.compile(
    r"\b(?:cut|chop|bake|fry|stir|mix|boil|heat|cook|whisk|sift|add|place|serve|soak|drain|"
    r"mélang|coup|découp|cui(?:re|t|tes|sons|sent)|mijot|faire|laisser|verser|sortir|rajouter|ajouter|"
    r"pouss|écras|retourn|récup|accompagn|arrêt|cuisson|batt|fouett|assaisonn|mettre|remplir|servir|tremper|piquer|"
    r"schneid|koch(?!schule|buch|wasser)|gekoch|back(?!werk|pulver|form|blech)|gebacken|brat|rühr|misch|knet|schäl|reib(?!er)|gerieb|geben|erwärm|verrühr|aufkoch|form(?:en|t)|geformt|"
    r"abkühl|eingerühr|gebacken|aufsetz|blanchier|überbrüh|auspress|erhitz|schmelz|zieh|"
    r"mitkoch|würfel|einkleid|verteil|schlag|schlagen|beigeb|aufgieß|gerieb|putz|wasch|"
    r"einweich|abschmeck|hinzu|zerkleiner|gemahl|unterrühr|einleg|ausroll|dünst|flüssig|"
    r"gesotten|stamp|preß|press|zerreib|ausgedrück|angemacht|übergieß|reiß|nimm|trockn|abgieß|kühl|stell|servier|ausstech)\w*\b", re.I)


def procedure_line(raw: str, value: str, state: str, ingredient_seen: bool) -> bool:
    """Apply different evidence thresholds inside and outside a method block."""
    if raw.lstrip().startswith("«") or value.startswith(("«", "↑")):
        return False
    if re.match(r"^(?:Temps de (?:préparation|cuisson|réalisation)|Niveau de Difficulté|(?:Pour|Recette pour) \d+|Plat et vin à consommer)", value, re.I):
        return False
    if not COOKING.search(value):
                                                                             
                                                                                     
        return state == "method" and bool(NUMBERED.match(raw) or BULLET.match(raw))
    if state == "method":
        return bool(NUMBERED.match(raw) or BULLET.match(raw) or len(value) > 30)
                                                                              
    if state in ("unknown", "ingredients"):
        if state == "unknown" and BULLET.match(raw) and not COOKING.match(value):
            return False                                                         
        return bool(NUMBERED.match(raw) or (ingredient_seen and len(value) > 45)
                    or (state == "unknown" and len(value) > 35))
    return False


def parse_page(page: dict) -> tuple[list[dict], list[dict], str]:
    if not page.get("capture_complete") or not page.get("lines"):
        return [], [], "incomplete page capture"
    rid, lang = page["candidate_id"], page["language"]
    ingredients, steps = [], []
    state, seen_ingredients = "unknown", False
    list_continuation = False
    method_started = False
    notes = set()
    for line in page["lines"]:
        raw = line["t"]
        if not raw.strip() or EDIT.search(raw) or NOISE.match(raw.strip()):
            continue
        heading = HEAD.match(raw)
        if heading:
            label = clean(heading.group(2)).lower().rstrip(" :：.\t")
            if ING.match(label) or label.startswith("man nehme"):
                state, seen_ingredients = "ingredients", True
                method_started = False
            elif METHOD.match(label):
                state = "method"
                method_started = False
            elif SECTION.match(label):
                state, seen_ingredients = "unknown", False
                method_started = False
            elif NON_METHOD.match(label):
                state = "other"
                                                                                 
            elif len(heading.group(1)) <= 2:
                state = "unknown"
            continue
        value = clean(raw)
        inline = INLINE.match(value)
        if inline:
            label, payload = inline.group(1).lower(), inline.group(2).strip()
            if ING.match(label):
                state, seen_ingredients = "ingredients", True
            else:
                state = "method"
            if not payload:
                continue
            value = payload
            notes.add("inline labels")
        if value.endswith(":") and len(value) < 75:
            list_continuation = bool(NUMBERED.match(raw))
            if not (list_continuation and COOKING.search(value)):
                continue
        if list_continuation and BULLET.match(raw):
            continue
        if not (NUMBERED.match(raw) and value.endswith(":")):
            list_continuation = False
        if state == "other":
            continue
        if state == "ingredients":
                                                                          
                                                                             
            if value.startswith(('"', '“')):
                boundary = re.search(r"\.\s+(?=(?:Die|Der|Das)\s+\S+\s+werden\b)", value)
                if boundary:
                    ingredients.append({"recipe_id": rid, "source_line": line["n"],
                                        "original_text": value[:boundary.end()].strip()})
                    value = value[boundary.end():]
                    notes.add("mixed ingredient and procedure line")
                    state = "method"
                                                                               
                                                                                
            if (BULLET.match(raw) or lang != "de" or
                    not procedure_line(raw, value, state, seen_ingredients and bool(ingredients))):
                ingredients.append({"recipe_id": rid, "source_line": line["n"], "original_text": value})
                continue
            notes.add("procedure after ingredient list")
            state = "method"
        if not procedure_line(raw, value, state, seen_ingredients):
            continue
        if state == "method" and not method_started and BULLET.match(raw) and AMOUNT.match(value):
            ingredients.append({"recipe_id": rid, "source_line": line["n"], "original_text": value})
            continue
                                                                             
        value = NUMBERED.sub("", value)
        if value.startswith(('"', '“')):
            value = value[1:]
        for item in split_sentences(value):
            if re.match(r"^(?:This step is optional\.|Le conseil de\b|(?:Die|Der|Das) \S+ (?:sind|ist)\b|Durch das \S+ entsteht\b|Wenn .{0,30}\bfertig (?:ist|sind)\b)", item, re.I):
                continue
            steps.append({"recipe_id": rid, "source_line": line["n"], "original_text": item})
        if state == "unknown":
            state = "method"
            notes.add("prose or numbered method")
        method_started = True
    for k, row in enumerate(steps, 1):
        row.update(instruction_id=f"{rid}-V3-S{k:03d}", step_index=k, language=lang,
                   source_url=page["source_url"], source_revision_id=page["observed_revid"])
    return ingredients, steps, "; ".join(sorted(notes))
