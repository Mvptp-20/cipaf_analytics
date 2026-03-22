import os
import re
import time
import logging
import argparse

from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from ddgs import DDGS


# ============================================================
# ARGUMENT PARSING
# ============================================================

parser = argparse.ArgumentParser(description="CIPAF Research Source Scout")

parser.add_argument("--lang", choices=["en", "es"], default="es", help="Idioma / Language")
parser.add_argument("--topic-label", required=False, help="Human-readable topic label")
parser.add_argument("--topic-slug", required=False, help="Short slug (no spaces)")
parser.add_argument("--save-folder", required=False, help="Folder to save results")
parser.add_argument("--queries", nargs="+", required=False, help="List of search queries")
parser.add_argument("--results-per-query", type=int, default=10, help="Results to save per query")
parser.add_argument("--min-score", type=int, default=3, help="Minimum trust score")

args = parser.parse_args()


# ============================================================
# LANGUAGE TEXT
# ============================================================

TEXT = {
    "es": {
        "topic_label": "Ingrese el tema (nombre descriptivo): ",
        "save_folder": "Ingrese el nombre de la carpeta de salida (ejemplo: salida_boletin): ",
        "queries": "Ingrese las consultas de búsqueda (separadas por comas): ",
        "no_results": "No se encontraron resultados. Revise la conexión o pruebe otras consultas."
    },
    "en": {
        "topic_label": "Enter topic label (human readable): ",
        "save_folder": "Enter output folder name (example: output_folder): ",
        "queries": "Enter search queries (comma separated): ",
        "no_results": "No results found. Check internet connection or try different queries."
    }
}

LANG = args.lang


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def ask_if_missing(value, prompt_text, is_list=False):
    if value:
        return value
    user_input = input(prompt_text)
    if is_list:
        return [q.strip() for q in user_input.split(",") if q.strip()]
    return user_input.strip()


def generate_slug(text):
    text = text.lower().strip()
    replacements = {
        "á": "a", "à": "a", "ä": "a", "â": "a",
        "é": "e", "è": "e", "ë": "e", "ê": "e",
        "í": "i", "ì": "i", "ï": "i", "î": "i",
        "ó": "o", "ò": "o", "ö": "o", "ô": "o",
        "ú": "u", "ù": "u", "ü": "u", "û": "u",
        "ñ": "n"
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def clean_folder_name(name):
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name


# ============================================================
# INPUT COLLECTION
# ============================================================

TOPIC_LABEL = ask_if_missing(
    args.topic_label,
    TEXT[LANG]["topic_label"]
)

TOPIC_SLUG = args.topic_slug or generate_slug(TOPIC_LABEL)

BASE_OUTPUT = "outputs"

user_folder = clean_folder_name(
    ask_if_missing(
        args.save_folder,
        TEXT[LANG]["save_folder"]
    )
)

SAVE_FOLDER = os.path.join(BASE_OUTPUT, user_folder)

SEARCH_QUERIES = ask_if_missing(
    args.queries,
    TEXT[LANG]["queries"],
    is_list=True
)

RESULTS_PER_QUERY = args.results_per_query
MIN_SCORE = args.min_score


# ============================================================
# TRUST / SCORING CONFIG
# ============================================================

DOMAIN_SCORES = {
    # Dominican Republic government
    "one.gob.do": 10,
    "msp.gob.do": 10,
    "mepyd.gob.do": 9,
    "ministeriodelamujer.gob.do": 10,
    "presidencia.gob.do": 8,
    "siuben.gob.do": 8,

    # International / institutional
    "cepal.org": 9,
    "eclac.org": 9,
    "undp.org": 8,
    "pnud.org": 8,
    "unwomen.org": 8,
    "onu.org": 7,
    "worldbank.org": 8,
    "bancomundial.org": 8,
    "unicef.org": 8,
    "who.int": 7,
    "paho.org": 7,

    # Academic / research
    "scielo.org": 7,
    "redalyc.org": 6,
}

URL_KEYWORD_BONUS = {
    "pdf": 2,
    "informe": 2,
    "report": 2,
    "estadistica": 2,
    "datos": 2,
    "boletin": 2,
    "boletín": 2,
    "encuesta": 1,
    "dashboard": 1,
    "observatorio": 2
}

FILE_EXT_BONUS = {
    ".pdf": 3,
    ".xlsx": 2,
    ".xls": 2,
    ".csv": 2,
    ".doc": 1,
    ".docx": 1,
    ".ppt": 1,
    ".pptx": 1
}


# ============================================================
# SETUP
# ============================================================

Path(SAVE_FOLDER).mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M")
log_filename = f"scout_log_{TOPIC_SLUG}_{timestamp}.txt"
log_path = os.path.join(SAVE_FOLDER, log_filename)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# CONFIG OUTPUT
# ============================================================

log.info("--- CONFIGURACIÓN / CONFIG ---")
log.info(f"LANG: {LANG}")
log.info(f"TOPIC_LABEL: {TOPIC_LABEL}")
log.info(f"TOPIC_SLUG: {TOPIC_SLUG}")
log.info(f"SAVE_FOLDER: {SAVE_FOLDER}")
log.info(f"SEARCH_QUERIES: {SEARCH_QUERIES}")
log.info(f"RESULTS_PER_QUERY: {RESULTS_PER_QUERY}")
log.info(f"MIN_SCORE: {MIN_SCORE}")
log.info("------------------------------")


# ============================================================
# SCORING ENGINE
# ============================================================

def score_url(url: str, title: str = "", snippet: str = "") -> dict:
    score = 0
    reasons = []
    url_lower = url.lower()

    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    for trusted_domain, pts in DOMAIN_SCORES.items():
        if trusted_domain in domain:
            score += pts
            reasons.append(f"trusted domain ({trusted_domain}: +{pts})")
            break
    else:
        if ".gob.do" in domain:
            score += 6
            reasons.append("gov.do domain (+6)")
        elif ".edu.do" in domain:
            score += 5
            reasons.append("edu.do domain (+5)")
        elif ".edu" in domain:
            score += 3
            reasons.append("edu domain (+3)")

    for kw, pts in URL_KEYWORD_BONUS.items():
        if kw in url_lower:
            score += pts
            reasons.append(f"URL has '{kw}' (+{pts})")

    for ext, pts in FILE_EXT_BONUS.items():
        if url_lower.endswith(ext):
            score += pts
            reasons.append(f"direct file link {ext} (+{pts})")
            break

    combined_text = (title + " " + snippet).lower()
    text_keywords = ["estadistica", "datos", "informe", "dominicana", "dominican", "cepal", "one.gob"]
    for kw in text_keywords:
        if kw in combined_text:
            score += 1
            reasons.append(f"text has '{kw}' (+1)")

    return {
        "score": score,
        "reasons": "; ".join(reasons) if reasons else "no bonus"
    }


# ============================================================
# SEARCH ENGINE
# ============================================================

def run_searches() -> list:
    seen_urls = set()
    all_results = []

    with DDGS() as ddgs:
        for i, query in enumerate(SEARCH_QUERIES, 1):
            log.info(f"\n[{i}/{len(SEARCH_QUERIES)}] Searching: {query}")
            try:
                results = list(ddgs.text(query, max_results=RESULTS_PER_QUERY))
                log.info(f"  → {len(results)} results returned")

                for r in results:
                    url = r.get("href", "").strip()
                    title = r.get("title", "")
                    snippet = r.get("body", "")

                    if not url or url in seen_urls:
                        continue

                    seen_urls.add(url)
                    scored = score_url(url, title, snippet)

                    all_results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "score": scored["score"],
                        "reasons": scored["reasons"],
                        "query": query,
                    })

                time.sleep(1.5)

            except Exception as e:
                log.warning(f"  ⚠ Query failed: {e}")

    return all_results


# ============================================================
# OUTPUT WRITERS
# ============================================================

def write_results(results: list) -> tuple[str, str]:
    # Sort all results
    all_results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Filter high-confidence from the already-sorted list
    filtered = [r for r in all_results if r["score"] >= MIN_SCORE]

    # Save ALL results
    out_all = os.path.join(SAVE_FOLDER, f"sources_{TOPIC_SLUG}_{timestamp}_ALL.txt")
    with open(out_all, "w", encoding="utf-8") as f:
        f.write(f"# CIPAF Research Scout — ALL Results\n")
        f.write(f"# Topic   : {TOPIC_LABEL}\n")
        f.write(f"# Created : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Total   : {len(all_results)} URLs\n\n")

        for r in all_results:
            f.write(f"# Score: {r['score']} | Query: {r['query']}\n")
            f.write(f"# Title: {r['title']}\n")
            f.write(f"# Reason: {r['reasons']}\n")
            f.write(f"{r['url']}\n\n")

    # Save HIGH confidence results
    out_high = os.path.join(SAVE_FOLDER, f"sources_{TOPIC_SLUG}_{timestamp}_HIGH.txt")
    with open(out_high, "w", encoding="utf-8") as f:
        f.write(f"# CIPAF Research Scout — High Confidence Results\n")
        f.write(f"# Topic   : {TOPIC_LABEL}\n")
        f.write(f"# Created : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Total   : {len(filtered)} URLs (score >= {MIN_SCORE})\n\n")

        for r in filtered:
            f.write(f"# Score: {r['score']} | Query: {r['query']}\n")
            f.write(f"# Title: {r['title']}\n")
            f.write(f"# Reason: {r['reasons']}\n")
            f.write(f"{r['url']}\n\n")

    log.info(f"\n✔ ALL results saved → {out_all} ({len(all_results)} URLs)")
    log.info(f"✔ HIGH confidence saved → {out_high} ({len(filtered)} URLs)")

    return out_all, out_high


# ============================================================
# MAIN
# ============================================================

def main():
    log.info("═" * 60)
    log.info("CIPAF Research Scout")
    log.info(f"Topic   : {TOPIC_LABEL}")
    log.info(f"Queries : {len(SEARCH_QUERIES)}")
    log.info(f"Folder  : {SAVE_FOLDER}")
    log.info("═" * 60)

    results = run_searches()
    log.info(f"\n── Search complete. {len(results)} unique URLs collected. ──")

    if not results:
        log.warning(TEXT[LANG]["no_results"])
        return

    out_all, out_high = write_results(results)

    filtered = [r for r in results if r["score"] >= MIN_SCORE]

    log.info(f"\n{'═' * 60}\nSUMMARY")
    log.info(f"  Total unique URLs : {len(results)}")
    log.info(f"  High-confidence   : {len(filtered)} (score ≥ {MIN_SCORE})")
    log.info(f"  ALL saved to      : {out_all}")
    log.info(f"  HIGH saved to     : {out_high}")
    log.info("═" * 60)

    print(f"SCOUT_OUTPUT_ALL:{out_all}")
    print(f"SCOUT_OUTPUT_HIGH:{out_high}")


if __name__ == "__main__":
    main()