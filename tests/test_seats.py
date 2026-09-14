"""The allocator must reproduce Valmyndigheten's own seat tables from the same votes."""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from riksdag import seats, data  # noqa: E402

SAMPLES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "samples", "*.zip")))


def check(path):
    snap = data.snapshot_from_zip(open(path, "rb").read())
    alloc = seats.allocate(data.constituency_votes(snap), data.fixed_seats(snap))
    assert alloc.national == {p: n for p, n in snap.official_national.items()}, (path, alloc.national, snap.official_national)
    mine = alloc.by_constituency()
    for code, k in snap.constituencies.items():
        assert mine.get(code, {}) == k.official_seats, (path, code, k.name, mine.get(code), k.official_seats)


def test_samples():
    assert SAMPLES, "no sample zips"
    for path in SAMPLES:
        check(path)


if __name__ == "__main__":
    for path in SAMPLES:
        check(path)
        print("ok", os.path.basename(path))
