# Senthil Station · Use Cases, Epics and Team Alignment

Live site: https://cieloepic.github.io/senthil-station-use-cases/

| Page | What it shows |
| --- | --- |
| [Use cases and epics](https://cieloepic.github.io/senthil-station-use-cases/) | Each use case traced through its epic, user story / task, implementation & evidence, and demonstration / validation |
| [Team alignment (SST-10)](https://cieloepic.github.io/senthil-station-use-cases/alignment.html) | What the Senthil Station digital twin, AIoT and ESG each do for every use case |
| [Data flow and ERD (SST-12)](https://cieloepic.github.io/senthil-station-use-cases/data-flow.html) | How data moves from the devices to decisions, and the database model |

## Adding use cases

Use the **Upload sheet** tab on the right of the site: drop an Excel or CSV file, check how each new use case was
categorised, then **Save to register**. Or drop the sheet straight into [`uploads/`](uploads/) on GitHub.

Either way the workflow in `.github/workflows/publish.yml` then:

1. reads the sheet (any reasonable column names; a title or scenario column is enough),
2. updates use cases the register already has and adds new ones with the next UC / DL / AG / OUT / AT numbers,
3. sorts each new one into its epic (or creates the epic named in the sheet), its AIoT live check, its ESG pillar(s)
   and GRI disclosure, and its digital-twin relationship, using `build/rules.json`,
4. saves the register (`register/*.csv`, with a change log) and republishes the pages, about two minutes later.

Rows it cannot place in an epic go to **E00 · Needs review**.

## Layout

| Path | Contents |
| --- | --- |
| `register/` | The use-case register: `use_cases.csv`, `epics.csv`, `use_case_alignment.csv`, `changelog.csv` |
| `uploads/` | Sheets waiting to be added; processed sheets move to `uploads/processed/` |
| `build/` | `ingest.py` (sheets → register), `site.py` (register → pages), `register.py`, `rules.json`, page templates |
| `static/` | The hand-made data flow and ERD page |
