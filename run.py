from scraper.catalog_scraper import CatalogScraper
from engine.scheduler import Scheduler
from gui.main_window import MainWindow
import sys

if __name__ == "__main__":
    # initialize scraper and cache
    scraper = CatalogScraper()
    scraper.build_cache()

    # initialize scheduling engine
    scheduler = Scheduler(scraper.cache_path)

    # launch GUI
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow(scheduler)
    window.show()
    sys.exit(app.exec())