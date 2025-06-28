from scraper.catalog_scraper import CatalogScraper
from models.course         import Course

scraper = CatalogScraper()
raw_courses = scraper.parse_major_requirements(major_url)

# Build a dict code → Course
course_catalog = {
    d["code"]: Course.from_dict({
        "code": d["code"],
        "title": d["title"],
        "description": d["description"],
        "prerequisites": d["prerequisites"],
        "semesters_offered": d["semesters_offered"],
        "credits": d["credits"],
        # for now you can set weekly_hours & difficulty to defaults or
        # derive them later once you have that data
    })
    for d in raw_courses
}