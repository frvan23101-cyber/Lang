"""Merge every country-category page captured to date and score article-level eligibility.

No per-language exceptions or within-article dropping. Article failures stay in
the inventory, and ambiguous linguistic coding remains assistant-generated.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from build_corpus_v3 import parse_page
from extract_actions_v4 import extract
from annotate_metric_pilot import CONTEXTUAL, ROOTS, UNCERTAIN, NON_GEOMETRIC
from develop_pilot_index import pilot_index

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "stage10"
FRAME = json.loads((ROOT / "validation_sampling_frame.json").read_text(encoding="utf-8"))
SOURCES = ["web_capture_en.jsonl", "web_capture_fr_v2.jsonl", "web_capture_de.jsonl",
           "validation_candidates.jsonl", "validation_english_corrected.jsonl", "stage08/source_pages.jsonl",
           "stage10/raw_capture_batch0.jsonl", "stage10/raw_capture_batch1.jsonl"]
FOOTER = re.compile(r"^(?:Retrieved from|Récupérée de|Abgerufen von|【\d+†Image】)")
CUT_CUE = {
    "en": re.compile(r"\b(?:into\s+(?:halves|quarters|slices|strips|cubes|squares|pieces|wedges)|"
                     r"(?:small|large|thin|thick|fine|coarse|even|uniform|tiny|rough|bite[- ]sized)\s+"
                     r"(?:pieces|slices|chunks|strips|cubes|squares|wedges)|\d+(?:[.\-– ]\d+)?\s*(?:cm|mm)\b)",re.I),
    "fr": re.compile(r"\b(?:en\s+(?:deux|quatre|filets|tranches?|morceaux|rondelles|lamelles|carrés|cubes|dés)|"
                     r"(?:petits?|gross?es?|fines?|épaiss?es?|réguliers?|uniformes?)\s+"
                     r"(?:morceaux|tranches|carrés|cubes|dés|rondelles|lamelles)|\d+(?:[.,–\-]\d+)?\s*(?:cm|mm)\b)",re.I),
    "de": re.compile(r"\b(?:in\s+(?:Würfel|Scheiben|Streifen|Stücke|Ringe|Viertel)|"
                     r"(?:fein|grob|dünn|dick|klein(?:e|en|er|es)?)\s+"
                     r"(?:Würfel|Scheiben|Streifen|Stücke|Ringe)|\d+(?:[.,–\-]\d+)?\s*(?:cm|mm)\b)",re.I),
}
NEGATIVE = {"en":re.compile(r"\b(?:cutting\s+board|orange\s+peel|lemon\s+peel|apple\s+peel|"
                               r"(?:a|the)\s+cutting\s+\w+)\b",re.I),
            "fr":re.compile(r"\b(?:d'un\s+mélange|de\s+mélange)\b",re.I),
            "de":re.compile(r"\b(?:nach dem Kochen)\b",re.I)}


def load_pages():
    frame={(l,p["title"]):(i+1,p["id"]) for l in ("en","fr","de") for i,p in enumerate(FRAME["category_pages"][l])}
    candidates={k:[] for k in frame}
    supplement={x["title"]:x for x in map(json.loads,(OUT/"supplement_tails.jsonl").read_text(encoding="utf-8").splitlines())}
    for source_index,name in enumerate(SOURCES):
        for page in map(json.loads,(ROOT/name).read_text(encoding="utf-8").splitlines()):
            key=(page["language"],page["title"])
            if key not in frame:continue
            if name.startswith("stage10/raw_capture"):
                if not page["matched"]:continue
                fix=supplement.get(page["title"])
                if fix:
                    combined={x["n"]:x for x in page["lines"]}
                    combined.update({x["n"]:x for x in fix["lines"]})
                    page["lines"]=[combined[n] for n in sorted(combined)]
                    page["observed_revid"]=page["observed_revid"] or fix["rev"]
                page["capture_complete"]=bool(page["observed_revid"])
            if not page.get("capture_complete") or not page.get("lines"):continue
            lines=page["lines"]
            title_headers=[x["t"] for x in lines if x["t"].startswith("# ")]
            if title_headers and not any(x.casefold()=="# "+page["title"].casefold() for x in title_headers) and not name.startswith("web_capture_"):
                continue
            if not page.get("observed_revid") and not page.get("observed_revision_id"):
                continue
            candidate={**page,"source_file":name,"source_priority":source_index}
            candidates[key].append(candidate)
    selected={k:max(v,key=lambda p:(p["source_priority"],len(p["lines"]))) if v else None for k,v in candidates.items()}
    return frame,selected


def body(page):
    lines=page["lines"]
    assert lines
    start=next((i+1 for i,x in enumerate(lines) if x["t"].casefold()=="# "+page["title"].casefold()),0)
    lines=lines[start:]
    end=next((i for i,x in enumerate(lines) if FOOTER.match(x["t"])),len(lines))
    return lines[:end]


def normalize(r):
    lemma=r["tentative_lemma"]
    if lemma=="kneten_variant":lemma="kneten"
    elif lemma in CONTEXTUAL:
        lemma={"amener_à_ébullition":"amener","passer_sur_plaque":"passer",
               "enlever_la_peau":"enlever","vider_le_gibier":"vider",
               "ziehen_im_Wasser":"ziehen"}[lemma]
    elif lemma=="schneiden" and r["surface_text"].lower().startswith("abschneid"):
        lemma="abschneiden"
    return lemma


def coding(actions,steps,lang):
    by_step={s["instruction_id"]:s["original_text"] for s in steps}
    used=[]
    for r in actions:
        lemma=normalize(r)
        phrase=by_step[r["instruction_id"]]
        before=phrase[:int(r["character_start"])]
        after=phrase[int(r["character_end"]):]
                                                                               
        near=before[-80:]+" "+r["surface_text"]+" "+after[:80]
        suspected_noun=(lang=="en" and
            (r["surface_text"].lower() in {"peel","cutting","browned","brown","beaten","melted"} and
             (NEGATIVE[lang].search(phrase) or r["surface_text"].lower() in {"browned","brown","beaten","melted"})))
        if lang=="en" and r["surface_text"].lower()=="slices" and re.search(r"\b(?:thin|thick|into|of|the)\s+$",before,re.I):
            suspected_noun=True
        eligible=(r["semantic_domain"]=="cutting" and lemma not in NON_GEOMETRIC
                  and lemma not in {"peel","éplucher","peler","schälen","abschälen"}
                  and not suspected_noun)
        cue=bool(eligible and CUT_CUE[lang].search(near))
        used.append({**r,"normalized_lemma":lemma,"eligible_cutting":eligible,"explicit_geometry_heuristic":cue,
                     "potential_noun_state":bool(suspected_noun),"nearby_cue":CUT_CUE[lang].search(near).group(0) if cue else ""})
                                                                             
                                                                                 
    groups={s["instruction_id"]:[] for s in steps}
    for x in used:groups[x["instruction_id"]].append(x)
    for sid,group in groups.items():
        phrase=by_step[sid]
        cues=list(CUT_CUE[lang].finditer(phrase))
        heads=[x for x in group if x["eligible_cutting"]]
        owners={}
        for cue in cues:
            if not heads:continue
            center=(cue.start()+cue.end())/2
            owner=min(heads,key=lambda x:abs(center-(int(x["character_start"])+int(x["character_end"]))/2))
            if abs(center-int(owner["character_start"]))<=85:
                owners.setdefault(id(owner),[]).append(cue.group(0))
        for x in group:
            matched=owners.get(id(x),[])
            x["explicit_geometry_heuristic"]=bool(matched)
            x["nearby_cue"]=matched[0] if matched else ""
    return used


def write_csv(path,rows):
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    frame,pages=load_pages()
    inventory=[];all_tokens=[]
    for (lang,title),(rank,source_id) in frame.items():
        page=pages[(lang,title)]
        rid=f"B{lang.upper()}-{rank:03d}"
        row={"recipe_id":rid,"language":lang,"category_rank":rank,"title":title,"category_page_id":source_id,
             "status":"","reason":"","source_file":"","source_url":f"https://{lang}.wikibooks.org/wiki/{title.replace(' ','_')}",
             "revision_id":"","body_lines":0,"method_segments":0,"candidate_tokens":0,
             "cutting_eligible_A":0,"cutting_cues_E":0,"neutral_only":False,"G_half":None,
             "I4":None,"I3":None,"distinct_action_types":0,"type_density":None,
             "is_drink":bool(re.search(r"(\btea\b|Boissons|cocktail|vin chaud|Hypocras|punch|limonade)",title,re.I)),
             "is_compilation":bool(re.search(r"(?:Recettes\s+(?:auvergnate|de la Provence|franc-comtoise)|Druckversion)",title,re.I)),
             "is_country_category":True}
        if page is None:
            row.update(status="source_unavailable",reason="no matching titled page with page revision could be captured")
            inventory.append(row);continue
        row["source_file"]=page["source_file"]
        row["source_url"]=page.get("source_url",row["source_url"])
        row["revision_id"]=page.get("observed_revid") or page.get("observed_revision_id") or ""
        if row["is_compilation"]:
            row.update(status="excluded_article_compilation",reason="entire page is a multi-recipe index or book compilation")
            inventory.append(row);continue
        lines=body(page);row["body_lines"]=len(lines)
        if not lines:
            row.update(status="excluded_article_empty",reason="page has no available body text")
            inventory.append(row);continue
        normalized={**page,"candidate_id":rid,"source_url":row["source_url"],"observed_revid":row["revision_id"],
                    "capture_complete":True,"lines":lines}
        _,steps,note=parse_page(normalized)
        row["method_segments"]=len(steps)
        if not steps:
            row.update(status="excluded_article_no_method",reason="no cooking instruction extracted from full page")
            inventory.append(row);continue
        extracted,_=extract(steps,True)
        tokens=coding(extracted,steps,lang)
        row["candidate_tokens"]=len(tokens)
        row["cutting_eligible_A"]=sum(x["eligible_cutting"] for x in tokens)
        row["cutting_cues_E"]=sum(x["explicit_geometry_heuristic"] for x in tokens)
        row["neutral_only"]=row["cutting_eligible_A"]==0
        row["G_half"]=(row["cutting_cues_E"]+.5)/(row["cutting_eligible_A"]+1)
        keys=[x["semantic_domain"]+":"+x["normalized_lemma"] for x in tokens]
        row["I4"]=pilot_index(keys,4)
        row["I3"]=pilot_index(keys,3)
        row["distinct_action_types"]=len(set(keys))
        row["type_density"]=(len(set(keys))/len(keys)) if keys else None
        row.update(status="included",reason=note)
        for t in tokens:
            all_tokens.append({"recipe_id":rid,"language":lang,"instruction_id":t["instruction_id"],
                               "source_line":t["source_line"],"semantic_domain":t["semantic_domain"],
                               "surface_text":t["surface_text"],"normalized_lemma":t["normalized_lemma"],
                               "eligible_cutting":t["eligible_cutting"],"explicit_geometry_heuristic":t["explicit_geometry_heuristic"],
                               "nearby_cue":t["nearby_cue"],"potential_noun_state":t["potential_noun_state"]})
        inventory.append(row)
    assert len(inventory)==150
    write_csv(OUT/"article_inventory.csv",inventory)
    if all_tokens:write_csv(OUT/"automated_action_candidates.csv",all_tokens)
    print(json.dumps({"articles":len(inventory),"by_status":dict(Counter(x["status"] for x in inventory)),
                      "included_by_language":dict(Counter(x["language"] for x in inventory if x["status"]=="included")),
                      "candidates":len(all_tokens),"eligible_cutting":sum(x["cutting_eligible_A"] for x in inventory),
                      "cues":sum(x["cutting_cues_E"] for x in inventory)},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
