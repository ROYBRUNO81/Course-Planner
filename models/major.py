from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class Major:
    name: str
    major_courses: Set[str]        # course codes
    credit_required: float 