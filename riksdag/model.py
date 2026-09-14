"""Monte Carlo forecast of the final Riksdag seat distribution from a partial count.

What is still unknown on election night, and how it is modelled:

1. Unreported ordinary districts (a handful). Each gets its 2022 result, scaled by the
   constituency's 2022 -> 2026 swing measured on the districts already counted, and is
   drawn as a multinomial.
2. The collection districts (uppsamlingsdistrikt): late early votes, votes from abroad
   and votes cast outside the home municipality, counted from the Wednesday after the
   election. They were 3.4 % of all votes in 2022 and vote differently from the polling
   stations (in 2022: S 26.6 % against 30.5 %, V 9.1 % against 6.7 %, ...). Their size per
   constituency is the 2022 size scaled by the constituency's growth in counted votes,
   with lognormal uncertainty; their party split is the 2022 split per constituency
   moved by the constituency swing, with a correlated national perturbation and
   constituency-level Dirichlet noise, then a multinomial draw.
3. The final count (slutlig rösträkning) re-counts everything; in 2022 it moved party
   shares by at most 0.02 percentage points. A small lognormal jitter stands in for it.

Every draw is then run through the statutory seat allocation.
"""
from __future__ import annotations

import json
from collections import Counter

import numpy as np

from .data import MAIN_PARTIES, OTHER, Snapshot
from .seats import allocate

DEFAULT_CONFIG = {
    "draws": 4000,
    "seed": None,
    "collection_size_sigma_national": 0.10,   # lognormal sd on the size of the late count, shared
    "collection_size_sigma_local": 0.06,      # ... and per constituency
    "collection_share_sigma_national": 0.08,  # lognormal sd on each party's late-vote share, shared
    "collection_share_concentration": 300,    # Dirichlet concentration per constituency
    "recount_sigma": 0.002,                   # lognormal jitter for the final count
    "blocs": {"left": ["S", "V", "C", "MP"], "right": ["M", "SD", "KD", "L"]},
    "majority": 175,
}


def _shares(c: Counter, parties: list[str]) -> np.ndarray:
    v = np.array([float(c.get(p, 0)) for p in parties])
    s = v.sum()
    return v / s if s > 0 else np.full(len(parties), 1.0 / len(parties))


def simulate(snap: Snapshot, prior: dict, config: dict | None = None) -> dict:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    rng = np.random.default_rng(cfg["seed"])
    parties = MAIN_PARTIES + [OTHER]
    P = len(parties)
    codes = sorted(snap.constituencies)
    fixed_seats = {k: snap.constituencies[k].fixed_seats for k in codes}

    # per-constituency ingredients
    base, swing, coll_size, coll_share, pending_frac, uncounted = {}, {}, {}, {}, {}, {}
    for k in codes:
        c = snap.constituencies[k]
        counted = np.array([float(c.counted_votes.get(p, 0)) for p in parties])
        base[k] = counted + np.array([float(c.collection_counted.get(p, 0)) for p in parties])
        normal22 = Counter(prior["normal"].get(k, {}))
        coll22 = Counter(prior["collection"].get(k, {}))
        s26 = _shares(c.counted_votes, parties)
        s22 = _shares(normal22, parties)
        with np.errstate(divide="ignore", invalid="ignore"):
            sw = np.where(s22 > 0, s26 / s22, 1.0)
        swing[k] = sw
        growth = counted.sum() / max(1.0, sum(normal22.values()))
        coll_size[k] = sum(coll22.values()) * growth
        sh = _shares(coll22, parties) * sw
        coll_share[k] = sh / sh.sum()
        n_coll = c.collection_pending + (1 if c.collection_counted else 0)
        pending_frac[k] = c.collection_pending / n_coll if n_coll else 0.0
        # unreported ordinary districts
        rows = []
        for d in c.uncounted:
            prev = prior["districts"].get(d["valdistriktskod"])
            if prev:
                pv = np.array([float(prev["votes"].get(p, 0)) for p in parties])
                total = pv.sum() * growth
                sh = pv / pv.sum() * sw if pv.sum() > 0 else s26
            else:
                total = (d.get("antalRostberattigade") or 1000) * 0.8
                sh = s26
            rows.append((total, sh / sh.sum()))
        uncounted[k] = rows

    # Monte Carlo
    seat_draws = np.zeros((cfg["draws"], P - 1), dtype=int)
    late_draws = np.zeros((cfg["draws"], P))
    krets_seats: dict[str, list[Counter]] = {k: [] for k in codes}
    for i in range(cfg["draws"]):
        size_nat = np.exp(rng.normal(0, cfg["collection_size_sigma_national"]))
        share_nat = np.exp(rng.normal(0, cfg["collection_share_sigma_national"], P))
        votes = {}
        late_total = np.zeros(P)
        for k in codes:
            v = base[k].copy()
            for total, sh in uncounted[k]:
                v += rng.multinomial(int(round(total)), sh)
            if pending_frac[k] > 0:
                n = coll_size[k] * pending_frac[k] * size_nat * np.exp(rng.normal(0, cfg["collection_size_sigma_local"]))
                sh = coll_share[k] * share_nat
                sh = rng.dirichlet(np.maximum(sh / sh.sum() * cfg["collection_share_concentration"], 1e-3))
                late = rng.multinomial(int(round(n)), sh)
                v += late
                late_total += late
            v = v * np.exp(rng.normal(0, cfg["recount_sigma"], P))
            votes[k] = {p: float(v[j]) for j, p in enumerate(parties) if p != OTHER}
            votes[k][OTHER] = float(v[-1])   # below-threshold votes count toward the 4 % base
        # 'other' parties never win seats but dilute the national threshold base
        alloc = allocate({k: {p: x for p, x in kv.items()} for k, kv in votes.items()}, fixed_seats)
        seat_draws[i] = [alloc.national.get(p, 0) for p in MAIN_PARTIES]
        late_draws[i] = late_total
        for k, tab in alloc.by_constituency().items():
            krets_seats[k].append(Counter(tab))

    blocs = cfg["blocs"]
    idx = {p: j for j, p in enumerate(MAIN_PARTIES)}
    left = seat_draws[:, [idx[p] for p in blocs["left"]]].sum(axis=1)
    right = seat_draws[:, [idx[p] for p in blocs["right"]]].sum(axis=1)
    maj = cfg["majority"]

    def summary(col):
        q = np.percentile(col, [5, 25, 50, 75, 95])
        return {"mean": float(col.mean()), "p5": int(q[0]), "p25": int(q[1]), "median": int(q[2]), "p75": int(q[3]), "p95": int(q[4])}

    seat_hist = {p: {int(v): int(n) for v, n in zip(*np.unique(seat_draws[:, idx[p]], return_counts=True))} for p in MAIN_PARTIES}
    left_hist = {int(v): int(n) for v, n in zip(*np.unique(left, return_counts=True))}
    krets_summary = {}
    for k in codes:
        agg: Counter = Counter()
        for tab in krets_seats[k]:
            agg.update(tab)
        krets_summary[k] = {p: round(agg[p] / cfg["draws"], 2) for p in MAIN_PARTIES if agg[p]}

    return {
        "draws": cfg["draws"],
        "config": {kk: vv for kk, vv in cfg.items() if kk != "seed"},
        "p_left_majority": float((left >= maj).mean()),
        "p_right_majority": float((right >= maj).mean()),
        "left_seats": summary(left),
        "right_seats": summary(right),
        "left_hist": left_hist,
        "seats": {p: summary(seat_draws[:, idx[p]]) for p in MAIN_PARTIES},
        "seat_hist": seat_hist,
        "p_below_threshold": {p: float((seat_draws[:, idx[p]] == 0).mean()) for p in MAIN_PARTIES},
        "expected_late_votes": {p: float(late_draws[:, j].mean()) for j, p in enumerate(parties)},
        "expected_late_total": float(late_draws.sum(axis=1).mean()),
        "constituency_expected_seats": krets_summary,
    }
