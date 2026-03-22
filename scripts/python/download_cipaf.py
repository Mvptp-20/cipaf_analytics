"""
CIPAF - Research Downloader
=============================
Downloads PDF, XLSX, XLS, and CSV files from a list of URLs.
Can read URLs from a scout output file or accept them directly.

Usage (called by Claude via the pipeline skill):
    python download_cipaf.py \
        --save-folder "/path/to/output" \
        --urls-file "/path/to/sources_topic_timestamp.txt"

    # Or with direct URLs:
    python download_cipaf.py \
        --save-folder "/path/to/output" \
        --urls "https://..." "https://..."
"""

import subprocess, sys

def _ensure(pkg, import_name=None):
    try:
        __import__(import_name or pkg)
    except ImportError:
        print(f"  Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("requests")
_ensure("beautifulsoup4", "bs4")

import os
import re
import time
import requests
import logging
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# ARGUMENT PARSING
# ─────────────────────────────────────────────

parser = argparse.ArgumentParser(description="CIPAF Research Downloader")
parser.add_argument("--save-folder", required=True, help="Folder to save downloaded files")
parser.add_argument("--urls-file",   help="Path to scout output URL list file")
parser.add_argument("--urls",        nargs="+", help="Direct list of URLs to scrape/download")
args = parser.parse_args()

SAVE_FOLDER = args.save_folder
Path(SAVE_FOLDER).mkdir(parents=True, exist_ok=True)

TARGET_EXTENSIONS = (".pdf", ".xlsx", ".xls", ".csv")

DOMAIN_ALIASES = {
    "statistics.cepal.org":              "CEPALSTAT",
    "observatorioplanificacion.cepal.org": "CEPAL",
    "repositorio.cepal.org":             "CEPAL_Repositorio",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────
# LOAD SOURCE URLS
# ─────────────────────────────────────────────

def load_urls_from_file(filepath: str) -> list:
    """Parse a scout output file and extract all non-comment URLs."""
    urls = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls

if args.urls_file:
    SOURCE_URLS = load_urls_from_file(args.urls_file)
elif args.urls:
    SOURCE_URLS = args.urls
else:
    print("Error: provide --urls-file or --urls")
    exit(1)

# URLs that need Selenium (JS-rendered pages)
SELENIUM_URLS = {
    "statistics.cepal.org",
    "mepyd.gob.do",
    "hacienda.gob.do",
    "observatorioplanificacion.cepal.org",
}

# ─────────────────────────────────────────────
# SETUP LOGGING
# ─────────────────────────────────────────────

log_path = os.path.join(SAVE_FOLDER, "_download_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

session = requests.Session()
session.headers.update(HEADERS)

downloaded   = []
skipped      = []
already_have = []
failed       = []

# ─────────────────────────────────────────────
# SELENIUM — optional
# ─────────────────────────────────────────────

SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    pass


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def is_downloadable(url: str) -> bool:
    return url.lower().split("?")[0].endswith(TARGET_EXTENSIONS)


def safe_filename(url: str, folder: str):
    name = os.path.basename(urlparse(url).path)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ") or "file"
    candidate = os.path.join(folder, name)
    if os.path.exists(candidate):
        return candidate, name, True
    return candidate, name, False


def subfolder_for(url: str) -> str:
    domain = urlparse(url).netloc
    if domain in DOMAIN_ALIASES:
        label = DOMAIN_ALIASES[domain]
    else:
        label = domain.replace("www.", "").split(".")[0].upper()
    path = os.path.join(SAVE_FOLDER, label)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def download_file(url: str, dest_folder: str) -> bool:
    filepath, filename, exists = safe_filename(url, dest_folder)
    if exists:
        log.info(f"  ⟳  {filename} — already downloaded, skipping")
        already_have.append({"file": filename, "url": url})
        return True
    try:
        r = session.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = os.path.getsize(filepath) / 1024
        log.info(f"  ✔  {filename}  ({size_kb:.1f} KB)")
        downloaded.append({"file": filename, "url": url})
        return True
    except Exception as e:
        log.warning(f"  ✘  {filename} — {e}")
        failed.append({"url": url, "error": str(e)})
        return False


def process_links(links: list) -> int:
    count = 0
    for abs_url in links:
        if is_downloadable(abs_url):
            count += 1
            folder = subfolder_for(abs_url)
            download_file(abs_url, folder)
            time.sleep(0.5)
    return count


# ─────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────

def scrape_static(page_url: str) -> int:
    try:
        r = session.get(page_url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Could not load page: {e}")
        failed.append({"url": page_url, "error": str(e)})
        return -1
    soup  = BeautifulSoup(r.text, "html.parser")
    links = [urljoin(page_url, tag["href"].strip()) for tag in soup.find_all("a", href=True)]
    return process_links(links)


def scrape_selenium(page_url: str) -> int:
    if not SELENIUM_AVAILABLE:
        log.warning("  Selenium not installed — skipping JS page.")
        skipped.append(page_url)
        return 0
    log.info("  (using Selenium for JavaScript rendering)")
    driver = None
    try:
        driver = make_driver()
        driver.get(page_url)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "a"))
            )
        except Exception:
            pass
        time.sleep(3)
        soup  = BeautifulSoup(driver.page_source, "html.parser")
        links = [urljoin(page_url, tag["href"].strip()) for tag in soup.find_all("a", href=True)]
        return process_links(links)
    except Exception as e:
        log.warning(f"  Selenium error: {e}")
        failed.append({"url": page_url, "error": f"Selenium: {e}"})
        return -1
    finally:
        if driver:
            driver.quit()


def scrape_page(page_url: str):
    log.info(f"\n{'='*60}\nScanning: {page_url}")
    if is_downloadable(page_url):
        folder = subfolder_for(page_url)
        download_file(page_url, folder)
        return
    needs_selenium = any(s in page_url for s in SELENIUM_URLS)
    if needs_selenium:
        links_found = scrape_selenium(page_url)
    else:
        links_found = scrape_static(page_url)
    if links_found == 0:
        log.info("  ⚠  No downloadable files found on this page.")
        skipped.append(page_url)
    elif links_found > 0:
        log.info(f"  → {links_found} file(s) processed from this page.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log.info("CIPAF Downloader — Starting")
    log.info(f"Save folder : {SAVE_FOLDER}")
    log.info(f"Sources     : {len(SOURCE_URLS)} URLs")
    log.info(f"Selenium    : {'available ✔' if SELENIUM_AVAILABLE else 'NOT installed'}\n")

    for url in SOURCE_URLS:
        scrape_page(url)
        time.sleep(1)

    log.info(f"\n{'='*60}\nSUMMARY")
    log.info(f"  Downloaded : {len(downloaded)} new files")
    log.info(f"  Already had: {len(already_have)} files (skipped)")
    log.info(f"  Failed     : {len(failed)}")
    log.info(f"  No-links   : {len(skipped)} pages")

    if failed:
        log.info("\nFailed downloads:")
        for f in failed:
            log.info(f"  • {f['url']}\n    Error: {f['error']}")

    log.info(f"\nLog saved to: {log_path}")
    log.info("Done.")
    print(f"DOWNLOAD_COMPLETE:{len(downloaded)} new files, {len(already_have)} skipped, {len(failed)} failed")


if __name__ == "__main__":
    main()