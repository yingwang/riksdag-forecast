"""Seat allocation for the Swedish Riksdag (vallagen 14 kap., rules in force since 2018).

310 fixed seats are distributed inside the 29 constituencies with the adjusted odd-number
method (first divisor 1.2, then 3, 5, 7 ...). Parties need 4 % nationally, or 12 % in the
constituency, to take part there. The 349 seats are then distributed nationally among the
parties above 4 % as if the country were one constituency. A party holding more fixed
seats than its national entitlement loses the surplus, seat by seat, in the constituency
where its comparison number for the last seat is lowest; each freed seat goes to the next
party in that constituency. Finally the 39 levelling seats (plus any freed ones) top the
under-represented parties up to their entitlement, one at a time, in the constituency where
the party's comparison number is highest.
"""
from __future__ import annotations

from dataclasses import dataclass, field

FIRST_DIVISOR = 1.2
NATIONAL_THRESHOLD = 0.04
CONSTITUENCY_THRESHOLD = 0.12
TOTAL_SEATS = 349


def comparison(votes: float, seats: int) -> float:
    """Comparison number for the next seat of a party that already holds `seats`."""
    return votes / (FIRST_DIVISOR if seats == 0 else 2 * seats + 1)


def sainte_lague(votes: dict[str, float], seats: int, initial: dict[str, int] | None = None) -> dict[str, int]:
    """Distribute `seats` seats by the adjusted odd-number method. Ties go to the larger vote."""
    won = {p: (initial or {}).get(p, 0) for p in votes}
    for _ in range(seats):
        best = max(votes, key=lambda p: (comparison(votes[p], won[p]), votes[p]))
        won[best] += 1
    return won


@dataclass
class Allocation:
    national: dict[str, int]
    fixed: dict[str, dict[str, int]]          # constituency -> party -> fixed seats (after surplus removal)
    levelling: dict[str, dict[str, int]]      # constituency -> party -> levelling seats
    eligible: set[str] = field(default_factory=set)

    def by_constituency(self) -> dict[str, dict[str, int]]:
        out = {}
        for k in self.fixed:
            out[k] = {p: self.fixed[k].get(p, 0) + self.levelling[k].get(p, 0) for p in set(self.fixed[k]) | set(self.levelling[k])}
            out[k] = {p: n for p, n in out[k].items() if n}
        return out


def allocate(votes: dict[str, dict[str, float]], fixed_seats: dict[str, int]) -> Allocation:
    """votes: constituency -> party -> votes (all parties, including ones below threshold).
    fixed_seats: constituency -> number of fixed seats."""
    national_votes: dict[str, float] = {}
    for k in votes:
        for p, v in votes[k].items():
            national_votes[p] = national_votes.get(p, 0) + v
    total = sum(national_votes.values())
    national_parties = {p for p, v in national_votes.items() if v / total >= NATIONAL_THRESHOLD}

    # 1. fixed seats inside each constituency
    fixed: dict[str, dict[str, int]] = {}
    for k, kv in votes.items():
        ktotal = sum(kv.values())
        eligible = {p: v for p, v in kv.items() if p in national_parties or (ktotal and v / ktotal >= CONSTITUENCY_THRESHOLD)}
        fixed[k] = {p: n for p, n in sainte_lague(eligible, fixed_seats[k]).items() if n} if eligible else {}

    # 2. national entitlement among the 4 % parties (seats won by 12 %-only parties are set aside)
    outside = sum(n for k in fixed for p, n in fixed[k].items() if p not in national_parties)
    entitlement = sainte_lague({p: national_votes[p] for p in national_parties}, TOTAL_SEATS - outside)

    # 3. remove surplus fixed seats
    freed = 0
    for p in national_parties:
        while sum(fixed[k].get(p, 0) for k in fixed) > entitlement[p]:
            # the constituency where the party's last seat had the lowest comparison number;
            # constituencies with fewer than three fixed seats are protected (14 kap. 4 a §)
            candidates = [k for k in fixed if fixed[k].get(p, 0) > 0 and fixed_seats[k] >= 3]
            if not candidates:
                break
            worst = min(candidates, key=lambda k: comparison(votes[k][p], fixed[k][p] - 1))
            fixed[worst][p] -= 1
            if fixed[worst][p] == 0:
                del fixed[worst][p]
            # the seat goes to the next party in that constituency
            kv = votes[worst]
            ktotal = sum(kv.values())
            eligible = [q for q in kv if q != p and (q in national_parties or (ktotal and kv[q] / ktotal >= CONSTITUENCY_THRESHOLD))
                        and not (q in national_parties and sum(fixed[kk].get(q, 0) for kk in fixed) >= entitlement.get(q, 0))]
            if eligible:
                nxt = max(eligible, key=lambda q: (comparison(kv[q], fixed[worst].get(q, 0)), kv[q]))
                fixed[worst][nxt] = fixed[worst].get(nxt, 0) + 1
            else:
                freed += 1

    # 4. levelling seats
    levelling: dict[str, dict[str, int]] = {k: {} for k in votes}
    held = {p: sum(fixed[k].get(p, 0) for k in fixed) for p in national_parties}
    remaining = TOTAL_SEATS - outside - sum(held.values())
    for _ in range(remaining):
        under = [p for p in national_parties if held[p] < entitlement[p]]
        if not under:
            break
        best_p, best_k, best_c = None, None, -1.0
        for p in under:
            for k in votes:
                if p not in votes[k]:
                    continue
                # 14 kap. 5 §: where the party holds no fixed seat, the comparison number for
                # its first (levelling) seat is the full vote count, not votes / 1.2
                have = fixed[k].get(p, 0) + levelling[k].get(p, 0)
                c = votes[k][p] if have == 0 else comparison(votes[k][p], have)
                if c > best_c:
                    best_p, best_k, best_c = p, k, c
        levelling[best_k][best_p] = levelling[best_k].get(best_p, 0) + 1
        held[best_p] += 1

    national = {p: held[p] for p in national_parties}
    for k in fixed:
        for p, n in fixed[k].items():
            if p not in national_parties:
                national[p] = national.get(p, 0) + n
    return Allocation(national=national, fixed=fixed, levelling=levelling, eligible=national_parties)
