import csv
import re
from datetime import datetime
from pathlib import Path

DATA_PATH = Path("data/charlotte_polo_properties.csv")

TARGET_COLUMNS = [
    "ID",
    "Dashboard Slug",
    "Dashboard Include",
    "Priority",
    "Recommendation Tier",
    "Weighted Polo Score",
    "Corridor",
    "Corridor Fit",
    "Address / Property",
    "City",
    "County",
    "State",
    "Acres",
    "List Price",
    "Price / Acre",
    "Status",
    "Source",
    "Listing Link Label",
    "Source URL",
    "Geocode Query",
    "Geo Status",
    "Research Confidence",
    "Listing Notes",
    "Polo / Investor Notes",
    "Investor Narrative",
    "Est. Drive Min to Charlotte",
    "Est. Min to I-77",
    "Location Score",
    "Acreage Score",
    "Field / Terrain Signal",
    "Price Efficiency Score",
    "Expansion / Assemblage Score",
    "Zoning / Entitlement Risk Score",
    "Access / Frontage Score",
    "Next Due Diligence",
    "Last Researched",
    "Property Name",
    "Property URL",
    "Map URL",
    "Latitude",
    "Longitude",
    "Drive Time From Charlotte",
    "Miles From Charlotte",
]


def clean_money(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"[^0-9.]", "", text)

    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def clean_number(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"[^0-9.]", "", text)

    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def format_money(value):
    if value is None:
        return ""

    return f"${value:,.0f}"


def normalize_row(row):
    normalized = {column: row.get(column, "") for column in TARGET_COLUMNS}

    acres = clean_number(normalized.get("Acres"))
    price = clean_money(normalized.get("List Price"))

    if acres and price and not str(normalized.get("Price / Acre", "")).strip():
        normalized["Price / Acre"] = format_money(price / acres)

    if not normalized.get("Property URL") and normalized.get("Source URL"):
        normalized["Property URL"] = normalized["Source URL"]

    if not normalized.get("Listing Link Label") and normalized.get("Property URL"):
        normalized["Listing Link Label"] = "View Listing"

    if not normalized.get("Dashboard Include"):
        normalized["Dashboard Include"] = "Yes"

    if not normalized.get("Status"):
        normalized["Status"] = "Active"

    if not normalized.get("Last Researched"):
        normalized["Last Researched"] = datetime.now().strftime("%Y-%m-%d")

    return normalized


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}")

    with DATA_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    cleaned_rows = [normalize_row(row) for row in rows]

    with DATA_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TARGET_COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"Updated {DATA_PATH}")
    print(f"Rows: {len(cleaned_rows)}")
    print(f"Columns: {len(TARGET_COLUMNS)}")


if __name__ == "__main__":
    main()