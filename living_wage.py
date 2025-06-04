# import numpy as np, pandas as pd
# from taxes import gross_from_net
# from family_dataclass import family_obj
# from city_health import city_health_monthly

# # -------------------------------------------------------------------
# # 1 ▪︎ Cost distributions  (10 000 random draws each, monthly $)
# # -------------------------------------------------------------------
# rng = np.random.default_rng(seed=42)

# transport_monthly  = rng.normal((113.86 + 121.3 + 122.66 + 100.17), 150, 10_000) # gas, insurance, maintenance, car loan
# food_monthly       = rng.normal(382.5, 140, 10_000) # avg (at home)
# health_monthly     = rng.normal((33.33 + 11.67 + 66.33), 50, 10_000) # avg
# civic_monthly      = rng.normal(215,  150, 10_000) # avg
# other_monthly      = rng.normal(314,  100, 10_000) # avg
# childcare_monthly  = rng.normal(889,  200, 10_000) # avg
# internet_monthly   = rng.normal(100,   30, 10_000) # avg

# # three distinct rent distributions
# housing_1br = rng.normal(1530, 250, 10_000) # avg price * 1.2 to account for util and stuff
# housing_2br = rng.normal(1830, 275, 10_000)
# housing_3br = rng.normal(2220, 300, 10_000)

# def housing_quantile(q: float, bedrooms: int) -> float:
#     """Return the q-quantile rent for the requested bedroom count."""
#     arr = {1: housing_1br, 2: housing_2br, 3: housing_3br}[bedrooms]
#     return float(np.quantile(arr, q))

# # -------------------------------------------------------------------
# # 2 ▪︎ Helper for some categories
# # -------------------------------------------------------------------
# def food_cost(base_single: float, adults: int, children: int) -> float:
#     """
#     base_single  = cost draw for *one* adult (≈ $300 at q=0.50).
#     Returns total monthly food cost for the household.
#     """
#     adult_factor  = 1 + 0.8 * max(adults - 1, 0)   # 1st adult full, 2nd 80%
#     child_factor  = 0.6 * children                 # each child @ 60 %
#     return base_single * (adult_factor + child_factor)

# def transport_cost(base_single: float,
#                    working_adults: int,
#                    children: int) -> float:
#     """
#     • `base_single` = monthly draw for one adult / one car.
#     • A second working adult usually means a second vehicle, but
#       not quite 100 % extra cost (shared trips, insurance bundling, etc.).
#       → assume 80 % of the first-vehicle cost.
#     • Children don’t add a whole car, but they do add miles (school, activities).
#       → assume +10 % extra mileage per child (applied to the *gas* part).
#     The helper scales the *entire* base cost for simplicity.
#     """
#     vehicle_factor  = 1 + 0.9 * max(working_adults - 1, 0)   # extra car(s)
#     mileage_factor  = 1 + 0.10 * children                    # extra driving
#     return base_single * vehicle_factor * mileage_factor

# def civic_cost(base_single: float,
#                adults: int,
#                children: int) -> float:
#     """
#     • One adult incurs the full baseline civic/rec‑type cost
#       (PTA dues, club fees, worship tithes, sports leagues…).
#     • Extra adults add 50 % of that baseline (shared memberships, bundled fees).
#     • Each child adds 30 % (youth sports, scouts, after‑school activities).
#     """
#     return base_single * (1 + 0.5 * max(adults - 1, 0) + 0.3 * children)

# def other_cost(base_single: float,
#                adults: int,
#                children: int) -> float:
#     """
#     “Other” = clothes, personal care, furnishings, small appliances, misc.
#     • 100 % for the first adult
#     • +75 % for each additional adult (clothes sizes differ, separate toiletries)
#     • +50 % for each child (lower unit cost, lots of hand‑me‑downs, but rapid growth)
#     """
#     return base_single * (1 + 0.75 * max(adults - 1, 0) + 0.5 * children)

# def internet_cost(base_single: float, adults: int) -> float:
#     """
#     Household internet / mobile plan:
#     • First adult pays 100 % of the baseline.
#     • If there’s a second adult, add 40 % (extra mobile line, higher data cap, etc.).
#       Children are assumed to share the existing bandwidth / family plan.
#     """
#     return base_single * (1 + 0.40 * max(adults - 1, 0))

# def bedrooms_required(adults: int, children: int) -> int:
#     """Rule requested by user (1 BR, 2 BR, or 3 BR)."""
#     if children == 0:
#         return 1
#     if children <= 2:
#         return 2
#     return 3

# def category_quantile(q: float) -> dict:
#     return {
#         "transport":   np.quantile(transport_monthly, q),
#         "food":        np.quantile(food_monthly,      q),
#         "health":      np.quantile(health_monthly,    q),
#         "civic":       np.quantile(civic_monthly,     q),
#         "other":       np.quantile(other_monthly,     q),
#         "childcare":   np.quantile(childcare_monthly, q),
#         "internet":    np.quantile(internet_monthly,  q)
#     }

# # -------------------------------------------------------------------
# # 3 ▪︎ Family archetypes  (adults, children, earners)
# # -------------------------------------------------------------------
# family_types = {
#     "1 Adult":                        (1, 0, 1),
#     "1 Adult 1 Child":                (1, 1, 1),
#     "1 Adult 2 Children":             (1, 2, 1),
#     "1 Adult 3 Children":             (1, 3, 1),
#     "2 Adults (1 Working)":           (2, 0, 1),
#     "2 Adults (1 Working) 1 Child":   (2, 1, 1),
#     "2 Adults (1 Working) 2 Children":(2, 2, 1),
#     "2 Adults (1 Working) 3 Children":(2, 3, 1),
#     "2 Adults (2 Working)":           (2, 0, 2),
#     "2 Adults (2 Working) 1 Child":   (2, 1, 2),
#     "2 Adults (2 Working) 2 Children":(2, 2, 2),
#     "2 Adults (2 Working) 3 Children":(2, 3, 2),
# }

# # -------------------------------------------------------------------
# # 4 ▪︎ Living-wage table
# # -------------------------------------------------------------------
# def living_wage_table(q: float = 0.5,
#                       include_tax: bool = True,
#                       filing_status: str = "single") -> pd.DataFrame:

#     base = category_quantile(q)              # everything but rent
#     rows = []
#     for label, (adults, children, earners) in family_types.items():
#         # ── bedroom-specific rent ───────────────────────────────────────
#         fam = family_obj(adults, children, earners)
#         br   = bedrooms_required(adults, children)
#         housing = housing_quantile(q, br)

#         # ── remaining cost buckets ─────────────────────────────────────
#         health    = city_health_monthly(fam)
#         transport = transport_cost(base["transport"], earners, children)
#         food      = food_cost(base["food"], adults, children)
#         civic     = civic_cost(base["civic"],  adults, children)   # ← NEW
#         other     = other_cost(base["other"],  adults, children)   # ← NEW
#         care      = care = 0 if (adults == 2 and earners == 1) else base["childcare"] * children
#         internet  = internet_cost(base["internet"], adults)        # ← NEW

#         monthly_net = (housing 
#                        + transport 
#                        + food 
#                        + health 
#                        + civic 
#                        + other 
#                        + care 
#                        + internet)

#         # gross-up for tax if desired
#         if include_tax:
#             gross, _ = gross_from_net(monthly_net * 12,
#                                       "single" if earners == 1 else filing_status)
#         else:
#             gross = monthly_net * 12

#         hourly = gross / (2080 * max(earners, 1))

#         rows.append({
#             "Family Type": label,
#             "Bedrooms": br,
#             "Monthly Net ($)":   round(monthly_net, 0),
#             "Monthly Gross ($)": round(gross / 12, 0),
#             "Annual Gross ($)":  round(gross, 0),
#             "Living Wage ($/hr)": round(hourly, 2),
#         })

#     return (pd.DataFrame(rows).set_index("Family Type").sort_index())


# ────────────────────────────────────────────────────────────────────
# living_wage.py   (spending model + updated gross‑up)
# ────────────────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
from taxes import gross_from_net            # ← NEW signature!
from family_dataclass import family_obj      # unchanged
from city_health import city_health_monthly  # unchanged


# -------------------------------------------------------------------
# 1 ▪︎ Monthly cost distributions  (10 000 draws each)
# -------------------------------------------------------------------
rng = np.random.default_rng(seed=42)

transport_monthly = rng.normal((113.86 + 121.3 + 122.66 + 100.17), 150, 10_000)
food_monthly      = rng.normal(382.5, 140, 10_000)
health_monthly    = rng.normal((33.33 + 11.67 + 66.33), 50, 10_000)
civic_monthly     = rng.normal(215, 150, 10_000)
other_monthly     = rng.normal(314, 100, 10_000)
childcare_monthly = rng.normal(889, 200, 10_000)
internet_monthly  = rng.normal(100, 30, 10_000)

housing_1br = rng.normal(1530, 250, 10_000)
housing_2br = rng.normal(1830, 275, 10_000)
housing_3br = rng.normal(2220, 300, 10_000)

def housing_quantile(q: float, bedrooms: int) -> float:
    arr = {1: housing_1br, 2: housing_2br, 3: housing_3br}[bedrooms]
    return float(np.quantile(arr, q))


# -------------------------------------------------------------------
# 2 ▪︎ Scaling helpers
# -------------------------------------------------------------------
def food_cost(base, adults, children):
    return base * (1 + 0.8 * max(adults - 1, 0) + 0.6 * children)

def transport_cost(base, earners, children):
    return base * (1 + 0.9 * max(earners - 1, 0)) * (1 + 0.10 * children)

def civic_cost(base, adults, children):
    return base * (1 + 0.5 * max(adults - 1, 0) + 0.3 * children)

def other_cost(base, adults, children):
    return base * (1 + 0.75 * max(adults - 1, 0) + 0.5 * children)

def internet_cost(base, adults):
    return base * (1 + 0.40 * max(adults - 1, 0))

def bedrooms_required(adults, children):
    if children == 0:
        return 1
    if children <= 2:
        return 2
    return 3

def category_quantile(q):
    return {
        "transport":  np.quantile(transport_monthly, q),
        "food":       np.quantile(food_monthly,      q),
        "health":     np.quantile(health_monthly,    q),
        "civic":      np.quantile(civic_monthly,     q),
        "other":      np.quantile(other_monthly,     q),
        "childcare":  np.quantile(childcare_monthly, q),
        "internet":   np.quantile(internet_monthly,  q),
    }


# -------------------------------------------------------------------
# 3 ▪︎ Family archetypes  (adults, children, earners)
# -------------------------------------------------------------------
family_types = {
    "1 Adult":                         (1, 0, 1),
    "1 Adult 1 Child":                 (1, 1, 1),
    "1 Adult 2 Children":              (1, 2, 1),
    "1 Adult 3 Children":              (1, 3, 1),
    "2 Adults (1 Working)":            (2, 0, 1),
    "2 Adults (1 Working) 1 Child":    (2, 1, 1),
    "2 Adults (1 Working) 2 Children": (2, 2, 1),
    "2 Adults (1 Working) 3 Children": (2, 3, 1),
    "2 Adults (2 Working)":            (2, 0, 2),
    "2 Adults (2 Working) 1 Child":    (2, 1, 2),
    "2 Adults (2 Working) 2 Children": (2, 2, 2),
    "2 Adults (2 Working) 3 Children": (2, 3, 2),
}


# -------------------------------------------------------------------
# 4 ▪︎ Living‑wage table generator
# -------------------------------------------------------------------
def living_wage_table(q: float = 0.5) -> pd.DataFrame:
    base = category_quantile(q)
    rows = []

    for label, (adults, children, earners) in family_types.items():
        fam = family_obj(adults, children, earners)  # if you still need it
        br = bedrooms_required(adults, children)
        rent = housing_quantile(q, br)

        # variable buckets
        health    = city_health_monthly(fam)
        transport = transport_cost(base["transport"], earners, children)
        food      = food_cost(base["food"], adults, children)
        civic     = civic_cost(base["civic"], adults, children)
        other     = other_cost(base["other"], adults, children)
        care      = 0 if (adults == 2 and earners == 1) else base["childcare"] * children
        internet  = internet_cost(base["internet"], adults)

        monthly_net = rent + transport + food + health + civic + other + care + internet

        # --- UPDATED TAX GROSS‑UP ------------------------------------
        filing = ("married" if adults == 2
                  else "hoh" if children > 0
                  else "single")

        annual_gross, _ = gross_from_net(
            monthly_net * 12,
            filing=filing,
            children=children,
            earners=earners
        )

        hourly = annual_gross / (2080 * earners)

        rows.append({
            "Family Type": label,
            "Bedrooms": br,
            "Monthly Net ($)": round(monthly_net, 0),
            "Monthly Gross ($)": round(annual_gross / 12, 0),
            "Annual Gross ($)": round(annual_gross, 0),
            "Living Wage ($/hr)": round(hourly, 2),
        })

    return pd.DataFrame(rows).set_index("Family Type").sort_index()
