from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class Minor:
    name: str
    required_courses: Set[str]
    gen_requirements: Set[str]        # general education tags
    credit_required: int    