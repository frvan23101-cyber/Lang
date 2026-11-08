"""AI-authored normalization and explicit-feature coding of stage06 candidates.

This is an exploratory coding ledger, not expert-reviewed semantics. Every
output token points back to an instruction and the page revision. Contextual
geometry is recorded only with a literal evidence span in the same sentence.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from validation_stage4 import ROOT, frozen

OUT = ROOT / "stage07"
DIMS = ("size", "thickness", "length", "width", "granularity", "uniformity", "shape")
CONTEXTUAL = {"amener_à_ébullition", "passer_sur_plaque", "enlever_la_peau",
              "vider_le_gibier", "ziehen_im_Wasser"}
COMPOSITIONAL = {"kleinschneiden", "abschneiden", "verkochen", "weichkochen",
                 "mitkochen", "durchkochen", "mitgaren", "überbrühen",
                 "unterrühren", "einrühren", "verkneten", "verreiben"}
ROOTS = {"kleinschneiden": "schneiden", "abschneiden": "schneiden",
         "verkochen": "kochen", "weichkochen": "kochen", "mitkochen": "kochen",
         "durchkochen": "kochen", "mitgaren": "garen", "überbrühen": "brühen",
         "unterrühren": "rühren", "einrühren": "rühren", "verkneten": "kneten",
         "verreiben": "reiben"}
UNCERTAIN = {"purée": "purée is a process, but its cutting/mixing boundary is debatable",
             "plumer": "feather removal can be treated as preparation rather than cutting",
             "vider_le_gibier": "gut removal spans cutting and general preparation",
             "entkernen": "seed removal spans cutting and general preparation",
             "stampfen": "mashing can be classified as cutting or mixing",
             "dissoudre": "dissolution can be classified as mixing or a state change",
             "auflösen": "dissolution can be classified as mixing or a state change",
             "ziehen_im_Wasser": "heat depends on the nearby water or broth context",
             "verarbeiten": "general processing is not always strictly mixing"}
NON_GEOMETRIC = {"crack", "casser", "séparer", "plumer", "vider", "enlever",
                 "schälen", "entkernen", "abschneiden"}

                                                                               
                                                                                 
EXPLICIT = {
    ("VEN-03-V3-S001", 45): {"size": ("halves", "into halves"), "shape": ("halves", "into halves")},
    ("VEN-03-V3-S002", 0): {"size": ("not too small", "not too small")},
    ("VEN-04-V3-S011", 21): {"shape": ("squares", "into squares")},
    ("VFR-03-V3-S005", 42): {"size": ("small", "petits carrés"), "shape": ("squares", "petits carrés")},
    ("VFR-03-V3-S008", 0): {"shape": ("fillets", "en filets")},
    ("VFR-03-V3-S009", 0): {"size": ("small", "petits morceaux")},
    ("VFR-03-V3-S009", 12): {"size": ("small", "petits morceaux")},
    ("VFR-03-V3-S019", 0): {"thickness": ("thin", "fines tranches"), "shape": ("slices", "fines tranches")},
    ("VFR-03-V3-S030", 72): {"size": ("halves", "en deux"), "shape": ("halves", "en deux")},
    ("VDE-01-V3-S001", 58): {"shape": ("cubes", "in Würfel")},
    ("VDE-01-V3-S012", 79): {"shape": ("slices", "in Scheiben")},
    ("VDE-03-V3-S004", 66): {"shape": ("slices", "in Scheiben")},
    ("VDE-03-V3-S004", 174): {"shape": ("cubes", "in Würfel")},
    ("VDE-03-V3-S008", 61): {"shape": ("slices", "in Scheiben")},
    ("VDE-03-V3-S014", 41): {"granularity": ("coarse", "grobe Streifen"), "shape": ("strips", "grobe Streifen")},
    ("VDE-03-V3-S018", 101): {"length": ("approximately 3 cm", "etwa 3 cm lange Stücke")},
    ("VDE-03-V3-S020", 30): {"length": ("elongated", "längliche Streifen"), "shape": ("strips", "längliche Streifen")},
    ("VDE-03-V3-S021", 116): {"length": ("2–3 cm", "2 bis 3 cm lange Stücke")},
    ("VDE-03-V3-S022", 53): {"size": ("approximately 1 cm", "etwa 1 cm große Würfel"), "shape": ("cubes", "etwa 1 cm große Würfel")},
    ("VDE-03-V3-S023", 85): {"length": ("1 cm edge length", "1 cm Kantenlänge")},
    ("VDE-04-V3-S006", 11): {"granularity": ("fine", "fein würfeln")},
    ("VDE-04-V3-S006", 38): {"shape": ("rings", "in Ringe")},
}

LEXICAL = {"purée": {"granularity": "fine/puréed"},
           "vierteln": {"size": "quarters", "shape": "quarters"},
           "würfeln": {"shape": "cubes"},
           "kleinschneiden": {"size": "small"}}


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, columns):
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader();writer.writerows(rows)


def main():
    frozen()
    candidates = read(ROOT / "stage06/action_candidates_v4.csv")
    steps = {r["instruction_id"]: r for r in read(ROOT / "stage05/instructions_v3.csv")}
    page_urls = {r["recipe_id"]: (r["source_url"], r["source_revision_id"])
                 for r in read(ROOT / "stage04/internal/selected_pages.csv")}
    entries, evidence, seen_explicit = [], [], set()
    for seq, candidate in enumerate(candidates, 1):
        row = dict(candidate)
        step = steps[row["instruction_id"]]
        phrase = step["original_text"]
        a,b = int(row["character_start"]),int(row["character_end"])
        assert phrase[a:b] == row["surface_text"]
        assert (step["recipe_id"],str(step["source_line"])) == (row["recipe_id"],row["source_line"])
        row["candidate_id"] = f"C7-{seq:04d}"
        lemma = row["tentative_lemma"]
        if lemma == "kneten_variant":lemma = "kneten"
        elif lemma in CONTEXTUAL:lemma = {"amener_à_ébullition":"amener", "passer_sur_plaque":"passer",
            "enlever_la_peau":"enlever", "vider_le_gibier":"vider", "ziehen_im_Wasser":"ziehen"}[lemma]
        elif lemma == "schneiden" and row["surface_text"].lower().startswith("abschneid"):
            lemma = "abschneiden"
        row["normalized_lemma"] = lemma
        original_lemma = row["tentative_lemma"]
        row["encoding_type"] = ("contextual_construction" if original_lemma in CONTEXTUAL else
                                 "compositional_or_prefixed" if lemma in COMPOSITIONAL else "lexical_head")
        row["collapsed_root_sensitivity"] = ROOTS.get(lemma, lemma)
        row["review_status"] = "assistant_context_screened_unverified"
        row["semantic_uncertainty"] = UNCERTAIN.get(original_lemma, "")
        row["source_url"],row["source_revision_id"] = page_urls[row["recipe_id"]]
        row["instruction_text"] = phrase
        default = ("unspecified" if row["semantic_domain"] == "cutting" and
                   lemma not in NON_GEOMETRIC else "not_applicable")
        for dim in DIMS:
            row[f"{dim}_context_status"] = default
            row[f"{dim}_context_value"] = ""
            row[f"{dim}_lexical_value"] = LEXICAL.get(lemma,{}).get(dim,"")
        key = (row["instruction_id"],a)
        if key in EXPLICIT:
            seen_explicit.add(key)
            for dim,(value,quoted) in EXPLICIT[key].items():
                assert dim in DIMS and quoted in phrase, (key,dim,quoted)
                row[f"{dim}_context_status"] = "explicit"
                row[f"{dim}_context_value"] = value
                pos = phrase.index(quoted)
                evidence.append({"candidate_id": row["candidate_id"], "dimension": dim,
                    "value":value,"evidence_text":quoted,"instruction_id":row["instruction_id"],
                    "evidence_start":pos,"evidence_end":pos+len(quoted),
                    "coding_basis":"same_AI_contextual_phrase"})
        entries.append(row)
    assert seen_explicit == set(EXPLICIT), "orphan feature annotations"
    assert len(entries) == len({e["candidate_id"] for e in entries})
    write(OUT / "screened_actions.csv",entries,list(entries[0]))
    write(OUT / "dimension_evidence.csv",evidence,list(evidence[0]))
    counts=Counter(x["semantic_uncertainty"]!="" for x in entries)
    summary={"status":"assistant-coded pilot on development sample; not independently validated",
             "candidate_tokens":len(entries),"uncertain_domain_tokens":counts[True],
             "contextual_evidence_rows":len(evidence),
             "cutting_tokens":sum(x["semantic_domain"]=="cutting" for x in entries),
             "lexical_heads":sum(x["encoding_type"]=="lexical_head" for x in entries),
             "contextual_constructions":sum(x["encoding_type"]=="contextual_construction" for x in entries),
             "prefixed_or_compositional":sum(x["encoding_type"]=="compositional_or_prefixed" for x in entries),
             "normalization_rule":"lemma with domain as type key; context-only expressions separated",
             "geometry_rule":"explicit only when a verbatim cue is linked to an action in the same instruction"}
    (OUT / "coding_manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
