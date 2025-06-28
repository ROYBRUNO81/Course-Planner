from dataclasses import dataclass, field
from typing import List, Optional

from models.major import Major
from models.minor import Minor

@dataclass
class Student:
    student_id: str
    name: str
    school_year: str                  # "Freshman", "Sophomore"
    major: Major                      # assigned Major object
    minor: Optional[Minor] = None     # assigned Minor, if any
    courses_taken: List[str] = field(default_factory=list)
    current_semester_courses: List[str] = field(default_factory=list)
    gpa: Optional[float] = None       # cumulative GPA
    planned_courses: List[List[str]] = field(default_factory=lambda: [[], [], [], [], [], [], [], []])
    # planned_courses: list of 8 semesters, each with a list of course codes