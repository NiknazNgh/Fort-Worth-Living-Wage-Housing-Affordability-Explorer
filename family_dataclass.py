from dataclasses import dataclass

@dataclass(frozen=True)
class Family:
    adults_working: int      # 1 or 2
    adults_nonworking: int   # 0‒2
    children: int            # 0‒3

    @property
    def total_adults(self):   return self.adults_working + self.adults_nonworking
    @property
    def total_people(self):   return self.total_adults + self.children

def family_obj(adults, children, earners) -> Family:
    return Family(adults_working=earners,
                adults_nonworking=adults-earners,
                children=children)
