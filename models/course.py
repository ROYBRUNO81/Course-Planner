from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Course:
    code: str
    title: str
    description: str
    requirements: List[str]           # e.g. IDs of prerequisite courses
    semesters_offered: List[str]      # e.g. ["Fall", "Spring"]
    weekly_hours: Dict[str, List[int]]   
    difficulty: float                 # scale 1.0–4.0 value
    credit: Optional[float]

    @classmethod
    def from_dict(cls, d: dict):
        # Helper to convert your scraper’s dict into a Course
        return cls(
            code=d["code"],
            title=d["title"],
            description=d.get("description", ""),
            semesters_offered=d.get("semesters_offered", []),
            requirements=d.get("prerequisites", []),
            credit=d.get("credits", None),
        )
