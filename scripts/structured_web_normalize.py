"""FREE-ONLY source-backed web-research deduplication; offline, no provider calls."""

from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()


def _url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    p = urlparse(value.strip())
    return value.strip() if p.scheme in {"http", "https"} and p.netloc else None


def _capacity(row: dict[str, Any]) -> tuple[float, str] | None:
    val = row.get("capacity_gwh_per_year")
    basis = _norm(row.get("capacity_basis"))
    if not basis or isinstance(val, bool):
        return None
    try:
        number = float(val)
    except (ValueError, TypeError):
        return None
    if not (0 <= number < float("inf")):
        return None
    return number, basis


def normalize_projects(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Do not merge uncertain identities or sum unlike/conflicting capacities."""
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError("Each source record must be an object")
        identity = tuple(_norm(row.get(k)) for k in
                         ("company", "country", "location", "facility_type", "chemistry_scope"))
        project_id = _norm(row.get("project_id"))
        complete = all(identity)
        key = identity + (project_id,) if complete else ("manual_identity", idx)
        if key not in groups:
            groups[key] = {
                "company": row.get("company"), "country": row.get("country"),
                "location": row.get("location"), "facility_type": row.get("facility_type"),
                "chemistry_scope": row.get("chemistry_scope"),
                "project_id": row.get("project_id"), "sources": [],
                "events": [], "capacity_gwh_per_year": [],
                "first_announced_date": None, "review_reasons": [],
                "source_record_count": 0,
            }
        project = groups[key]
        project["source_record_count"] += 1
        reasons = project["review_reasons"]
        if not complete:
            if not _norm(row.get("location")) and "unknown_location_no_automatic_merge" not in reasons:
                reasons.append("unknown_location_no_automatic_merge")
            if "incomplete_project_identity" not in reasons:
                reasons.append("incomplete_project_identity")
        source = _url(row.get("source_url"))
        if not source:
            if "missing_source_url" not in reasons:
                reasons.append("missing_source_url")
        elif source not in project["sources"]:
            project["sources"].append(source)
        date, event_type = row.get("event_date"), _norm(row.get("event_type"))
        event = {"date": date, "type": event_type or None,
                 "source_url": source, "status": row.get("status")}
        if event not in project["events"]:
            project["events"].append(event)
        if (event_type == "announcement" and isinstance(date, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)):
            prev = project["first_announced_date"]
            project["first_announced_date"] = min(prev, date) if prev else date
        capacity = _capacity(row)
        if capacity is None:
            if "capacity_not_verified" not in reasons:
                reasons.append("capacity_not_verified")
        elif not any(c["value"] == capacity[0] and c["basis"] == capacity[1]
                     for c in project["capacity_gwh_per_year"]):
            project["capacity_gwh_per_year"].append({
                "value": capacity[0], "basis": capacity[1], "source_url": source,
            })
    for project in groups.values():
        caps = project["capacity_gwh_per_year"]
        if len({(c["value"], c["basis"]) for c in caps}) > 1:
            project["review_reasons"].append("conflicting_capacity_reports")
        project["sources"].sort()
        project["events"].sort(key=lambda v: (str(v["date"]), str(v["type"]), str(v["source_url"])))
        caps.sort(key=lambda v: (v["basis"], v["value"]))
        project["review_reasons"].sort()
    projects = sorted(groups.values(), key=lambda v: (
        _norm(v["company"]), _norm(v["country"]), _norm(v["location"]),
        _norm(v["facility_type"]), _norm(v["project_id"])))
    return {
        "summary": {"source_records": len(rows), "distinct_projects": len(projects),
                    "requiring_manual_review": sum(bool(p["review_reasons"]) for p in projects)},
        "projects": projects,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline source-backed research deduplication")
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        parser.error("Input root must be a JSON list")
    data = normalize_projects(rows)
    args.output_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
    print(json.dumps(data["summary"]))
