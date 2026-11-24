"""Build the public site from the register: index.html (use cases), alignment.html (SST-10) and data-flow.html.

    python build/site.py _site

The page designs are build/templates/use_case_map.html and use_case_alignment.html (kept in step with the Senthil
Station project's scripts/); upload.html is the "Upload sheet" panel added to both pages.
"""

from __future__ import annotations

import html
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from register import HERE, REPO, RULES, page_data

TEMPLATES = HERE / "templates"
REPO_NAME = "CieloEpic/senthil-station-use-cases"
LINKS = {"__HREF_USECASES__": "./", "__HREF_ALIGN__": "alignment.html", "__HREF_FLOW__": "data-flow.html"}
IST = timezone(timedelta(hours=5, minutes=30))


def page(template: str, data: dict, panel: str) -> str:
    out = (TEMPLATES / template).read_text(encoding="utf-8")
    for k, v in LINKS.items():
        out = out.replace(k, v)
    out = (out.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
              .replace("__GENERATED__", html.escape(datetime.now(IST).strftime("%d %b %Y, %H:%M IST"))))
    return out.replace("</body>", panel + "\n</body>", 1)


def main() -> None:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "_site")
    dest.mkdir(parents=True, exist_ok=True)
    data = page_data()
    panel = ((TEMPLATES / "upload.html").read_text(encoding="utf-8")
             .replace("__RULES__", json.dumps(RULES, ensure_ascii=False).replace("</", "<\\/"))
             .replace("__REPO__", REPO_NAME))
    (dest / "index.html").write_text(page("use_case_map.html", data, panel), encoding="utf-8")
    (dest / "alignment.html").write_text(page("use_case_alignment.html", data, panel), encoding="utf-8")
    shutil.copy(REPO / "static" / "data-flow.html", dest / "data-flow.html")
    (dest / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(data['cases'])} use cases in {len(data['epics'])} epics -> {dest}")


if __name__ == "__main__":
    main()
