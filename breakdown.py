# breakdown.py  ───────────────────────────────────────────────────────
import pandas as pd
from family_dataclass import family_obj
from city_health import city_health_monthly
from living_wage import (
    category_quantile,
    family_types,
    gross_from_net,
    housing_quantile,     # ← NEW
    bedrooms_required,    # ← NEW
    food_cost,
    transport_cost,
    civic_cost,
    other_cost,
    internet_cost
)

def living_wage_breakdown(q: float = 0.5,
                          include_tax: bool = True,
                          filing_status: str = "single") -> pd.DataFrame:
    """
    Per-family monthly costs by category, + TAX and TOTAL.
    Now uses the bedroom-specific rent distributions.
    """
    base = category_quantile(q)            # everything except housing
    rows = []

    for label, (adults, children, earners) in family_types.items():
        # ── bedroom-specific rent ───────────────────────────────────────
        fam = family_obj(adults, children, earners)
        br   = bedrooms_required(adults, children)
        housing = housing_quantile(q, br)

        # ----- this is the ONLY line that changed -------------
        health = city_health_monthly(fam)

        # ── remaining cost buckets ─────────────────────────────────────
        transport = transport_cost(base["transport"], earners, children)
        food      = food_cost(base["food"], adults, children)
        civic     = civic_cost(base["civic"],  adults, children)   # ← NEW
        other     = other_cost(base["other"],  adults, children)   # ← NEW
        care      = care = 0 if (adults == 2 and earners == 1) else base["childcare"] * children
        internet  = internet_cost(base["internet"], adults)        # ← NEW

        monthly_net = (housing + transport + food + health +
                       civic + other + care + internet)

        # ── taxes (optional) ───────────────────────────────────────────
        # --- replace the IF‑block that adds TAX --------------------------------
        if include_tax:
            filing = ("married" if adults == 2               # MFJ
                    else "hoh"  if children > 0            # Head‑of‑Household
                    else "single")

            annual_gross, _ = gross_from_net(
                monthly_net * 12,
                filing=filing,
                children=children,
                earners=earners
            )
            tax_monthly = annual_gross / 12 - monthly_net
        else:
            tax_monthly = 0.0

        total = monthly_net + tax_monthly

        rows.append({
            "Family Type": label,
            # "Bedrooms":        br,
            "housing":         round(housing,   0),
            "transport":       round(transport, 0),
            "food":            round(food,      0),
            "health":          round(health,    0),
            "civic":           round(civic,     0),
            "other":           round(other,     0),
            "childcare":       round(care,      0),
            "internet":        round(internet,  0),
            "TAX":             round(tax_monthly, 0),
            "TOTAL":           round(total,     0),
        })

    return (pd.DataFrame(rows)
              .set_index("Family Type")
              .sort_index())
