# # taxes.py  ───────────────────────────────────────────────────────────
# from typing import Literal, Tuple

# # 2025 brackets (taxable income = gross - standard_deduction)
# BRACKETS = {
#     "single":  [
#         (0,        0.10),
#         (11_925,   0.12),
#         (48_475,   0.22),
#         (103_350,  0.24),
#         (197_300,  0.32),
#         (250_525,  0.35),
#         (626_350,  0.37),
#     ],
#     "married": [
#         (0,        0.10),
#         (23_850,   0.12),
#         (96_950,   0.22),
#         (206_700,  0.24),
#         (394_600,  0.32),
#         (501_050,  0.35),
#         (751_600,  0.37),
#     ],
# }
# STD_DED = {"single": 15_000, "married": 30_000}

# SS_WAGE_BASE = 176_100
# OASDI_RATE   = 0.062
# MEDIC_RATE   = 0.0145


# def fed_tax(gross: float, filing: Literal["single", "married"]) -> float:
#     taxable = max(0.0, gross - STD_DED[filing])
#     tax = 0.0
#     rates = BRACKETS[filing] + [(float("inf"), BRACKETS[filing][-1][1])]
#     for (lower, rate), (upper, _) in zip(rates, rates[1:]):
#         if taxable > lower:
#             taxed = min(taxable, upper) - lower
#             tax += taxed * rate
#         else:
#             break
#     return tax


# def payroll_tax(gross: float) -> float:
#     ss = min(gross, SS_WAGE_BASE) * OASDI_RATE
#     medic = gross * MEDIC_RATE
#     return ss + medic


# def gross_from_net(target_net: float,
#                    filing: Literal["single", "married"]) -> Tuple[float, float]:
#     """Return (gross_needed, effective_tax_rate)."""
#     lo, hi = target_net, target_net * 2.0         # bracket-free bisection
#     for _ in range(60):                           # enough to reach <1¢ accuracy
#         mid = (lo + hi) / 2
#         net = mid - fed_tax(mid, filing) - payroll_tax(mid)
#         if net < target_net:
#             lo = mid
#         else:
#             hi = mid
#     gross = hi
#     eff_rate = 1 - target_net / gross
#     return gross, eff_rate

# ────────────────────────────────────────────────────────────────────
# taxes.py   (2025 rules + children‑aware gross‑up helper)
# ────────────────────────────────────────────────────────────────────
from typing import Literal, Tuple

# 2025 standard deductions
STD_DED = {
    "single": 15_000,
    "married": 30_000,
    "hoh": 22_500,   # Head‑of‑Household
}

# 2025 ordinary‑income brackets
BRACKETS = {
    "single": [
        (0, 0.10), (11_600, 0.12), (47_150, 0.22),
        (100_525, 0.24), (191_950, 0.32),
        (243_725, 0.35), (609_350, 0.37),
    ],
    "married": [
        (0, 0.10), (23_200, 0.12), (94_300, 0.22),
        (201_050, 0.24), (383_900, 0.32),
        (487_450, 0.35), (731_200, 0.37),
    ],
    "hoh": [
        (0, 0.10), (16_550, 0.12), (63_100, 0.22),
        (100_500, 0.24), (191_950, 0.32),
        (243_700, 0.35), (609_350, 0.37),
    ],
}

SS_WAGE_BASE = 176_100
OASDI, MEDIC = 0.062, 0.0145  # FICA rates


# ── helpers ─────────────────────────────────────────────────────────
def _income_tax_liability(taxable: float, schedule) -> float:
    tax = 0.0
    for (lo, rate), (hi, _) in zip(schedule, schedule[1:] + [(float("inf"), 0)]):
        if taxable > lo:
            tax += (min(taxable, hi) - lo) * rate
        else:
            break
    return tax


def child_tax_credit(agi: float, n_children: int, filing: str) -> float:
    """
    Simple 2025 CTC:
    $2 000 per child, phase‑out 5 ¢ per $ over threshold.
    """
    base = 2_000 * n_children
    threshold = 400_000 if filing == "married" else 200_000
    reduction = max(0.0, 0.05 * (agi - threshold))
    return max(0.0, base - reduction)


def payroll_tax(gross: float, earners: int = 1) -> float:
    """
    OASDI cap is applied PER earner.  Medicare has no cap.
    """
    each = gross / earners
    per_earner = min(each, SS_WAGE_BASE) * OASDI + each * MEDIC
    return earners * per_earner


def net_after_tax(gross: float,
                  filing: str,
                  children: int,
                  earners: int) -> float:
    taxable = max(0.0, gross - STD_DED[filing])
    liability = _income_tax_liability(taxable, BRACKETS[filing])
    liability -= child_tax_credit(gross, children, filing)
    fica = payroll_tax(gross, earners)
    return gross - liability - fica


# ── public helper ───────────────────────────────────────────────────
def gross_from_net(target_net: float,
                   filing: Literal["single", "married", "hoh"],
                   children: int = 0,
                   earners: int = 1,
                   tol: float = 0.01) -> Tuple[float, float]:
    """
    Return (gross_income_needed, effective_tax_rate) that yields `target_net`
    after 2025 federal income tax, FICA, and the child tax credit.
    """
    lo, hi = target_net, target_net * 2.5
    for _ in range(80):                # bisection to <1 ¢
        mid = (lo + hi) / 2
        if net_after_tax(mid, filing, children, earners) < target_net:
            lo = mid
        else:
            hi = mid
    eff_rate = 1 - target_net / hi
    return hi, eff_rate
