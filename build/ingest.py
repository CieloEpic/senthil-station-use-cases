"""Add the sheets dropped into uploads/ to the use-case register, then move them to uploads/processed/.

Each sheet (.xlsx or .csv, any reasonable column names, the header row anywhere near the top) is read row by row:
a use case the register already has (same UC ID, or the same scenario text) is updated, a new one gets the next free
UC / DL / AG / OUT / AT numbers and is categorised (epic, AIoT live check, ESG pillar, GRI, twin relationship) by
register.categorize. Runs on GitHub (.github/workflows/publish.yml) or locally: python build/ingest.py
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

from register import REPO, RULES, merge, norm

UPLOADS = REPO / "uploads"
DONE = UPLOADS / "processed"
TITLE_ALIASES = set(RULES["headers"]["scenario"] + RULES["headers"]["use_case"])


def grid(path: Path) -> list[list[str]]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            return [list(r) for r in csv.reader(f)]
    from openpyxl import load_workbook          # only needed for Excel files
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        out: list[list[str]] = []
        for ws in wb.worksheets:                # the first sheet that has a title column wins
            rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
            if header_at(rows) is not None:
                return rows
            out = out or rows
        return out
    finally:
        wb.close()


def header_at(rows: list[list[str]]) -> int | None:
    for i, r in enumerate(rows[:15]):
        if any(norm(c) in TITLE_ALIASES for c in r):
            return i
    return None


def records(path: Path) -> list[dict[str, str]]:
    rows = grid(path)
    h = header_at(rows)
    if h is None:
        print(f"  {path.name}: no use-case title column found, skipped")
        return []
    head = rows[h]
    return [dict(zip(head, r)) for r in rows[h + 1:] if any(str(c).strip() for c in r)]


def main() -> None:
    files = sorted(p for p in UPLOADS.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".xlsx") and not p.name.startswith("."))
    if not files:
        print("no uploads to process")
        return
    DONE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for path in files:
        result = merge(records(path), path.name, stamp)
        print(f"  {path.name}: added {result['added'] or 'none'}, updated {result['updated'] or 'none'}, "
              f"new epics {result['new_epics'] or 'none'}")
        shutil.move(str(path), DONE / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{path.name}")


if __name__ == "__main__":
    main()
