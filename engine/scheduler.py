# engine/scheduler.py
import sqlite3
import json

from typing import Dict, List
from collections import defaultdict, deque
from scraper.catalog_scraper import CatalogScraper
from models.course import Course
from models.student import Student
from models.major   import Major

DB_PATH = "data/course_planner.db"

class Scheduler:
    def __init__(self, student: Student, db_path: str = DB_PATH):
        self.student = student
        self.courses: Dict[str, Course] = {}
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.db_path = db_path
    
    def create_database(self):
        """Create SQLite schema for courses, prerequisites, and student info."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # courses table
            c.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                code TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                credit REAL,
                difficulty REAL,
                semesters_offered TEXT,   -- JSON list
                weekly_hours TEXT         -- JSON dict
            )""")
            # prereqs table
            c.execute("""
            CREATE TABLE IF NOT EXISTS prereqs (
                course_code TEXT,
                prereq_code TEXT,
                PRIMARY KEY(course_code, prereq_code),
                FOREIGN KEY(course_code) REFERENCES courses(code),
                FOREIGN KEY(prereq_code) REFERENCES courses(code)
            )""")
            # student table
            c.execute("""
            CREATE TABLE IF NOT EXISTS student (
                student_id TEXT PRIMARY KEY,
                name TEXT,
                school_year TEXT,
                gpa REAL,
                term TEXT
            )""")
            # courses_taken
            c.execute("""
            CREATE TABLE IF NOT EXISTS courses_taken (
                student_id TEXT,
                course_code TEXT,
                PRIMARY KEY(student_id, course_code),
                FOREIGN KEY(student_id) REFERENCES student(student_id),
                FOREIGN KEY(course_code) REFERENCES courses(code)
            )""")
            # current_semester
            c.execute("""
            CREATE TABLE IF NOT EXISTS current_semester (
                student_id TEXT,
                course_code TEXT,
                PRIMARY KEY(student_id, course_code),
                FOREIGN KEY(student_id) REFERENCES student(student_id),
                FOREIGN KEY(course_code) REFERENCES courses(code)
            )""")
            # planned_courses
            c.execute("""
            CREATE TABLE IF NOT EXISTS planned_courses (
                student_id TEXT,
                semester_idx INTEGER,
                course_code TEXT,
                PRIMARY KEY(student_id, semester_idx, course_code),
                FOREIGN KEY(student_id) REFERENCES student(student_id),
                FOREIGN KEY(course_code) REFERENCES courses(code)
            )""")
            conn.commit()
    
    def load_all_from_db(self):
        """Load every table back into memory structures."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()

            # Courses + build self.courses
            c.execute("SELECT * FROM courses")
            for code, title, desc, credit, diff, sems_json, hours_json in c:
                d = {
                    "code": code,
                    "title": title,
                    "description": desc,
                    "credits": credit,
                    "prerequisites": [],  # fill next
                    "semesters_offered": json.loads(sems_json),
                    "weekly_hours": json.loads(hours_json),
                    "difficulty": diff
                }
                self.courses[code] = Course.from_dict(d)

            # Prereqs → graph + update each Course.requirements
            c.execute("SELECT course_code, prereq_code FROM prereqs")
            for course_code, prereq_code in c:
                self.graph[prereq_code].append(course_code)
                self.courses[course_code].requirements.append(prereq_code)

            # Student info
            c.execute("SELECT student_id, name, school_year, gpa, term FROM student")
            row = c.fetchone()
            if row:
                sid, name, year, gpa, term = row
                self.student.student_id = sid
                self.student.name = name
                self.student.school_year = year
                self.student.gpa = gpa
                self.student.term = term

            # courses_taken
            c.execute("SELECT course_code FROM courses_taken WHERE student_id=?", (self.student.student_id,))
            self.student.courses_taken = {r[0] for r in c}

            # current_semester
            c.execute("SELECT course_code FROM current_semester WHERE student_id=?", (self.student.student_id,))
            self.student.current_semester_courses = {r[0] for r in c}

            # planned_courses
            c.execute("SELECT semester_idx, course_code FROM planned_courses WHERE student_id=?", (self.student.student_id,))
            for sem_idx, code in c:
                self.student.planned_courses[sem_idx].append(code)
    
    def update_student_in_db(self):
        """Insert or update the student row and all related course mappings."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # student table
            c.execute("""
                INSERT INTO student(student_id,name,school_year,gpa, term)
                VALUES(?,?,?,?,?)
                ON CONFLICT(student_id) DO UPDATE SET
                  name=excluded.name,
                  school_year=excluded.school_year,
                  gpa=excluded.gpa,
                  term=excluded.term
            """, (self.student.student_id, self.student.name,
                  self.student.school_year, self.student.gpa, self.student.term))
            # courses_taken
            c.execute("DELETE FROM courses_taken WHERE student_id=?", (self.student.student_id,))
            c.executemany("INSERT INTO courses_taken VALUES(?,?)",
                          [(self.student.student_id, code) for code in self.student.courses_taken])
            # current_semester
            c.execute("DELETE FROM current_semester WHERE student_id=?", (self.student.student_id,))
            c.executemany("INSERT INTO current_semester VALUES(?,?)",
                          [(self.student.student_id, code) for code in self.student.current_semester_courses])
            # planned_courses
            c.execute("DELETE FROM planned_courses WHERE student_id=?", (self.student.student_id,))
            rows = []
            for idx, sem in enumerate(self.student.planned_courses):
                rows += [(self.student.student_id, idx, code) for code in sem]
            c.executemany("INSERT INTO planned_courses VALUES(?,?,?)", rows)

            conn.commit()

    def add_or_update_course_in_db(self, course: Course):
        """Insert or update a Course and its prereqs into the DB."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # courses table
            c.execute("""
                INSERT INTO courses(code,title,description,credit,difficulty,semesters_offered,weekly_hours)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(code) DO UPDATE SET
                  title=excluded.title,
                  description=excluded.description,
                  credit=excluded.credit,
                  difficulty=excluded.difficulty,
                  semesters_offered=excluded.semesters_offered,
                  weekly_hours=excluded.weekly_hours
            """, (
                course.code,
                course.title,
                course.description,
                course.credit,
                course.difficulty,
                json.dumps(course.semesters_offered),
                json.dumps(course.weekly_hours),
            ))
            # prereqs table
            c.execute("DELETE FROM prereqs WHERE course_code=?", (course.code,))
            c.executemany("INSERT INTO prereqs VALUES(?,?)",
                          [(course.code, prereq) for prereq in course.requirements])
            conn.commit()

    def load_major_from_url(self, major_url: str):
        scraper = CatalogScraper()
        raw_list = scraper.parse_major_requirements(major_url)

        # Map + DB-insert each course
        for raw in raw_list:
            course = Course.from_dict(raw)
            self.courses[course.code] = course
            self.add_or_update_course_in_db(course)

        # Update student.major object as before
        codes = set(self.courses.keys())
        self.student.major = Major(
            name=self.student.major.name,
            major_courses=codes,
            credit_required=sum(c.credit or 0 for c in self.courses.values())
        )
        # Persist student structure (majors are implicit in planned/course tables)
        self.update_student_in_db()

        # Rebuild in-memory graph
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

if __name__ == "__main__":
    # 1. Setup a dummy Student
    student = Student(
        student_id="S12345",
        name="Test Student",
        school_year="Sophomore",
        major=Major(name="Computer Science, BSE", major_courses=set(), credit_required=0),
        courses_taken=set(["CIS 1100"]),      # assume already took intro CS
        current_semester_courses=set(["CIS 1200"]),  # currently enrolled
        term=""
    )

    sched = Scheduler(student)
    print("Creating database…")
    sched.create_database()

    url = "https://catalog.upenn.edu/undergraduate/programs/computer-science-bse/"

    # 2. Load major (scrape + insert into DB + in-memory)
    print(f"Loading major from {url}")
    sched.load_major_from_url(url)
    print(f"{len(sched.courses)} courses loaded.")

    print("Current courses and prerequisites:")
    for code, course in sched.courses.items():
        print(f"{code}: {course.requirements}")
    
    print("graph of prerequisites:")
    for u, deps in sched.graph.items():
        print(f"{u} -> {deps}")

    # # 3. Reload everything from DB to verify persistence
    print("Reloading all data from DB…")
    sched.load_all_from_db()
    print(f"Student: {sched.student.student_id}, {sched.student.name}, Year: {sched.student.school_year}")
    print(f"Taken: {sched.student.courses_taken}")
    print(f"Current sem: {sched.student.current_semester_courses}")
    print(f"Major courses: {len(sched.student.major.major_courses)} codes")

    # 4. Test add_course (scrape one extra course dict manually)
    extra = {
        "code": "TEST 0001",
        "title": "Dummy Test Course",
        "description": "A dummy course for testing.",
        "credits": 1.0,
        "prerequisites": [],
        "semesters_offered": ["Fall"],
        "weekly_hours": {"Monday": [900, 1000]},
        "difficulty": 2.5
    }
    print("Adding new course TEST 0001…", sched.add_course(extra))
    sched.add_or_update_course_in_db(Course.from_dict(extra))

    # 5. Test add_major_course
    print("Adding TEST 0001 to major…", sched.add_major_course("TEST 0001"))
    print(f"New credit_required: {sched.student.major.credit_required}")

    # 6. Test edit_student_info
    print("Editing student info…")
    sched.edit_student_info(name="Updated Student", school_year="Junior", gpa=3.9)
    sched.update_student_in_db()
    print(f"New name/year/gpa: {sched.student.name}, {sched.student.school_year}, {sched.student.gpa}")

    # 7. Test edit_course
    print("Editing TEST 0001 difficulty to 3.0…", sched.edit_course("TEST 0001", difficulty=3.0))
    sched.add_or_update_course_in_db(sched.courses["TEST 0001"])

    # 8. Test toposort helper
    print("Topo sort of current graph (first 10):", sched.topo_sort(sched.graph)[:10])

    # 9. Test generate_plan from semester index 2
    avg_diff = sched.generate_plan(current_semester_idx=2)
    print("Generated plan (semesters 3–8):")
    for idx, sem in enumerate(sched.student.planned_courses, start=1):
        print(f"  Sem {idx}: {sem}")
    print(f"Overall average difficulty (sem 3+): {avg_diff:.2f}")
