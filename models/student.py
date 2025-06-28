from dataclasses import dataclass, field
from typing import List, Optional, Set

from models.major import Major

@dataclass
class Student:
    student_id: str
    name: str
    school_year: str                  # "Freshman", "Sophomore"
    major: Major                      # assigned Major object
    courses_taken: Set[str]  # set of course codes
    current_semester_courses: Set[str]
    gpa: Optional[float] = None       # cumulative GPA
    planned_courses: List[List[str]] = field(default_factory=lambda: [[], [], [], [], [], [], [], []])
    # planned_courses: list of 8 semesters, each with a list of course codes