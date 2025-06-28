# engine/scheduler.py

from typing import Dict, List
from collections import defaultdict
from scraper.catalog_scraper import CatalogScraper
from models.course import Course
from models.student import Student
from models.major   import Major

class Scheduler:
    def __init__(self, student: Student):
        """
        Scheduler holds onto:
         - the Student object we’re planning for
         - a lookup of Course.code → Course instance
         - a prereq graph where edges point prereq → dependent course
        """
        self.student     = student
        self.courses: Dict[str, Course] = {}
        self.graph: Dict[str, List[str]] = defaultdict(list)

    def load_major_from_url(self, major_url: str):
        """
        Scrape the provided major URL for required courses.
        Convert each dict → Course via from_dict().
        Update student.major.major_courses set.
        Build prereq graph.
        """
        scraper = CatalogScraper()
        raw_list = scraper.parse_major_requirements(major_url)

        # Map codes → Course
        for raw in raw_list:
            course = Course.from_dict(raw)
            self.courses[course.code] = course

        # Update student.major
        codes = set(self.courses.keys())
        self.student.major = Major(
            name=self.student.major.name,    
            major_courses=codes,
            credit_required=sum(c.credit or 0 for c in self.courses.values())
        )

        self.build_prereq_graph()

    def build_prereq_graph(self):
        """Rebuild the prereq dependency graph from self.courses."""
        self.graph.clear()
        for course in self.student.major.major_courses:
            for prereq in self.courses[course].requirements:
                self.graph[prereq].append(course)

    def add_course(self, raw: dict) -> bool:
        """
        Add a new course to the catalog (self.courses).
        raw should be the dict format returned by parse_major_requirements.
        Returns True if added, False if the code already existed.
        """
        code = raw.get("code")
        if not code or code in self.courses:
            return False
        course = Course.from_dict(raw)
        self.courses[course.code] = course
        return True

    def add_major_course(self, course_code: str) -> bool:
        """
        Add an existing course (by code) from self.courses into the student's major.
        Returns True if successfully added; False if invalid code or already present.
        """
        code = course_code.strip().upper()
        if code not in self.courses:
            return False
        if code in self.student.major.major_courses:
            return False
        self.student.major.major_courses.add(code)
        self.student.major.credit_required += self.courses[code].credit or 0
        # rebuild graph in case this new major course has prereqs we need
        self.build_prereq_graph()
        return True

    def edit_student_info(
        self,
        student_id: str = None,
        name: str = None,
        school_year: str = None,
        gpa: float = None
    ) -> None:
        """
        Update the Student’s personal fields in-place.
        """
        if student_id is not None:
            self.student.student_id = student_id
        if name is not None:
            self.student.name = name
        if school_year is not None:
            self.student.school_year = school_year
        if gpa is not None:
            self.student.gpa = gpa
