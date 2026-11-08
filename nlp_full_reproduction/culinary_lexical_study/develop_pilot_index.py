"""Exact small-sample action-lemma diversity and separate feature coverage.

I_m is a proposed descriptive index, not a measure of overall culinary or
national linguistic complexity. The 12 pages were used for rule development.
"""
from __future__ import annotations

import csv
import json
from collections import Counter,defaultdict
from math import comb

from annotate_metric_pilot import DIMS, OUT, ROOT, read, write
from validation_stage4 import frozen


def rarefied_types(keys, m):
    n=len(keys)
    if m<2 or n<m:
        return None
    counts=Counter(keys)
    denominator=comb(n,m)
    return sum(1-(comb(n-c,m)/denominator if n-c>=m else 0) for c in counts.values())


def pilot_index(keys, m):
    r=rarefied_types(keys,m)
    return None if r is None else (r-1)/(m-1)


def key_for(r, collapsed=False):
    return f"{r['semantic_domain']}:{r['collapsed_root_sensitivity'] if collapsed else r['normalized_lemma']}"


def metrics(rows, recipe, language):
    tokens=[x for x in rows if x['recipe_id']==recipe]
    words=[key_for(x) for x in tokens]
    collapsed=[key_for(x,True) for x in tokens]
    conservative=[key_for(x) for x in tokens
                  if not x['semantic_uncertainty'] and x['encoding_type']!="contextual_construction"]
    cutting=[x for x in tokens if x['semantic_domain']=="cutting"]
    applicable=[x for x in cutting if any(x[f"{d}_context_status"]!="not_applicable" for d in DIMS)]
    explicitly=[x for x in applicable if any(x[f"{d}_context_status"]=="explicit" for d in DIMS)]
    lexicalized=[x for x in applicable if any(x[f"{d}_lexical_value"] for d in DIMS)]
    ct=Counter(x['semantic_domain'] for x in tokens)
    return {"recipe_id":recipe,"language":language,"candidate_action_tokens":len(tokens),
        "tentative_domain_cutting":ct['cutting'],"tentative_domain_heating":ct['heating'],
        "tentative_domain_mixing":ct['mixing'],"observed_distinct_lemma_domain_types":len(set(words)),
        "expected_types_at_m4":rarefied_types(words,4),
        "action_lemma_richness_I4":pilot_index(words,4),
        "I3_sample_size_sensitivity":pilot_index(words,3),
        "I4_prefix_collapsing_sensitivity":pilot_index(collapsed,4),
        "tokens_excluding_uncertain_and_contextual":len(conservative),
        "I4_conservative_sensitivity":pilot_index(conservative,4),
        "cutting_tokens_geometry_applicable":len(applicable),
        "cutting_tokens_context_explicit_any_dimension":len(explicitly),
        "cutting_tokens_lexically_coded_any_dimension":len(lexicalized),
        "context_explicit_rate_cutting":len(explicitly)/len(applicable) if applicable else None,
        "lexicalized_rate_cutting":len(lexicalized)/len(applicable) if applicable else None}


def main():
    frozen()
    assert abs(pilot_index(['a']*4,4))<1e-12
    assert abs(pilot_index(['a','b','c','d'],4)-1)<1e-12
    assert abs(rarefied_types(['a','a','b','b'],2)-5/3)<1e-12
    rows=read(OUT / "screened_actions.csv")
    sample=read(ROOT / "stage04/internal/selected_pages.csv")
    assert len(sample)==12 and len(rows)==163
    assert min(Counter(x['recipe_id'] for x in rows).values())==4              
    answer=[metrics(rows,p['recipe_id'],p['language']) for p in sample]
    write(OUT / "pilot_index_by_recipe.csv",answer,list(answer[0]))
    dataset={"index_name":"exploratory_action_lemma_richness_I4",
      "status":"prototype on same 12 selected development pages; no cross-language inference",
      "posthoc_sample_size_m":4,
      "formula":"R_m=Σ_l[1−C(N−n_l,m)/C(N,m)]; I_m=(R_m−1)/(m−1)",
      "candidate_action_tokens":len(rows),
      "recipe_count":len(sample),
      "undefined_rule":"If N<m, I_m is null; contextual feature rate is null if no applicable cutting action",
      "type_key":"semantic domain plus normalized lemma; same lemma repeated counts as a single type",
      "limitations":"AI-coded, sample used to tune extraction, unequal food/task mix, only one Wiki family"}
    (OUT / "pilot_index_manifest.json").write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dataset,ensure_ascii=False,indent=2))
    print("per recipe:")
    for x in answer:
        print(x['recipe_id'],x['candidate_action_tokens'],round(x['action_lemma_richness_I4'],4),
              "context explicit",x['cutting_tokens_context_explicit_any_dimension'],"/",x['cutting_tokens_geometry_applicable'])


if __name__=="__main__":
    main()
