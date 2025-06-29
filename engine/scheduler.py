# engine/scheduler.py

from typing import Dict, List
from collections import defaultdict, deque
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
        gpa: float = None,
        term: str = None
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
        if term is not None:
            self.student.term = term

    def edit_course(self, course_code: str, **updates) -> bool:
        """
        Edit fields of an existing Course in self.courses.

        Parameters:
            - course_code: the code of the course to edit (e.g. "CIS 3200")
            - updates:      keyword args mapping Course field names to new values

        Returns True if the course was found and updated, False otherwise.
        Raises ValueError if you try to update a non-existent field.
        """
        code = course_code.strip().upper()
        if code not in self.courses:
            return False

        course = self.courses[code]
        for field_name, new_value in updates.items():
            if not hasattr(course, field_name):
                raise ValueError(f"Course has no field '{field_name}'")
            setattr(course, field_name, new_value)

        # If credit changed, keep the major's credit_required in sync:
        if 'credit' in updates:
            total = sum(self.courses[c].credit or 0 for c in self.student.major.major_courses)
            self.student.major.credit_required = total

        # If prerequisites changed, rebuild the graph:
        if 'requirements' in updates:
            self.build_prereq_graph()

        return True
    
    def topo_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        Kahn’s algorithm: graph is prereq -> [dependent,...].
        Returns a list of nodes in topo order.
        """
        indegree = {u: 0 for u in graph}
        for deps in graph.values():
            for v in deps:
                indegree[v] = indegree.get(v, 0) + 1

        q = deque([u for u, deg in indegree.items() if deg == 0])
        result = []
        while q:
            u = q.popleft()
            result.append(u)
            for v in graph.get(u, []):
                indegree[v] -= 1
                if indegree[v] == 0:
                    q.append(v)
        return result

    def generate_plan(self, current_semester_idx: int) -> float:
        # Determine remaining courses
        all_reqs = set(self.student.major.major_courses)
        done = set(self.student.courses_taken) | set(self.student.current_semester_courses)
        remaining = all_reqs - done

        # Induce graph on remaining
        induced = {u: [v for v in self.graph.get(u, []) if v in remaining]
                   for u in remaining}

        # Topo-sort
        order = self.topo_sort(induced)

        # Prepare plan, difficulty trackers, and schedule grids
        plan = self.student.planned_courses
        diff_sum = [0.0] * len(plan)
        count    = [0]   * len(plan)
        # For each semester, track scheduled slots per weekday
        schedule_slots: List[Dict[str, List[List[int]]]] = [
            defaultdict(list) for _ in plan
        ]
        terms = ["Fall", "Spring"] * ((len(plan)+1)//2)

        # Place courses by descending difficulty
        for code in sorted(order, key=lambda c: self.courses[c].difficulty, reverse=True):
            course = self.courses[code]
            candidates = []
            for sem in range(current_semester_idx, len(plan)):
                if terms[sem] not in course.semesters_offered:
                    continue

                # Check for time conflicts on every day
                conflict = False
                for day, interval in course.weekly_hours.items():
                    start, end = interval
                    for (s2, e2) in schedule_slots[sem].get(day, []):
                        if not (end <= s2 or start >= e2):
                            conflict = True
                            break
                    if conflict:
                        break

                if not conflict:
                    candidates.append(sem)

            if not candidates:
                continue

            # Choose semester with lowest current avg difficulty
            def avg(idx): return diff_sum[idx]/count[idx] if count[idx] else 0.0
            best = min(candidates, key=avg)

            # Assign course
            plan[best].append(code)
            diff_sum[best] += course.difficulty
            count[best]   += 1
            # Register its time slots
            for day, interval in course.weekly_hours.items():
                schedule_slots[best][day].append(interval)

        # Compute overall average difficulty
        filled = [i for i in range(current_semester_idx, len(plan)) if count[i] > 0]
        if not filled:
            return 0.0
        per_sem = [diff_sum[i]/count[i] for i in filled]
        return sum(per_sem) / len(per_sem)
