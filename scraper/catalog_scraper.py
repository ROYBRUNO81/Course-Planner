import re
import requests # type: ignore
from bs4 import BeautifulSoup # type: ignore

class CatalogScraper:
    def __init__(self):
        self.search_base = "https://catalog.upenn.edu/search/?search="

    def parse_major_requirements(self, major_url: str):
        resp = requests.get(major_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Locate the course-list table by its class
        table = soup.select_one("table.sc_courselist")
        if not table:
            raise RuntimeError("No <table class='sc_courselist'> found")

        courses = []
        # Iterate each row
        for row in table.select("tr"):
            # Find the code cell
            code_td = row.select_one("td.codecol")
            title_td = row.select_one("td:nth-of-type(2)")
            credit_td = row.select_one("td:nth-of-type(3)")
            if not code_td or not title_td or not credit_td:
                continue

            raw_code = code_td.get_text(strip=True)
            raw_code = " ".join(raw_code.replace("\xa0", " ").split())
            # Handle cross-listings: take only the first code before any '/'
            primary_code = raw_code.split("/")[0].strip()

            # Validate format
            parts = primary_code.split()
            if len(parts) != 2 or not parts[1].isdigit():
                continue

            title   = title_td.get_text(strip=True)
            credit_text = credit_td.get_text(strip=True)
            try:
                credits = float(credit_text)
            except ValueError:
                credits = None

            # Only accept valid codes like
            parts = primary_code.split()
            if len(parts) != 2 or not parts[1].isdigit():
                continue

            # Fetch description, semesters, prerequisites
            detail = self.get_course_detail(primary_code)

            courses.append({
                "code": primary_code,
                "title": title,
                "credits": credits,
                **detail
            })

        return courses

    def get_course_detail(self, course_code: str):
        url = self.search_base + course_code.replace(" ", "+")
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Locate the courseblock
        block = soup.select_one("div.search-summary div.courseblock")
        if not block:
            raise RuntimeError(f"No courseblock for {course_code}")

        # Gather <p class="courseblockextra noindent">
        paras = block.select("p.courseblockextra.noindent")

        # Description is the first paragraph
        description = paras[0].get_text(strip=True) if len(paras) > 0 else ""

        # Semester offerings 
        semesters = []
        if len(paras) > 1:
            sem_text = paras[1].get_text(strip=True)
            for term in ("Fall", "Spring", "Summer"):
                if term in sem_text:
                    semesters.append(term)

        # Prerequisites: third <p>
        prereqs = []
        if len(paras) > 2 and "Prerequisite" in paras[2].get_text():
            # 1) Try to grab the bubblelink codes
            links = paras[2].select("a.bubblelink.code")
            if links:
                prereqs = []
                for a in links:
                    raw = a.get_text()
                    # Replace non-breaking spaces, collapse whitespace
                    clean = " ".join(raw.replace("\xa0", " ").split())
                    prereqs.append(clean)
            else:
                # 2) Fallback: regex scan for codes like "ABCD 1234"
                text = paras[2].get_text()
                matches = re.findall(r"[A-Z]{2,4}\s*\d{4}", text)
                prereqs = []
                for m in matches:
                    clean = " ".join(m.replace("\xa0", " ").split())
                    prereqs.append(clean)

        return {
            "description": description,
            "semesters_offered": semesters,
            "prerequisites": prereqs
        }

# Quick test
if __name__ == "__main__":
    url = "https://catalog.upenn.edu/undergraduate/programs/computer-science-bse/"
    scraper = CatalogScraper()
    courses = scraper.parse_major_requirements(url)
    for c in courses:
        print(f"{c['code']:10} {c['title'][:30]:30} {c['credits']:4}  {c['semesters_offered']} prereqs:{c['prerequisites']}")
