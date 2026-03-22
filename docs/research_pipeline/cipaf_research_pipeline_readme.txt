---
name: cipaf-research-pipeline
description: >
  Use this skill to run a full automated research pipeline for any topic: scouts the web for
  relevant sources, downloads all files (PDFs, Excel, CSV), catalogs them by relevance into
  an inventory Excel file, reorganizes the folder by HIGH/MEDIUM/LOW relevance, and creates
  a zip of the results. Trigger when the user says things like "run the research pipeline",
  "scout and download sources for [topic]", "build a research folder on [topic]",
  "download and catalog sources about [topic]", "run the CIPAF pipeline", or any combination
  of "research + download + organize". Also trigger when the user wants to run any individual
  step of the pipeline (scout only, download only, triage only, or organize only).
  Always use this skill when the user mentions a research topic and wants to gather documents.
---

# CIPAF Research Pipeline Skill

This skill automates a full research document pipeline in 4 modular steps:

1. **Scout** — Search the web for relevant source URLs on a given topic
2. **Download** — Fetch all PDF/Excel/CSV files from those URLs
3. **Triage** — Scan every file and build an `_INVENTARIO_*.xlsx` catalog with relevance scores
4. **Organize** — Sort files into `HIGH / MEDIUM / LOW` → source folder structure and zip

Each step can be run independently or all together in sequence.

## Scripts location

All scripts are in `scripts/` relative to this SKILL.md:
- `scripts/scout_cipaf.py`
- `scripts/download_cipaf.py`
- `scripts/triage_cipaf.py`
- `scripts/organize_inventory.py`

To get the path to the scripts directory, note it is in the same folder as this SKILL.md.

## Step 0 — Gather inputs from user

Before running anything, confirm these three things:

1. **Topic** — What is the research topic? (e.g., "Poverty in Dominican Republic", "Maternal Mortality", "Child Nutrition")
2. **Save folder** — Where should files be saved? This should be the user's mounted workspace folder (check `/sessions/*/mnt/` for the active workspace). If unclear, ask.
3. **Which steps** — Run the full pipeline (all 4 steps), or just specific ones?

If the user already ran the scout before and has a URL list file, you can skip step 1 and point the downloader at that file.

## Step 1 — Scout: Find sources

Generate search queries for the topic. A good set has:
- 4-6 Spanish queries with country name + statistical terms (estadísticas, datos, informe, boletín)
- 2-4 English queries (report, statistics, data)
- Queries targeting key institutions (ONE, CEPAL, MEPYD, PAHO, WHO, World Bank, etc.)

Run the scout:

```bash
python <skill_dir>/scripts/scout_cipaf.py \
  --topic-label "<Human Readable Topic>" \
  --topic-slug "<topic_slug_no_spaces>" \
  --save-folder "<save_folder>" \
  --queries \
    "query 1 here" \
    "query 2 here" \
    ...
```

Install dependencies if needed:
```bash
pip install duckduckgo-search --break-system-packages -q
```

The scout will print `SCOUT_OUTPUT:/path/to/sources_*.txt` at the end. Save this path — you'll need it for the downloader.

**Show the user the top 10-15 URLs** from the output file before downloading. Let them confirm or remove any that look off-topic. The URL list file has `# Score: X | Title` comments above each URL — use these to present the list clearly.

## Step 2 — Download: Fetch files

Install dependencies if needed:
```bash
pip install requests beautifulsoup4 --break-system-packages -q
# Optional for JS-heavy pages:
pip install selenium webdriver-manager --break-system-packages -q
```

Run the downloader with the scout's URL list:

```bash
python <skill_dir>/scripts/download_cipaf.py \
  --save-folder "<save_folder>" \
  --urls-file "<path_to_sources_*.txt>"
```

Or with specific known URLs (useful if user provides their own list):

```bash
python <skill_dir>/scripts/download_cipaf.py \
  --save-folder "<save_folder>" \
  --urls "https://url1.com" "https://url2.com" ...
```

The script organizes files into subfolders by source domain automatically (ONE/, CEPAL/, MEPYD/, etc.).

Note: Some government sites use heavy JavaScript rendering. If Selenium isn't available, those pages will be skipped — the script logs a clear warning. Static pages will still be downloaded normally.

After downloading, show the user a count of files per source folder:
```bash
for dir in <save_folder>/*/; do echo "$dir: $(ls $dir | wc -l) files"; done
```

## Step 3 — Triage: Build the inventory

Install dependencies if needed:
```bash
pip install pymupdf openpyxl pandas --break-system-packages -q
```

Run the triage tool:

```bash
python <skill_dir>/scripts/triage_cipaf.py \
  --folder "<save_folder>" \
  --topic-slug "<topic_slug>"
```

This scans every PDF and Excel file, matches content against 13 keyword categories, assigns a relevance score, and produces `_INVENTARIO_<TOPIC_SLUG>.xlsx` in the save folder.

Relevance thresholds:
- 🟢 HIGH = 4+ keyword categories matched
- 🟡 MEDIUM = 2-3 categories matched
- 🔴 LOW = 0-1 categories matched

The output Excel has two sheets:
- **Inventario** — one row per file, color-coded, with category checkmarks and a Notas column for manual notes
- **Resumen** — summary counts by relevance level

After triage, share the `_INVENTARIO_*.xlsx` file with the user so they can review it before organizing.

**Custom keywords (optional):** If the topic is quite different from social/poverty research, offer to generate a custom keywords JSON file. Ask the user to describe the main thematic categories they care about, then create a JSON file like:
```json
{
  "Category Name": ["keyword1", "keyword2", ...],
  ...
}
```
Pass it with `--keywords-json /path/to/keywords.json`.

## Step 4 — Organize: Sort by relevance

Run the organizer:

```bash
python <skill_dir>/scripts/organize_inventory.py \
  --folder "<save_folder>"
```

This reads the `_INVENTARIO_*.xlsx`, moves files into:
```
HIGH/SOURCE/
MEDIUM/SOURCE/
LOW/SOURCE/
UNCATALOGUED/    ← files not in the inventory
```

Then creates `INVENTARIO_ORGANIZADO.zip` containing the HIGH/MEDIUM/LOW structure.

## Final step — Share results

After the full pipeline completes:

1. Share the `_INVENTARIO_*.xlsx` file as a `computer://` link
2. Share the `INVENTARIO_ORGANIZADO.zip` file as a `computer://` link
3. Give the user a brief summary:
   - Total files downloaded
   - HIGH / MEDIUM / LOW counts
   - Any pages that were skipped (JS sites without Selenium)
   - Any uncatalogued files

## Running individual steps

If the user only wants one step, run just that script. Common partial runs:
- "Just triage the files I already have" → Step 3 only
- "Organize using the inventory I already built" → Step 4 only
- "Re-run the scout with different queries" → Step 1 only

## Reusing the pipeline for new topics

The pipeline is fully topic-agnostic. To use for any new topic:
1. Change `--topic-label` and `--topic-slug`
2. Generate new search queries for the topic (step 1)
3. Point to the new save folder
4. Optionally provide `--keywords-json` if the default social-research keywords don't fit

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: duckduckgo_search` | `pip install duckduckgo-search --break-system-packages` |
| `ModuleNotFoundError: fitz` | `pip install pymupdf --break-system-packages` |
| Scout returns 0 results | Check internet. Try simpler queries. DuckDuckGo may rate-limit — wait 30s and retry |
| Download fails on JS pages | Install Selenium: `pip install selenium webdriver-manager --break-system-packages` |
| Zip creation fails | The script writes zip to `/tmp/` first then copies — check disk space |