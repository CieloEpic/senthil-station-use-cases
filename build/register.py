"""The use-case register (register/*.csv): reading, writing, categorising new rows and building the page data.

The categorising rules are in rules.json, shared with the upload panel on the page so both sort a new use case the
same way: its epic, its AIoT live check, its ESG pillar(s) and GRI disclosure, and its digital-twin relationship.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
REG = REPO / "register"
RULES = json.loads((HERE / "rules.json").read_text(encoding="utf-8"))

USE_CASE_COLS = ["uc_id", "epic_id", "scenario", "use_case", "assets", "phase", "detection_id", "detection_inputs",
                 "detection_logic", "data_analysis", "twin_relationship", "agent_id", "agent_action", "outcome_id",
                 "outcome", "outcome_metric", "outcome_measure", "proposed_acceptance", "limitation", "test_id",
                 "test_case", "owner"]
EPIC_COLS = ["epic_id", "epic", "personas"]
ALIGN_COLS = ["uc_id", "aiot_check", "aiot_signals", "aiot_scenario", "esg_pillar", "esg_metric", "gri", "data_today"]
CHANGE_COLS = ["date", "file", "added", "updated", "new_epics"]
REVIEW_EPIC = ("E00", "Needs review", "")


def read(name: str) -> list[dict[str, str]]:
    path = REG / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def write(name: str, rows: list[dict[str, str]], cols: list[str]) -> None:
    REG.mkdir(parents=True, exist_ok=True)
    with open(REG / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def has(text: str, word: str) -> bool:
    """Short keywords (3 letters or fewer) match whole words only, so 'ac' does not match 'account'."""
    if len(word) <= 3:
        return re.search(rf"\b{re.escape(word)}\b", text) is not None
    return word in text


def score(text: str, words: list[str]) -> int:
    return sum(1 for w in words if has(text, w))


def num(uid: str) -> int:
    m = re.search(r"(\d+)$", uid or "")
    return int(m.group(1)) if m else 0


def categorize(row: dict[str, str], epics: list[dict[str, str]]) -> dict[str, str]:
    """Fill in what the row leaves blank: epic, AIoT check, ESG pillar(s), metric, GRI and twin relationship."""
    text = " ".join(str(row.get(k, "")) for k in ("scenario", "use_case", "assets", "detection_logic", "detection_inputs",
                                                   "agent_action", "outcome", "outcome_metric", "epic", "domain")).lower()
    out: dict[str, str] = {}
    if not row.get("epic_id"):
        best = max(RULES["epics"].items(), key=lambda kv: score(text, kv[1]))
        out["epic_id"] = best[0] if score(text, best[1]) else ""
    domain = str(row.get("domain", "")).lower()
    if not row.get("aiot_check"):
        if score(text, RULES["aiot_triggers"]) or "aiot" in domain:
            name, words = max(RULES["aiot_checks"], key=lambda c: score(text, c[1]))
            out["aiot_check"] = name if score(text, words) else "New AIoT rule"
    if not row.get("esg_pillar"):
        ps = [p for p, words in RULES["esg"].items() if score(text, words)]
        if not ps and "esg" in domain:
            ps = ["E"]
        out["esg_pillar"] = "+".join(ps)
    pillars = (row.get("esg_pillar") or out.get("esg_pillar", "")).split("+")
    if not row.get("esg_metric") and pillars[0]:
        out["esg_metric"] = row.get("outcome_metric") or RULES["esg_metric"].get(pillars[0], "")
    if not row.get("gri") and "E" in pillars:
        out["gri"] = next((g for g, words in RULES["gri"] if score(text, words)), "")
    if not row.get("twin_relationship"):
        out["twin_relationship"] = next((t for t, words in RULES["twin"] if not words or score(text, words)), "Space contains Asset")
    if not row.get("phase") or row.get("phase") not in RULES["phases"]:
        out["phase"] = next((p for p in RULES["phases"] if norm(p) == norm(row.get("phase", ""))), RULES["default_phase"])
    if not row.get("data_today"):
        out["data_today"] = "Planned"
    return out


def map_headers(raw: dict[str, str]) -> dict[str, str]:
    """A sheet row with any reasonable column names -> register field names."""
    alias: dict[str, str] = {}
    for field, names in RULES["headers"].items():
        for a in names:
            alias.setdefault(a, field)          # the first rule wins, as in the upload panel
    out: dict[str, str] = {}
    for k, v in raw.items():
        field = alias.get(norm(k))
        val = "" if v is None else str(v).strip()
        if field and val and not out.get(field):
            out[field] = val
    derived = []                                # filled in from another column: never overwrites the register
    if not out.get("scenario") and out.get("use_case"):
        out["scenario"] = out["use_case"]
        derived.append("scenario")
    if not out.get("use_case") and out.get("scenario"):
        out["use_case"] = " ".join(out["scenario"].split()[:5])
        derived.append("use_case")
    out["_derived"] = " ".join(derived)
    return out


def merge(rows: list[dict[str, str]], source: str, date: str) -> dict[str, list[str]]:
    """Add new use cases (and new epics) from sheet rows to the register; update ones it already has."""
    cases, epics, align = read("use_cases.csv"), read("epics.csv"), read("use_case_alignment.csv")
    by_id = {c["uc_id"]: c for c in cases}
    by_text = {norm(c["scenario"]): c for c in cases}
    al = {a["uc_id"]: a for a in align}
    added, updated, new_epics = [], [], []
    next_uc = max([num(c["uc_id"]) for c in cases] + [0]) + 1
    next_ep = max([num(e["epic_id"]) for e in epics] + [0]) + 1

    def epic_for(r: dict[str, str]) -> str:
        nonlocal next_ep
        if r.get("epic_id") and any(e["epic_id"] == r["epic_id"] for e in epics):
            return r["epic_id"]
        name = r.get("epic", "")
        if name:
            hit = next((e for e in epics if norm(e["epic"]) == norm(name)), None)
            if hit:
                return hit["epic_id"]
            eid = f"E{next_ep:02d}"
            next_ep += 1
            epics.append({"epic_id": eid, "epic": name, "personas": r.get("personas", "")})
            new_epics.append(eid)
            return eid
        return ""

    for raw in rows:
        r = map_headers(raw)
        if not r.get("scenario"):
            continue
        hit = by_id.get(r.get("uc_id", "")) or by_text.get(norm(r["scenario"]))
        if hit:
            changed = False
            skip = {"uc_id", "owner", "epic_id", *r.get("_derived", "").split()}
            for k in USE_CASE_COLS:
                if k not in skip and r.get(k) and r[k] != hit.get(k, ""):
                    hit[k] = r[k]
                    changed = True
            a = al.setdefault(hit["uc_id"], {"uc_id": hit["uc_id"]})
            for k in ALIGN_COLS[1:]:
                if r.get(k) and r[k] != a.get(k, ""):
                    a[k] = r[k]
                    changed = True
            if changed:
                updated.append(hit["uc_id"])
            continue
        r["epic_id"] = epic_for(r)
        r.update({k: v for k, v in categorize(r, epics).items() if not r.get(k)})
        if not r["epic_id"]:
            if not any(e["epic_id"] == REVIEW_EPIC[0] for e in epics):
                epics.append(dict(zip(EPIC_COLS, REVIEW_EPIC)))
            r["epic_id"] = REVIEW_EPIC[0]
        uid = r.get("uc_id", "")
        if not re.fullmatch(r"UC-\d{3,}", uid) or uid in by_id:
            uid = f"UC-{next_uc:03d}"
        next_uc = max(next_uc, num(uid)) + 1
        n = uid.split("-")[1]
        case = {
            "uc_id": uid, "epic_id": r["epic_id"], "scenario": r["scenario"], "use_case": r.get("use_case", ""),
            "assets": r.get("assets", ""), "phase": r.get("phase", RULES["default_phase"]),
            "detection_id": f"DL-{n}", "detection_inputs": r.get("detection_inputs", ""),
            "detection_logic": r.get("detection_logic", "To be defined"), "data_analysis": "",
            "twin_relationship": r.get("twin_relationship", ""), "agent_id": f"AG-{n}",
            "agent_action": r.get("agent_action", "To be defined"), "outcome_id": f"OUT-{n}",
            "outcome": r.get("outcome", ""), "outcome_metric": r.get("outcome_metric", ""), "outcome_measure": "",
            "proposed_acceptance": r.get("proposed_acceptance", ""), "limitation": "", "test_id": f"AT-{n}",
            "test_case": r.get("test_case", "To be defined"), "owner": "",
        }
        cases.append(case)
        by_id[uid] = case
        by_text[norm(case["scenario"])] = case
        al[uid] = {"uc_id": uid, **{k: r.get(k, "") for k in ALIGN_COLS[1:]}}
        added.append(uid)

    if added or updated or new_epics:
        epics.sort(key=lambda e: num(e["epic_id"]))
        write("use_cases.csv", cases, USE_CASE_COLS)
        write("epics.csv", epics, EPIC_COLS)
        write("use_case_alignment.csv", [al[c["uc_id"]] for c in cases if c["uc_id"] in al], ALIGN_COLS)
        log = read("changelog.csv")
        log.insert(0, {"date": date, "file": source, "added": " ".join(added), "updated": " ".join(updated),
                       "new_epics": " ".join(new_epics)})
        write("changelog.csv", log, CHANGE_COLS)
    return {"added": added, "updated": updated, "new_epics": new_epics}


def lower_first(s: str) -> str:
    return s if s[1:2].isupper() else s[:1].lower() + s[1:]


def story(uc: dict[str, str], epic: dict[str, str]) -> str:
    who = lower_first(epic.get("personas", "") or "site operator")
    article = "an" if who[:1] in "aeiou" else "a"
    outcome = uc.get("outcome") or "a clear, measured outcome"
    return f"As {article} {who}, I want to know when {lower_first(uc['scenario'])}, so that I get {lower_first(outcome)}."


def page_data() -> dict:
    epics, cases, align = read("epics.csv"), read("use_cases.csv"), read("use_case_alignment.csv")
    by_id = {e["epic_id"]: e for e in epics}
    al = {a["uc_id"]: a for a in align}
    return {
        "epics": [{"id": e["epic_id"], "name": e["epic"], "personas": e.get("personas", "")} for e in epics],
        "cases": [{
            "id": c["uc_id"], "epic": c["epic_id"], "scenario": c["scenario"], "name": c["use_case"],
            "assets": c["assets"].replace(",", ", "), "phase": c["phase"],
            "story": story(c, by_id.get(c["epic_id"], {})), "agent_id": c["agent_id"], "agent": c["agent_action"],
            "detection_id": c["detection_id"], "detection": c["detection_logic"],
            "inputs": c["detection_inputs"].replace(",", ", "), "analysis": c["data_analysis"],
            "twin": c.get("twin_relationship", ""),
            "outcome_id": c["outcome_id"], "outcome": c["outcome"], "metric": c["outcome_metric"],
            "measure": c["outcome_measure"], "test_id": c["test_id"], "test": c["test_case"],
            "acceptance": c["proposed_acceptance"], "limitation": c["limitation"], "owner": "",
            "aiot": al.get(c["uc_id"], {}).get("aiot_check", ""),
            "aiot_signals": al.get(c["uc_id"], {}).get("aiot_signals", ""),
            "aiot_scenario": al.get(c["uc_id"], {}).get("aiot_scenario", ""),
            "esg": al.get(c["uc_id"], {}).get("esg_pillar", ""),
            "esg_metric": al.get(c["uc_id"], {}).get("esg_metric", ""),
            "gri": al.get(c["uc_id"], {}).get("gri", ""),
            "data_today": al.get(c["uc_id"], {}).get("data_today", "") or "Planned",
        } for c in cases],
        "changes": read("changelog.csv")[:10],
    }
