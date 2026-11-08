import csv
import hashlib
import json
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

def read(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def summarize(articles, domains, languages, condition):
    results = []
    for language in languages:
        for domain in domains:
            group = [r for r in articles if r["language"] == language and r["domain"] == domain and condition(r)]
            values = [float(r["score"]) for r in group]
            if not values:
                raise ValueError((language, domain))
            results.append({"language": language, "domain": domain, "n": len(group),
                            "A_total": sum(int(r["A"]) for r in group),
                            "E_total": sum(int(r["E"]) for r in group),
                            "mean": statistics.mean(values),
                            "sample_sd": statistics.stdev(values) if len(values) > 1 else 0,
                            "standard_error": statistics.stdev(values) / len(values) ** 0.5 if len(values) > 1 else 0})
    return results

def main():
    subprocess.run([sys.executable, str(HERE / "run_all_spacy.py")], cwd=HERE, check=True)
    included = [r for r in read("article_decisions.csv") if r["decision"] == "included"]
    assert len(included) == 130
    counts = defaultdict(lambda: [0, 0])
    for r in read("nlp_cutting_audit.csv"):
        pair = counts[(r["recipe_id"], "cutting")]
        pair[0] += 1
        pair[1] += int(r["E_flag"])
    for r in read("other_actions_audit.csv"):
        pair = counts[(r["recipe_id"], r["domain"])]
        pair[0] += 1
        pair[1] += int(r["has_specificity_cue"])
    articles = []
    for r in included:
        for domain in ("cutting", "heating", "mixing"):
            A, E = counts[(r["recipe_id"], domain)]
            assert 0 <= E <= A
            articles.append({"recipe_id": r["recipe_id"], "language": r["language"],
                             "title": r["title"], "domain": domain, "A": A, "E": E,
                             "score": (E + 1) / (A + 2), "no_action": int(A == 0),
                             "source_url": r["source_url"], "revision_id": r["revision_id"]})
    assert len(articles) == 390
    write("all_domain_article_scores.csv", articles)
    all_summary = summarize(articles, ("cutting", "heating", "mixing"), ("fr", "de", "en"), lambda r: True)
    write("all_domain_country_summary.csv", all_summary)
    poster_articles = [r for r in articles if r["language"] in ("fr", "de") and r["domain"] in ("cutting", "heating") and r["E"] > 0]
    poster_summary = summarize(poster_articles, ("cutting", "heating"), ("fr", "de"), lambda r: True)
    write("poster_fr_de_articles.csv", poster_articles)
    write("poster_fr_de_summary.csv", poster_summary)
    manifest_path = HERE / "nlp_reproduction_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["additional_outputs"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                      for name in ("all_domain_article_scores.csv", "all_domain_country_summary.csv", "poster_fr_de_articles.csv", "poster_fr_de_summary.csv")}
    manifest["poster_definition"] = "France and Germany, cutting and heating, articles with E>0; g=(E+1)/(A+2); article-equal mean, sample SD"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Poster results")
    for r in poster_summary:
        print(r["language"], r["domain"], "n", r["n"], "mean", round(r["mean"], 6), "SD", round(r["sample_sd"], 6))

if __name__ == "__main__":
    main()
