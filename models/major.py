from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class Major:
    name: str
    required_courses: Set[str]        # course codes
    gen_requirements_sshum: Set[str]  # social science & humanities gen-ed tags
    gen_requirements_major: Set[str]  # major-area gen-ed tags
    credit_required: int  