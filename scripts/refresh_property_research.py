"""Active arena-first refresh entry point; reuse legacy parsers, not legacy scoring.

Discovery is deliberately broader than qualification. No HTTP response, acreage,
county name, or estimated road distance establishes flatness or a 45-minute route.
The browser evaluates every record against data/property-search-brief.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data/charlotte_polo_properties.csv"
BRIEF_PATH = ROOT / "data/property-search-brief.json"
RESEARCH_COLUMNS = [
    "Terrain Status", "Terrain Evidence", "Terrain Checked At", "Terrain Notes",
    "Usable Flat Acres", "Arena Fit", "Grass Fit", "Layout Evidence", "Layout Checked At",
    "Corridor Status", "Corridor Evidence", "Corridor Checked At",
    "Verified Drive Minutes", "Drive Origin", "Drive Evidence", "Drive Checked At",
    "Expansion Status", "Expansion Evidence", "Expansion Checked At",
]
CORE_COLUMNS = ["ID", "Dashboard Include", "Property Name", "Address / Property", "City", "County", "State",
                "Acres", "List Price", "Source", "Property URL", "Source URL", "Listing Notes", "Status",
                "Latitude", "Longitude", "Last Researched", "Listing Verified At", "Listing Verification Status",
                "Listing External ID", "Scrape Source Name", "Scrape Source URL", "Corridor", "Next Due Diligence"]
AUDIT_FIELDS = {"Last Researched", "Listing Verified At", "Listing Verification Status"}


def numeric(value: Any) -> float | None:
    raw = str(value if value is not None else "").strip().replace(",", "").replace("$", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return None
    number = float(raw)
    return number if math.isfinite(number) else None


def source_url(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlparse(raw)
        return raw if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def row_key(row: dict[str, str]) -> str:
    return source_url(row.get("Property URL") or row.get("Source URL")).rstrip("/").lower() or row.get("ID", "")


def is_audit(row: dict[str, str]) -> bool:
    return bool(re.fullmatch(r"SEARCH-.*-AUDIT", row.get("ID", ""))) or row.get("Priority", "").lower() == "audit"


def load_data(path: Path = DATA_PATH) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns):
            raise ValueError("Duplicate CSV headers")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV contains an incomplete or overlong row")
    return columns, rows


def validate(rows: list[dict[str, str]]) -> list[str]:
    errors, seen = [], set()
    for row in rows:
        if is_audit(row):
            continue
        key = row_key(row)
        label = row.get("ID") or row.get("Property Name") or "Unnamed row"
        if not key or key in seen:
            errors.append(f"{label}: missing or duplicate property identity")
        seen.add(key)
        if not source_url(row.get("Property URL") or row.get("Source URL")):
            errors.append(f"{label}: missing HTTP(S) listing/source URL")
        acres = numeric(row.get("Acres"))
        if row.get("Acres") and (acres is None or acres <= 0):
            errors.append(f"{label}: invalid acreage")
        # Historical sub-minimum and off-corridor rows are valid archived records.
        # They must not be deleted or promoted simply to make validation pass.
    return errors


def discovery_candidate(candidate: Any, brief: dict[str, Any]) -> bool:
    acres = numeric(candidate.acres)
    if acres is None or acres < brief["minimumAcres"]:
        return False
    lat = numeric(candidate.latitude)
    if lat is not None and not brief["southernLatitude"] <= lat <= brief["origin"]["latitude"]:
        return False
    county = str(candidate.county or "").lower()
    if county and county not in {value.lower() for value in brief["discoveryCounties"]}:
        return False
    # A target-market search page is a discovery lead only. Missing coordinates,
    # routing and topography stay unknown, never inferred from crow-flight miles.
    return True


def apply_listing(existing: dict[str, str], candidate: Any, source: dict[str, str], now: datetime) -> dict[str, str]:
    row = existing.copy()
    url = source_url(candidate.url)
    if not url:
        raise ValueError("Candidate has no safe source URL")
    new = not existing
    row.setdefault("ID", "POLO-" + hashlib.sha256(url.encode()).hexdigest()[:12])
    row.setdefault("Dashboard Include", "Yes")
    row.setdefault("Status", "Availability unverified")
    row.setdefault("Corridor", "I-77 south — proximity unverified")
    row.setdefault("Next Due Diligence", "Confirm contiguous flat land; draw arena/support and grass layouts; verify southern I-77 access and an Uptown Charlotte route within 45 minutes; check permitted use, drainage, utilities and availability.")
    # Preserve analyst research and all unknown/custom CSV columns.
    changed_geometry = False
    for key, value in [("Acres", candidate.acres), ("List Price", candidate.price), ("Latitude", candidate.latitude), ("Longitude", candidate.longitude)]:
        number = numeric(value)
        if number is not None and (number > 0 or key in {"Latitude", "Longitude"}):
            previous = numeric(row.get(key))
            if not new and key in {"Acres", "Latitude", "Longitude"} and previous is not None and not math.isclose(number, previous, abs_tol=0.00001):
                changed_geometry = True
            row[key] = f"{number:g}"
    if changed_geometry:
        for key in ["Terrain Status", "Arena Fit", "Grass Fit", "Corridor Status", "Expansion Status"]:
            row[key] = "unverified"
        row["Verified Drive Minutes"] = ""
        row["Usable Flat Acres"] = ""
        # Keep source links and review dates as historical evidence, but revoke
        # pass statuses until an analyst resolves the changed parcel facts.
    for key, value in [("Property Name", candidate.title or candidate.address), ("Address / Property", candidate.address),
                       ("City", candidate.city), ("County", candidate.county), ("State", candidate.state)]:
        if value:
            row[key] = str(value)
    if candidate.description:
        row["Listing Notes"] = str(candidate.description)[:4000]
    if new:
        row.update({"Terrain Status":"unverified", "Arena Fit":"unverified", "Grass Fit":"unverified", "Corridor Status":"unverified", "Expansion Status":"unverified"})
    row.update({"Property URL":url, "Source URL":url, "Source":candidate.source or source["source"],
                "Listing External ID":str(candidate.external_id or row.get("Listing External ID", "")),
                "Last Researched":now.date().isoformat(), "Listing Verified At":now.isoformat().replace("+00:00", "Z"),
                "Listing Verification Status":"Public source parsed; current availability and polo suitability remain unverified."})
    # A tracked URL is not falsely attributed to an arbitrary market search.
    if source.get("url"):
        row["Scrape Source Name"], row["Scrape Source URL"] = source["name"], source["url"]
    return row


def meaningful(row: dict[str, str]) -> dict[str, str]:
    return {key:value for key,value in row.items() if key not in AUDIT_FIELDS and value != ""}


def write_data(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    fields = list(dict.fromkeys(columns + CORE_COLUMNS + RESEARCH_COLUMNS + [key for row in rows for key in row]))
    temporary = path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run_refresh(rows: list[dict[str, str]], brief: dict[str, Any], parser: Any, limit: int = 80, pause: float = 0.8) -> tuple[list[dict[str,str]], dict[str,Any]]:
    now = datetime.now(timezone.utc)
    summary: dict[str,Any] = {"brief_version":brief["version"], "sources_attempted":0, "sources_succeeded":0,
        "sources_failed":0, "listing_pages_attempted":0, "listing_pages_failed":0, "listing_urls_discovered":0,
        "rows_added":0, "rows_updated":0, "csv_written":False, "source_attempts":[]}
    # Preserve every old row. Out-of-brief rows are archived by the UI rules.
    result = [row.copy() for row in rows]
    indexes = {row_key(row):index for index,row in enumerate(result) if not is_audit(row)}
    candidates: dict[str,dict[str,str]] = {}
    for row in rows:
        url = source_url(row.get("Property URL") or row.get("Source URL"))
        if not is_audit(row) and url and parser.is_listing_url(url):
            candidates[url] = {"source":row.get("Source", ""), "name":"Tracked listing", "url":""}
    for source in brief["sources"]:
        page = parser.fetch_url(source["url"])
        summary["sources_attempted"] += 1
        summary["sources_succeeded" if page.ok else "sources_failed"] += 1
        links = parser.extract_listing_links(page.text, page.url) if page.ok else []
        summary["source_attempts"].append({"name":source["name"], "url":source["url"], "ok":page.ok, "status":page.status, "discovered_links":len(links), "error":page.error})
        for link in sorted(links):
            if source_url(link) and link not in candidates:
                candidates[link] = source
                summary["listing_urls_discovered"] += 1
        time.sleep(pause)
    summary["listing_limit_reached"] = len(candidates) > limit
    for url,source in list(candidates.items())[:limit]:
        page = parser.fetch_url(url)
        summary["listing_pages_attempted"] += 1
        if not page.ok:
            summary["listing_pages_failed"] += 1
            time.sleep(pause)
            continue
        candidate = parser.parse_listing_page(page, source=source["source"])
        key = url.rstrip("/").lower()
        index = indexes.get(key)
        # Parsing success does not establish site suitability or source freshness.
        if not candidate.verified or (index is None and not discovery_candidate(candidate,brief)):
            time.sleep(pause)
            continue
        updated = apply_listing(result[index] if index is not None else {},candidate,source,now)
        if index is None:
            indexes[row_key(updated)] = len(result)
            result.append(updated)
            summary["rows_added"] += 1
        elif meaningful(updated) != meaningful(result[index]):
            result[index] = updated
            summary["rows_updated"] += 1
        time.sleep(pause)
    return result,summary


def main() -> None:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--validate-only", action="store_true")
    arg.add_argument("--dry-run", action="store_true")
    arg.add_argument("--summary-path", type=Path)
    arg.add_argument("--max-listings", type=int, default=80)
    arg.add_argument("--allow-source-failures", action="store_true")
    args = arg.parse_args()
    brief = json.loads(BRIEF_PATH.read_text())
    columns,rows = load_data()
    errors = validate(rows)
    if errors:
        raise SystemExit("CSV validation failed:\n" + "\n".join(errors))
    if args.validate_only:
        print(f"Validated {len(rows)} retained research/archive rows; active brief is {brief['minimumAcres']}+ acres, flat land, I-77 south, maximum {brief['maximumDriveMinutes']} minutes.")
        return
    if args.max_listings <= 0:
        arg.error("--max-listings must be positive")
    # Existing dependency-free source parsers remain reusable. Never call their
    # old apply_candidate, is_target_candidate, scoring, normalize_row or main.
    import update_properties as parser
    updated,summary = run_refresh(rows,brief,parser,args.max_listings)
    summary["dry_run"] = args.dry_run
    errors = validate(updated)
    degraded = summary["sources_failed"] / max(1,summary["sources_attempted"]) >= 0.75
    all_listings_failed = summary["listing_pages_attempted"] > 0 and summary["listing_pages_failed"] == summary["listing_pages_attempted"]
    failed = bool(errors) or ((degraded or all_listings_failed) and not args.allow_source_failures)
    summary["validation_errors"] = errors
    summary["degraded"] = degraded or all_listings_failed
    summary["write_blocked"] = failed
    if not failed and not args.dry_run and (summary["rows_added"] or summary["rows_updated"]):
        write_data(DATA_PATH,columns,updated)
        summary["csv_written"] = True
    output = json.dumps(summary,indent=2)
    print(output)
    if args.summary_path:
        args.summary_path.write_text(output + "\n", encoding="utf-8")
    if failed:
        raise SystemExit("Refresh failed/degraded or invalid; original CSV retained. Review the summary; no successful refresh is implied.")


if __name__ == "__main__":
    main()
