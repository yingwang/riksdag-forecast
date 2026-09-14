"""Render forecast/latest.json as docs/index.html and a README block."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .data import MAIN_PARTIES

PARTY_NAMES = {"S": "Socialdemokraterna", "M": "Moderaterna", "SD": "Sverigedemokraterna", "V": "Vänsterpartiet",
               "C": "Centerpartiet", "KD": "Kristdemokraterna", "MP": "Miljöpartiet", "L": "Liberalerna"}
COLORS = {"S": "#E8112d", "M": "#52BDEC", "SD": "#DDDD00", "V": "#DA291C", "C": "#009933", "KD": "#000077", "MP": "#83CF39", "L": "#006AB3"}


def pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def render_html(f: dict, history: list[dict]) -> str:
    snap = f["snapshot"]; sim = f["forecast"]
    left = sim["left_seats"]; right = sim["right_seats"]
    rows = "".join(
        f"<tr><td><span class=sw style='background:{COLORS[p]}'></span>{p}</td><td>{PARTY_NAMES[p]}</td>"
        f"<td class=n>{snap['official_seats'].get(p, 0)}</td><td class=n>{sim['seats'][p]['mean']:.1f}</td>"
        f"<td class=n>{sim['seats'][p]['p5']}–{sim['seats'][p]['p95']}</td>"
        f"<td class=n>{snap['counted_share'].get(p, 0):.2f} %</td><td class=n>{100 * sim['expected_late_votes'][p] / max(1, sim['expected_late_total']):.1f} %</td></tr>"
        for p in MAIN_PARTIES)
    hist = sim["left_hist"]; lo, hi = min(hist), max(hist); mx = max(hist.values())
    bars = "".join(
        f"<div class=bar title='{v} seats: {pct(hist.get(v, 0) / sim['draws'])}'><div class=fill style='height:{100 * hist.get(v, 0) / mx:.0f}%;background:{'#c33' if v >= 175 else '#36c'}'></div><span>{v}</span></div>"
        for v in range(lo, hi + 1))
    trend = "".join(
        f"<tr><td>{h['generated']}</td><td class=n>{h['counted_districts']}/{h['total_districts']}</td><td class=n>{pct(h['p_left_majority'])}</td>"
        f"<td class=n>{h['left_median']}</td><td class=n>{h['right_median']}</td></tr>" for h in history[-40:][::-1])
    gov = f["government"]
    govrows = "".join(f"<tr><td>{html.escape(k)}</td><td class=n>{pct(v)}</td></tr>" for k, v in gov["probabilities"].items())
    return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Riksdag 2026 forecast</title>
<style>
body{{font:15px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}}
h1{{font-size:1.6rem}} h2{{font-size:1.15rem;margin-top:2rem}} table{{border-collapse:collapse;width:100%}} td,th{{padding:.35rem .5rem;border-bottom:1px solid #e5e5e5;text-align:left}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}} .sw{{display:inline-block;width:.8em;height:.8em;border-radius:2px;margin-right:.4em;vertical-align:-1px}}
.big{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}} .card{{flex:1 1 200px;border:1px solid #ddd;border-radius:8px;padding:1rem}} .card b{{font-size:2rem;display:block}}
.hist{{display:flex;align-items:flex-end;gap:2px;height:160px;margin:1rem 0}} .bar{{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;font-size:10px;text-align:center}} .fill{{width:100%}}
small,.muted{{color:#666}} code{{background:#f4f4f4;padding:0 .25em}}
</style>
<h1>Riksdag 2026: what the final count will look like</h1>
<p class=muted>Generated {f['generated']} · data: Valmyndigheten preliminary count updated {snap['updated']}, {snap['counted_districts']} of {snap['total_districts']} districts, {snap['counted_votes']:,} valid party votes · {sim['draws']:,} simulations</p>
<div class=big>
<div class=card><small>S + V + C + MP reach 175</small><b>{pct(sim['p_left_majority'])}</b><small>median {left['median']} seats, 90 % range {left['p5']}–{left['p95']}</small></div>
<div class=card><small>M + SD + KD + L reach 175</small><b>{pct(sim['p_right_majority'])}</b><small>median {right['median']} seats, 90 % range {right['p5']}–{right['p95']}</small></div>
<div class=card><small>Votes still to be counted (expected)</small><b>{sim['expected_late_total']:,.0f}</b><small>collection districts, counted from Wednesday</small></div>
</div>
<h2>Seats for S + V + C + MP across the simulations</h2>
<div class=hist>{bars}</div>
<h2>Parties</h2>
<table><tr><th></th><th></th><th class=n>Seats now (official preliminary)</th><th class=n>Forecast mean</th><th class=n>90 % range</th><th class=n>Share counted</th><th class=n>Share of late votes (exp.)</th></tr>{rows}</table>
<h2>Who becomes prime minister</h2>
<p class=muted>{html.escape(gov['note'])}</p>
<table>{govrows}</table>
<h2>Runs so far</h2>
<table><tr><th>Generated</th><th class=n>Districts</th><th class=n>P(S+V+C+MP ≥ 175)</th><th class=n>Left median</th><th class=n>Right median</th></tr>{trend}</table>
<h2>Method</h2>
<p>Every run downloads Valmyndigheten's result files, takes the votes already counted as given, and simulates the rest: the few unreported polling districts from their 2022 result moved by the local swing, and the collection districts (late early votes, votes from abroad, votes cast in another municipality, all counted from Wednesday) from their 2022 size and party mix per constituency, moved by the local swing, with correlated uncertainty on both size and mix. Each simulated national result goes through the statutory allocation (vallagen 14 kap.: 310 fixed seats by the adjusted odd-number method with first divisor 1.2, the 4 % and 12 % thresholds, surplus return, 39 levelling seats). The allocator reproduces Valmyndigheten's own seat tables for all 29 constituencies from the same votes. Code and every run's numbers: <a href="https://github.com/yingwang/riksdag-forecast">github.com/yingwang/riksdag-forecast</a>.</p>
</html>"""


def readme_block(f: dict) -> str:
    snap = f["snapshot"]; sim = f["forecast"]
    lines = [f"**Latest run** {f['generated']} · count updated {snap['updated']} · {snap['counted_districts']}/{snap['total_districts']} districts",
             "",
             f"- P(S + V + C + MP ≥ 175) = **{pct(sim['p_left_majority'])}** (median {sim['left_seats']['median']}, 90 % range {sim['left_seats']['p5']}–{sim['left_seats']['p95']})",
             f"- P(M + SD + KD + L ≥ 175) = **{pct(sim['p_right_majority'])}** (median {sim['right_seats']['median']}, 90 % range {sim['right_seats']['p5']}–{sim['right_seats']['p95']})",
             f"- Expected votes still to count: {sim['expected_late_total']:,.0f}",
             "",
             "| Party | Seats now | Forecast mean | 90 % range |", "|---|---:|---:|---:|"]
    for p in MAIN_PARTIES:
        s = sim["seats"][p]
        lines.append(f"| {p} | {snap['official_seats'].get(p, 0)} | {s['mean']:.1f} | {s['p5']}–{s['p95']} |")
    return "\n".join(lines)
