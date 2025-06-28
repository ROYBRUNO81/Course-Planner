from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Course:
    code: str
    title: str
    description: str
    requirements: List[str]           # e.g. IDs of prerequisite courses
    semesters_offered: List[str]      # e.g. ["Fall", "Spring"]
    weekly_hours: Dict[str, float]    # e.g. {"Lecture": 3.0, "Lab": 1.0}
    difficulty: float                 # scale 1.0–4.0 value