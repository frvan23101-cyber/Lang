"""Separate exploratory NLP-assisted indices for heating and mixing.

Run with the same nlp_instructions.jsonl and article_decisions.csv as the cutting
study. spaCy supplies POS/lemma/dependency structure; action and cue inventories
are explicit researcher-defined rules. Does not modify the cutting results.
"""
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

import spacy

HERE = Path(__file__).resolve().parent
MODELS = {"en": "en_core_web_sm", "fr": "fr_core_news_sm", "de": "de_core_news_sm"}
DOMAINS = ("heating", "mixing")
ACTIONS = {
    "en": {"heating": {"heat", "preheat", "bake", "boil", "simmer", "fry", "roast", "grill", "brown", "cook", "melt", "stew", "reheat", "steam", "blanch", "sauté"},
           "mixing": {"mix", "stir", "whisk", "beat", "knead", "fold", "blend", "combine", "incorporate", "whip", "dissolve"}},
    "fr": {"heating": {"préchauffer", "chauffer", "cuire", "bouillir", "mijoter", "dorer", "griller", "frire", "rôtir", "enfourner", "fondre", "rissoler", "saisir", "réduire", "pocher", "blanchir", "étuver"},
           "mixing": {"mélanger", "remuer", "fouetter", "battre", "pétrir", "incorporer", "dissoudre", "monter", "malaxer"}},
    "de": {"heating": {"vorheizen", "backen", "braten", "kochen", "rösten", "erhitzen", "schmoren", "schmelzen", "dünsten", "brühen", "blanchieren", "erwärmen", "aufkochen", "garen", "mitgaren", "mitkochen", "weichkochen", "verkochen", "durchkochen"},
           "mixing": {"mischen", "rühren", "kneten", "schlagen", "vermengen", "unterheben", "einrühren", "unterrühren", "verrühren", "auflösen", "verrühren", "verreiben"}},
}

                                                                    
                                                                      
CUE_PATTERNS = {
    "en": {
        "heating": {
            "time": r"\b(?:for\s+)?\d+(?:[.\-–]\d+)?\s*(?:min(?:ute)?s?|hours?|hrs?)\b",
            "temperature": r"\b\d{2,3}\s*°?\s*(?:c|f|celsius|fahrenheit)\b|\b(?:low|medium|high)\s+heat\b",
            "endpoint": r"\b(?:until\s+(?:golden|brown(?:ed)?|tender|soft|crispy|thick|melted|hot|boiling)|golden\s*brown)\b",
        },
        "mixing": {
            "time": r"\b(?:for\s+)?\d+(?:[.\-–]\d+)?\s*(?:min(?:ute)?s?|hours?|hrs?)\b",
            "manner": r"\b(?:gently|vigorously|slowly|gradually|quickly|lightly|well|thoroughly|clockwise)\b",
            "endpoint": r"\buntil\s+(?:smooth|combined|homogeneous|creamy|fluffy|stiff|thick|well\s+mixed)\b",
        },
    },
    "fr": {
        "heating": {
            "time": r"\b\d+(?:[.,\-–]\d+)?\s*(?:min(?:utes?)?|heures?|h)\b",
            "temperature": r"\b\d{2,3}\s*°?\s*(?:c|f|degrés?)\b|\b(?:feu\s+(?:doux|moyen|vif)|à\s+(?:feu\s+)?(?:doux|moyen|vif))\b",
            "endpoint": r"\b(?:jusqu['’]à\s+(?:coloration|ce\s+que|obtenir)|doré(?:e|s|es)?|tendre|croustillant(?:e|s|es)?)\b",
        },
        "mixing": {
            "time": r"\b\d+(?:[.,\-–]\d+)?\s*(?:min(?:utes?)?|heures?|h)\b",
            "manner": r"\b(?:doucement|vigoureusement|lentement|progressivement|délicatement|énergiquement|soigneusement)\b",
            "endpoint": r"\b(?:jusqu['’]à\s+(?:obtenir|ce\s+que)|homogène|lisse|crémeux|mousseux)\b",
        },
    },
    "de": {
        "heating": {
            "time": r"\b\d+(?:[.,\-–]\d+)?\s*(?:min(?:uten?)?|stunden?|std\.?|h)\b",
            "temperature": r"\b\d{2,3}\s*°?\s*(?:c|f|grad)\b|\b(?:bei\s+)?(?:schwacher|mittlerer|starker|niedriger)\s+hitze\b",
            "endpoint": r"\b(?:bis\s+(?:sie|es|die|alles|der|das)\s+\w+|goldbraun|weich|knusprig|gar)\b",
        },
        "mixing": {
            "time": r"\b\d+(?:[.,\-–]\d+)?\s*(?:min(?:uten?)?|stunden?|std\.?|h)\b",
            "manner": r"\b(?:vorsichtig|kräftig|langsam|gründlich|behutsam|gleichmäßig|schrittweise)\b",
            "endpoint": r"\b(?:bis\s+(?:eine|ein|alles)\s+\w+|glatt|homogen|schaumig|cremig)\b",
        },
    },
}
CUES = {l: {d: {k: re.compile(v, re.I) for k, v in groups.items()}
            for d, groups in domains.items()} for l, domains in CUE_PATTERNS.items()}


def candidates(token, lang):
    if token.pos_ not in {"VERB", "AUX"}:
        return []
    lemma = token.lemma_.casefold()
    return [domain for domain in DOMAINS if lemma in ACTIONS[lang][domain]]


def dep_distance(a, b):
    ancestors = {x.i: j for j, x in enumerate((a, *a.ancestors))}
    return min((ancestors[x.i] + j for j, x in enumerate((b, *b.ancestors)) if x.i in ancestors), default=999)


def write_csv(path, rows):
    assert rows, f"empty output: {path}"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    models = {lang: spacy.load(name) for lang, name in MODELS.items()}
    assert all("parser" in nlp.pipe_names for nlp in models.values())
    selected = [r for r in csv.DictReader((HERE / "article_decisions.csv").open(encoding="utf-8")) if r["decision"] == "included"]
    assert len(selected) == 130
    steps = [json.loads(x) for x in (HERE / "nlp_instructions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {x["recipe_id"] for x in steps} == {x["recipe_id"] for x in selected}
    counts = {(x["recipe_id"], domain): [0, 0] for x in selected for domain in DOMAINS}
    audit = []
    for row in steps:
        lang = row["language"]
        doc = models[lang](row["text"])
        for sent in doc.sents:
            for domain in DOMAINS:
                heads = [t for t in sent if domain in candidates(t, lang)]
                if not heads:
                    continue
                owners = defaultdict(list)
                for cue_type, pattern in CUES[lang][domain].items():
                    for match in pattern.finditer(sent.text):
                        start = sent.start_char + match.start()
                        span = doc.char_span(start, sent.start_char + match.end(), alignment_mode="expand")
                        if span is None:
                            continue
                        target = min(heads, key=lambda h: (dep_distance(span.root, h), abs(h.idx - start)))
                        if dep_distance(span.root, target) <= 4 and abs(target.idx - start) <= 110:
                            owners[target.i].append((cue_type, match.group(0)))
                for head in heads:
                    matched = owners.get(head.i, [])
                    counter = counts[(row["recipe_id"], domain)]
                    counter[0] += 1
                    counter[1] += bool(matched)
                    audit.append({"recipe_id": row["recipe_id"], "language": lang,
                                  "domain": domain, "instruction_id": row["instruction_id"],
                                  "source_line": row["source_line"], "sentence": sent.text,
                                  "verb": head.text, "lemma": head.lemma_, "pos": head.pos_,
                                  "linked_types": " | ".join(dict.fromkeys(k for k, _ in matched)),
                                  "linked_cues": " | ".join(x for _, x in matched),
                                  "has_specificity_cue": int(bool(matched))})
    article = []
    for row in selected:
        for domain in DOMAINS:
            A, E = counts[(row["recipe_id"], domain)]
            article.append({"recipe_id": row["recipe_id"], "language": row["language"],
                            "title": row["title"], "domain": domain, "A": A, "E": E,
                            "rate_when_A_positive": E / A if A else ""})
    summary = []
    for lang in ("fr", "de", "en"):
        for domain in DOMAINS:
            group = [r for r in article if r["language"] == lang and r["domain"] == domain]
            active = [r for r in group if r["A"] > 0]
            A = sum(r["A"] for r in group)
            E = sum(r["E"] for r in group)
            summary.append({"language": lang, "domain": domain, "total_articles": len(group),
                            "articles_with_action": len(active), "articles_without_action": len(group) - len(active),
                            "A_action_occurrences": A, "E_actions_with_cue": E,
                            "article_mean_active_only": statistics.mean(r["rate_when_A_positive"] for r in active) if active else "",
                            "article_sd_active_only": statistics.stdev(r["rate_when_A_positive"] for r in active) if len(active) > 1 else "",
                            "pooled_action_rate": E / A if A else ""})
    write_csv(HERE / "other_actions_audit.csv", audit)
    write_csv(HERE / "other_actions_articles.csv", article)
    write_csv(HERE / "other_actions_summary.csv", summary)
    for row in summary:
        print(row)
    print("Exploratory NLP-assisted coding; no independent linguistic validation")


if __name__ == "__main__":
    main()
