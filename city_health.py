from random import choices
from family_dataclass import Family

def city_health_monthly(fam: Family) -> float:
    """
    Return *monthly* total healthcare cost = premium + out-of-pocket
    using the same rules you coded last year.
    """
    # --- out-of-pocket ----------------------------------------------
    adult_oop  = 33.33 + 11.67 + 66.33    # = 111.33
    child_oop  = adult_oop * 0.8
    oop = (adult_oop * fam.total_adults + child_oop * fam.children)

    # --- premium ----------------------------------------------------
    plans = {
        "ee": 51.11,
        "ee+sp": 252.89,
        "ee+ch": 188.68,
        "family": 353.78,
    }

    if fam.total_adults == 1:
        premium = plans["ee"] if fam.children == 0 else plans["ee+ch"]
    else:  # two adults
        if fam.children == 0:
            premium = choices([plans["ee+sp"], plans["ee"]],
                              weights=[0.5, 0.5])[0]
        else:
            premium = choices(
                [plans["family"], plans["ee"], plans["ee+sp"], plans["ee+ch"]],
                weights=[0.25, 0.25, 0.25, 0.25])[0]

    return premium + oop
