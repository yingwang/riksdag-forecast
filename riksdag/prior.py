"""Build the 2022 prior from Valmyndigheten's 2022 preliminary result file.

The preliminary count of 2022, once complete, contains every district including the
`uppsamlingsdistrikt` (the collection districts holding late early votes, votes from
abroad and votes cast in other municipalities, all counted on the Wednesday after the
election). That is exactly the part of the 2026 count still outstanding on election
night, so 2022 tells us both how large that tail is per constituency and how it votes
compared with the polling-station count.

usage: prior.py <Val_20220911_preliminar_00_RD.zip> <Val_20220911_slutlig_00_RD.zip> <out.json>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

from .data import party_votes, read_zip


def build(prelim_zip: bytes, final_zip: bytes) -> dict:
    rost, _ = read_zip(prelim_zip)
    rost_final, _ = read_zip(final_zip)
    coll: dict[str, Counter] = defaultdict(Counter)
    normal: dict[str, Counter] = defaultdict(Counter)
    districts: dict[str, dict] = {}
    for d in rost["valdistrikt"]:
        pv = party_votes(d)
        if d["valdistriktstyp"] == "uppsamlingsdistrikt":
            coll[d["kretskod"]].update(pv)
        else:
            normal[d["kretskod"]].update(pv)
            districts[d["valdistriktskod"]] = {"krets": d["kretskod"], "votes": dict(pv)}
    prelim_nat: Counter = Counter()
    for c in coll.values():
        prelim_nat.update(c)
    for c in normal.values():
        prelim_nat.update(c)
    final_nat: Counter = Counter()
    for d in rost_final["valdistrikt"]:
        final_nat.update(party_votes(d))
    return {
        "source": "resultat.val.se val2022 preliminär + slutlig, riksdag",
        "collection": {k: dict(v) for k, v in coll.items()},
        "normal": {k: dict(v) for k, v in normal.items()},
        "districts": districts,
        "national_preliminary": dict(prelim_nat),
        "national_final": dict(final_nat),
    }


if __name__ == "__main__":
    prelim, final, out = sys.argv[1:4]
    json.dump(build(open(prelim, "rb").read(), open(final, "rb").read()), open(out, "w"), ensure_ascii=False, separators=(",", ":"))
    print(out)
