"""Readers for Valmyndigheten's result files (resultat.val.se, val2026 format)."""
from __future__ import annotations

import io
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field

MAIN_PARTIES = ["S", "M", "SD", "V", "C", "KD", "MP", "L"]
OTHER = "ÖVR"


def party_votes(district: dict) -> Counter:
    """Valid party votes in one district (or any node with a `rostfordelning`)."""
    out: Counter = Counter()
    rf = district.get("rostfordelning")
    if not rf or not rf.get("rosterPaverkaMandat"):
        return out
    for p in rf["rosterPaverkaMandat"]["partiRoster"]:
        out[p["partiforkortning"] or p["partibeteckning"]] += p["antalRoster"] or 0
    ov = rf["rosterPaverkaMandat"].get("rosterOvrigaPartier") or {}
    out[OTHER] += ov.get("antalRoster") or 0
    return out


def previous_party_votes(district: dict) -> Counter:
    out: Counter = Counter()
    rf = district.get("rostfordelning")
    if not rf or not rf.get("rosterPaverkaMandat"):
        return out
    for p in rf["rosterPaverkaMandat"]["partiRoster"]:
        v = p.get("antalRosterForegaendeVal")
        if isinstance(v, int):
            out[p["partiforkortning"] or p["partibeteckning"]] += v
    ov = rf["rosterPaverkaMandat"].get("rosterOvrigaPartier") or {}
    v = ov.get("antalRosterForegaendeVal")
    if isinstance(v, int):
        out[OTHER] += v
    return out


@dataclass
class Constituency:
    code: str
    name: str
    fixed_seats: int
    eligible: int
    counted_votes: Counter = field(default_factory=Counter)          # normal districts counted so far
    counted_districts: int = 0
    total_districts: int = 0
    uncounted: list = field(default_factory=list)                     # normal districts not yet reported
    collection_counted: Counter = field(default_factory=Counter)      # uppsamlingsdistrikt already reported
    collection_pending: int = 0                                       # uppsamlingsdistrikt not yet reported
    prev_total: int = 0                                               # 2022 constituency total (final)
    prev_votes: Counter = field(default_factory=Counter)              # 2022 constituency party votes (final)
    official_seats: dict = field(default_factory=dict)                # party -> seats in the official allocation


@dataclass
class Snapshot:
    stage: str                     # "preliminär" or "slutlig"
    updated: str
    constituencies: dict           # code -> Constituency
    official_national: dict        # party -> seats
    total_eligible: int
    counted_districts: int
    total_districts: int

    def counted_national(self) -> Counter:
        out: Counter = Counter()
        for k in self.constituencies.values():
            out.update(k.counted_votes)
            out.update(k.collection_counted)
        return out


def read_zip(blob: bytes) -> tuple[dict, dict]:
    """Return (rostfordelning, mandatfordelning) JSON objects from a result zip."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    rost = mand = None
    for name in z.namelist():
        if name.endswith(".json") and "rostfordelning" in name:
            rost = json.loads(z.read(name).decode("utf-8-sig"))
        elif name.endswith(".json") and "mandatfordelning" in name:
            mand = json.loads(z.read(name).decode("utf-8-sig"))
    if rost is None or mand is None:
        raise ValueError("zip lacks rostfordelning or mandatfordelning")
    return rost, mand


def snapshot_from_zip(blob: bytes) -> Snapshot:
    rost, mand = read_zip(blob)
    area = mand["valomrade"]
    ks: dict[str, Constituency] = {}
    for kl in area["valkretsLista"]:
        k = Constituency(code=kl["kod"], name=kl["namnValkrets"], fixed_seats=int(kl["totaltAntalFastaMandat"]),
                         eligible=int(kl["antalRostberattigade"] or 0),
                         prev_total=int(kl["totaltAntalRosterForegaendeVal"] or 0),
                         prev_votes=previous_party_votes(kl),
                         official_seats={p["partiforkortning"]: p["antalMandat"] for p in (kl.get("mandatfordelning") or {}).get("partiLista", [])
                                         if p.get("antalMandat")})
        ks[k.code] = k
    for d in rost["valdistrikt"]:
        k = ks[d["kretskod"]]
        reported = bool(d["rapporteringsTid"])
        if d["valdistriktstyp"] == "uppsamlingsdistrikt":
            if reported:
                k.collection_counted.update(party_votes(d))
            else:
                k.collection_pending += 1
            continue
        k.total_districts += 1
        if reported:
            k.counted_districts += 1
            k.counted_votes.update(party_votes(d))
        else:
            k.uncounted.append(d)
    official = {p["partiforkortning"]: p["antalMandat"] for p in (area.get("mandatfordelning") or {}).get("partiLista", []) if p.get("antalMandat")}
    return Snapshot(stage=rost["rakningstillfalle"], updated=rost["senasteUppdateringstid"], constituencies=ks,
                    official_national=official, total_eligible=int(area["antalRostberattigade"]),
                    counted_districts=int(rost["antalValdistriktRaknade"]), total_districts=int(rost["antalValdistriktSomSkaRaknas"]))


def constituency_votes(snap: Snapshot) -> dict[str, dict[str, float]]:
    """Votes actually counted so far, per constituency and party (input for seats.allocate)."""
    out = {}
    for code, k in snap.constituencies.items():
        v = Counter(k.counted_votes)
        v.update(k.collection_counted)
        v.pop(OTHER, None)
        out[code] = dict(v)
    return out


def fixed_seats(snap: Snapshot) -> dict[str, int]:
    return {code: k.fixed_seats for code, k in snap.constituencies.items()}
