"""
CIPAF - Inventory Organizer
=============================
Reorganizes a research folder using an _INVENTARIO*.xlsx file.
Moves files into HIGH/MEDIUM/LOW -> Source subfolder structure.
Moves uncatalogued files to UNCATALOGUED/.
Creates INVENTARIO_ORGANIZADO.zip.

Usage:
    python organize_inventory.py --folder "/path/to/research/folder"
"""

import os
import glob
import shutil
import subprocess
import argparse
import pandas as pd
from pathlib import Path

parser = argparse.ArgumentParser(description="CIPAF Inventory Organizer")
parser.add_argument("--folder",   required=True, help="Research folder to organize")
parser.add_argument("--zip-name", default="INVENTARIO_ORGANIZADO.zip", help="Output zip filename")
args = parser.parse_args()

FOLDER   = args.folder
ZIP_NAME = args.zip_name

REL_MAP = {"🟢 HIGH": "HIGH", "🟡 MEDIUM": "MEDIUM", "🔴 LOW": "LOW"}

def find_inventory(folder: str) -> str:
    matches = glob.glob(os.path.join(folder, "_INVENTARIO*.xlsx"))
    if not matches:
        raise FileNotFoundError(f"No _INVENTARIO*.xlsx found in {folder}")
    return matches[0]

def main():
    inv_path = find_inventory(FOLDER)
    print(f"Reading inventory: {os.path.basename(inv_path)}")

    df = pd.read_excel(inv_path, sheet_name=0)

    # Print summary
    rel_counts = df["Relevancia"].value_counts()
    print(f"  Total: {len(df)} files")
    for rel, count in rel_counts.items():
        print(f"  {rel}: {count}")

    moved       = []
    not_found   = []
    seen_files  = set()

    for _, row in df.iterrows():
        archivo   = str(row["Archivo"]).strip()
        fuente    = str(row["Fuente"]).strip()
        relevance = str(row["Relevancia"]).strip()

        rel_folder = REL_MAP.get(relevance)
        if not rel_folder:
            continue

        file_key = (fuente, archivo)
        if file_key in seen_files:
            continue
        seen_files.add(file_key)

        src      = os.path.join(FOLDER, fuente, archivo)
        dest_dir = os.path.join(FOLDER, rel_folder, fuente)
        dest     = os.path.join(dest_dir, archivo)

        if os.path.exists(src):
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, dest)
            moved.append(f"{rel_folder}/{fuente}/{archivo}")
        else:
            not_found.append(f"{fuente}/{archivo}")

    # Handle uncatalogued files
    uncatalogued = []
    source_folders = [d for d in os.listdir(FOLDER)
                      if os.path.isdir(os.path.join(FOLDER, d))
                      and d not in ("HIGH", "MEDIUM", "LOW", "UNCATALOGUED")
                      and not d.startswith("_")]

    for src_folder in source_folders:
        src_path = os.path.join(FOLDER, src_folder)
        for fname in os.listdir(src_path):
            fpath = os.path.join(src_path, fname)
            if os.path.isfile(fpath):
                unc_dir = os.path.join(FOLDER, "UNCATALOGUED")
                os.makedirs(unc_dir, exist_ok=True)
                shutil.move(fpath, os.path.join(unc_dir, fname))
                uncatalogued.append(fname)

    # Try to clean up empty source folders
    for src_folder in source_folders:
        src_path = os.path.join(FOLDER, src_folder)
        try:
            if os.path.isdir(src_path) and not os.listdir(src_path):
                os.rmdir(src_path)
        except Exception:
            pass

    # Create zip
    zip_tmp = os.path.join("/tmp", ZIP_NAME)
    os.chdir(FOLDER)
    subprocess.run(["zip", "-r", zip_tmp, "HIGH/", "MEDIUM/", "LOW/", "-q"],
                   capture_output=True)
    if os.path.exists(zip_tmp):
        shutil.copy(zip_tmp, os.path.join(FOLDER, ZIP_NAME))
        zip_size_mb = os.path.getsize(os.path.join(FOLDER, ZIP_NAME)) / (1024*1024)
    else:
        zip_size_mb = 0

    print(f"\n✅ Done!")
    print(f"  Moved:        {len(moved)} files")
    print(f"  Not found:    {len(not_found)}")
    print(f"  Uncatalogued: {len(uncatalogued)} → moved to UNCATALOGUED/")
    print(f"  Zip:          {ZIP_NAME} ({zip_size_mb:.1f} MB)")

    rel_summary = {}
    for path in moved:
        rel = path.split("/")[0]
        rel_summary[rel] = rel_summary.get(rel, 0) + 1
    for rel, count in sorted(rel_summary.items()):
        print(f"  {rel}: {count} files")

    print(f"ORGANIZE_COMPLETE:{len(moved)} moved, {len(uncatalogued)} uncatalogued")


if __name__ == "__main__":
    main()