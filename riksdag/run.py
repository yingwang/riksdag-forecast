"""One forecast run: fetch, simulate, write forecast/, docs/, README block, history."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

from . import fetch, model, report, verify
from .data import MAIN_PARTIES, OTHER, snapshot_from_zip

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def government_layer(sim: dict, cfg: dict) -> dict:
    """An explicit judgement layer, not a model: given who has 175, who leads the government."""
    pl, pr = sim["p_left_majority"], sim["p_right_majority"]
    g = cfg["government"]
    probs = {
        "Magdalena Andersson (S) leads the government": pl * g["left_majority_andersson"] + pr * g["right_majority_andersson"],
        "Ulf Kristersson (M) leads the government": pr * g["right_majority_kristersson"] + pl * g["left_majority_kristersson"],
    }
    probs["Someone else, or a new election"] = max(0.0, 1.0 - sum(probs.values()))
    return {"probabilities": probs, "note": g["note"]}


def main(argv: list[str]) -> int:
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    prior = json.load(open(os.path.join(ROOT, "data", "prior_2022.json")))
    if len(argv) > 1 and argv[1] != "-":
        blob = open(argv[1], "rb").read(); final_blob = None
    else:
        blobs = fetch.fetch_all(); blob = blobs["preliminar"]; final_blob = blobs["slutlig"]
    snap = snapshot_from_zip(blob)
    final = snapshot_from_zip(final_blob) if final_blob else None
    sim = model.simulate(snap, prior, cfg.get("model"))
    counted = snap.counted_national(); tot = sum(counted.values())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = {
        "generated": now,
        "snapshot": {
            "stage": snap.stage, "updated": snap.updated, "counted_districts": snap.counted_districts,
            "total_districts": snap.total_districts, "counted_votes": tot, "eligible": snap.total_eligible,
            "official_seats": snap.official_national,
            "counted_share": {p: round(100 * counted.get(p, 0) / tot, 2) for p in MAIN_PARTIES + [OTHER]},
            "final_count": {"counted_districts": final.counted_districts, "updated": final.updated, "official_seats": final.official_national} if final else None,
        },
        "forecast": sim,
    }
    out["government"] = government_layer(sim, cfg)
    os.makedirs(os.path.join(ROOT, "forecast"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "forecast", "latest.json"), "w"), indent=1, ensure_ascii=False)
    hist_path = os.path.join(ROOT, "forecast", "history.jsonl")
    entry = {"generated": now, "count_updated": snap.updated, "counted_districts": snap.counted_districts, "total_districts": snap.total_districts,
             "p_left_majority": sim["p_left_majority"], "p_right_majority": sim["p_right_majority"],
             "left_median": sim["left_seats"]["median"], "right_median": sim["right_seats"]["median"],
             "seats_mean": {p: sim["seats"][p]["mean"] for p in MAIN_PARTIES}, "official_seats": snap.official_national,
             "government": out["government"]["probabilities"]}
    with open(hist_path, "a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    history = [json.loads(l) for l in open(hist_path) if l.strip()]
    # keep a compact per-run snapshot of the counted votes (small; the zips are not stored)
    snapdir = os.path.join(ROOT, "data", "snapshots"); os.makedirs(snapdir, exist_ok=True)
    stamp = re.sub(r"[^0-9T]", "", snap.updated)[:15] or now.replace(" ", "T")
    json.dump({"updated": snap.updated, "counted_districts": snap.counted_districts,
               "constituencies": {k: {"counted": dict(c.counted_votes), "collection_counted": dict(c.collection_counted),
                                      "counted_districts": c.counted_districts, "total_districts": c.total_districts,
                                      "collection_pending": c.collection_pending, "official_seats": c.official_seats}
                                  for k, c in snap.constituencies.items()}},
              open(os.path.join(snapdir, f"prelim_{stamp}.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    open(os.path.join(ROOT, "docs", "index.html"), "w").write(report.render_html(out, history))
    readme = os.path.join(ROOT, "README.md")
    if os.path.exists(readme):
        txt = open(readme).read()
        block = "<!-- forecast:start -->\n" + report.readme_block(out) + "\n<!-- forecast:end -->"
        txt = re.sub(r"<!-- forecast:start -->.*?<!-- forecast:end -->", block, txt, flags=re.S) if "<!-- forecast:start -->" in txt else txt + "\n" + block + "\n"
        open(readme, "w").write(txt)
    if final is not None:
        v = verify.verify(final, cfg["model"].get("blocs", model.DEFAULT_CONFIG["blocs"]))
        if v:
            print("final count complete; verification written to forecast/verification.md")
    print(f"{now}: {snap.counted_districts}/{snap.total_districts} districts, P(left>=175)={sim['p_left_majority']:.3f}, "
          f"left median {sim['left_seats']['median']}, right median {sim['right_seats']['median']}, late votes ~{sim['expected_late_total']:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
