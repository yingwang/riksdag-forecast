"""Score every past run against the certified final result, once it exists."""
from __future__ import annotations

import json
import os

from .data import MAIN_PARTIES, Snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def verify(final: Snapshot, blocs: dict, majority: int = 175) -> str | None:
    if final.counted_districts < final.total_districts or not final.official_national:
        return None
    seats = final.official_national
    left = sum(seats.get(p, 0) for p in blocs["left"]); right = sum(seats.get(p, 0) for p in blocs["right"])
    left_won = left >= majority
    hist_path = os.path.join(ROOT, "forecast", "history.jsonl")
    runs = [json.loads(l) for l in open(hist_path) if l.strip()] if os.path.exists(hist_path) else []
    lines = ["# Verification against the final count", "",
             f"Final count updated {final.updated}: " + ", ".join(f"{p} {seats.get(p, 0)}" for p in MAIN_PARTIES) +
             f" → S+V+C+MP {left}, M+SD+KD+L {right}.", "",
             "| Run | Districts | P(left ≥ 175) | Brier | Left median | Seat MAE |", "|---|---:|---:|---:|---:|---:|"]
    briers = []
    for r in runs:
        p = r["p_left_majority"]; brier = (p - (1.0 if left_won else 0.0)) ** 2; briers.append(brier)
        mae = sum(abs(r["seats_mean"][q] - seats.get(q, 0)) for q in MAIN_PARTIES) / len(MAIN_PARTIES)
        lines.append(f"| {r['generated']} | {r['counted_districts']}/{r['total_districts']} | {100 * p:.1f} % | {brier:.4f} | {r['left_median']} | {mae:.2f} |")
    if briers:
        lines += ["", f"Mean Brier score over {len(briers)} runs: {sum(briers) / len(briers):.4f} (0 is perfect, 0.25 is a coin flip)."]
    text = "\n".join(lines) + "\n"
    open(os.path.join(ROOT, "forecast", "verification.md"), "w").write(text)
    return text
