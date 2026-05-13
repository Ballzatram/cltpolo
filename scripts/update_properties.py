"""Update the investor property CSV from tracked listings and public search pages.

The script is intentionally dependency-free so it can run reliably from GitHub
Actions. It fetches only public pages, extracts durable listing identifiers and
investor-relevant fields when they are present in page markup, and merges those
findings into the existing research CSV.

Operational guardrails:
* source fetch failures are reported separately from "no new listings found";
* blocked/403-heavy refreshes fail by default instead of committing a misleading
  audit-only timestamp;
* audit-only CSV writes are skipped unless --allow-audit-only is supplied; and
* --dry-run prints the same summary without modifying the CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DATA_PATH = Path("data/charlotte_polo_properties.csv")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

UPTOWN_CHARLOTTE = (35.2271, -80.8431)
TARGET_MIN_ACRES = 50.0
TARGET_MIN_DRIVE_MIN = 35
TARGET_MAX_DRIVE_MIN = 55
REQUEST_TIMEOUT_SECONDS = 18
REQUEST_PAUSE_SECONDS = 0.8
FAILURE_STATUSES = {401, 403, 429, 500, 502, 503, 504}
AUDIT_ROW_IDS = {"SEARCH-100AC-AUDIT", "SEARCH-50AC-AUDIT"}

# Approximate I-77 interchange coordinates south of Charlotte. These are used as
# a transparent proximity signal; they never replace parcel-level diligence.
I77_REFERENCES = [
    ("I-77 Exit 90 / Carowinds", 35.1044, -80.9408),
    ("I-77 Exit 85 / SC-160", 35.0072, -80.9461),
    ("I-77 Exit 82 / Rock Hill", 34.9632, -80.9930),
    ("I-77 Exit 77 / US-21", 34.9055, -81.0255),
    ("I-77 Exit 73 / SC-901", 34.8353, -81.0277),
    ("I-77 Exit 65 / Richburg", 34.7210, -81.0240),
]

TARGET_COUNTIES = {
    "york county",
    "chester county",
    "lancaster county",
    "union county",
    "iredell county",
    "gaston county",
    "lincoln county",
    "cabarrus county",
    "stanly county",
    "rowan county",
    "cleveland county",
}

TARGET_CITIES = {
    "albemarle",
    "belmont",
    "catawba",
    "charlotte region",
    "chester",
    "china grove",
    "concord",
    "dallas",
    "denver",
    "edgemoor",
    "fort lawn",
    "fort mill",
    "gastonia",
    "hickory grove",
    "indian trail",
    "kannapolis",
    "lancaster",
    "lincolnton",
    "locust",
    "midland",
    "monroe",
    "mooresville",
    "mount pleasant",
    "norwood",
    "richburg",
    "rock hill",
    "rockwell",
    "salisbury",
    "sharon",
    "smyrna",
    "statesville",
    "troutman",
    "waxhaw",
    "weddington",
    "york",
}

SEARCH_MARKETS = [
    ("York County SC", "LandSearch", "https://www.landsearch.com/properties/york-county-sc/filter/50-minacres"),
    ("Chester County SC", "LandSearch", "https://www.landsearch.com/properties/chester-county-sc/filter/50-minacres"),
    ("Lancaster County SC", "LandSearch", "https://www.landsearch.com/properties/lancaster-county-sc/filter/50-minacres"),
    ("Union County NC", "LandSearch", "https://www.landsearch.com/properties/union-county-nc/filter/50-minacres"),
    ("Gaston County NC", "LandSearch", "https://www.landsearch.com/properties/gaston-county-nc/filter/50-minacres"),
    ("Lincoln County NC", "LandSearch", "https://www.landsearch.com/properties/lincoln-county-nc/filter/50-minacres"),
    ("Iredell County NC", "LandSearch", "https://www.landsearch.com/properties/iredell-county-nc/filter/50-minacres"),
    ("Cabarrus County NC", "LandSearch", "https://www.landsearch.com/properties/cabarrus-county-nc/filter/50-minacres"),
    ("Stanly County NC", "LandSearch", "https://www.landsearch.com/properties/stanly-county-nc/filter/50-minacres"),
    ("Rowan County NC", "LandSearch", "https://www.landsearch.com/properties/rowan-county-nc/filter/50-minacres"),
    ("Cleveland County NC", "LandSearch", "https://www.landsearch.com/properties/cleveland-county-nc/filter/50-minacres"),
    ("York County SC", "Land.com", "https://www.land.com/York-County-SC/all-land/50-100000-acres/"),
    ("Chester County SC", "Land.com", "https://www.land.com/Chester-County-SC/all-land/50-100000-acres/"),
    ("Lancaster County SC", "Land.com", "https://www.land.com/Lancaster-County-SC/all-land/50-100000-acres/"),
    ("Union County NC", "Land.com", "https://www.land.com/Union-County-NC/all-land/50-100000-acres/"),
    ("Gaston County NC", "Land.com", "https://www.land.com/Gaston-County-NC/all-land/50-100000-acres/"),
    ("Lincoln County NC", "Land.com", "https://www.land.com/Lincoln-County-NC/all-land/50-100000-acres/"),
    ("Cabarrus County NC", "Land.com", "https://www.land.com/Cabarrus-County-NC/all-land/50-100000-acres/"),
    ("York County SC", "LandWatch", "https://www.landwatch.com/south-carolina-land-for-sale/york-county/acres-over-50"),
    ("Chester County SC", "LandWatch", "https://www.landwatch.com/south-carolina-land-for-sale/chester-county/acres-over-50"),
    ("Lancaster County SC", "LandWatch", "https://www.landwatch.com/south-carolina-land-for-sale/lancaster-county/acres-over-50"),
    ("Union County NC", "LandWatch", "https://www.landwatch.com/north-carolina-land-for-sale/union-county/acres-over-50"),
    ("Gaston County NC", "LandWatch", "https://www.landwatch.com/north-carolina-land-for-sale/gaston-county/acres-over-50"),
    ("Lincoln County NC", "LandWatch", "https://www.landwatch.com/north-carolina-land-for-sale/lincoln-county/acres-over-50"),
    ("Charlotte region", "Realtor.com", "https://www.realtor.com/realestateandhomes-search/Charlotte_NC/type-land/lot-sqft-2178000"),
    ("Charlotte region", "Zillow", "https://www.zillow.com/charlotte-nc/land_type/?searchQueryState=%7B%22filterState%22%3A%7B%22lot%22%3A%7B%22min%22%3A2178000%7D%7D%7D"),
    ("Charlotte region", "LoopNet", "https://www.loopnet.com/search/land/charlotte-nc/for-sale/"),
    ("Charlotte region", "Crexi", "https://www.crexi.com/properties/NC/Charlotte/Land"),
]

SEARCH_SOURCES = [
    {
        "name": f"{source} {market} 35-55 min from Charlotte 50+ acres",
        "source": source,
        "url": url,
    }
    for market, source, url in SEARCH_MARKETS
]

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
    "Listing Verified At",
    "Listing External ID",
    "Listing Verification Status",
    "Nearest I-77 Reference",
    "Scrape Source Name",
    "Scrape Source URL",
]

URL_FIELDS = ("Property URL", "Source URL")


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None
    text: str
    error: str = ""


@dataclass
class ListingCandidate:
    url: str
    source: str = ""
    source_name: str = ""
    source_url: str = ""
    title: str = ""
    address: str = ""
    city: str = ""
    county: str = ""
    state: str = "SC"
    acres: float | None = None
    price: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str = ""
    external_id: str = ""
    verified: bool = False
    verification_status: str = "Discovered; verify with broker/source page"


@dataclass
class SourceAttempt:
    name: str
    source: str
    url: str
    ok: bool
    status: int | None
    discovered_links: int = 0
    error: str = ""

    @property
    def failed(self) -> bool:
        return not self.ok

    @property
    def blocked(self) -> bool:
        return self.status in {401, 403, 429} or bool(re.search(r"forbidden|blocked|captcha|rate", self.error, re.I))


@dataclass
class RefreshSummary:
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    sources_blocked: int = 0
    listing_urls_discovered: int = 0
    tracked_listing_urls: int = 0
    candidates_processed: int = 0
    rows_added: int = 0
    rows_updated: int = 0
    audit_only_changes: bool = False
    csv_written: bool = False
    dry_run: bool = False
    failure_rate: float = 0.0
    source_attempts: list[SourceAttempt] = field(default_factory=list)

    def finalize(self) -> None:
        self.sources_attempted = len(self.source_attempts)
        self.sources_succeeded = sum(1 for attempt in self.source_attempts if attempt.ok)
        self.sources_failed = self.sources_attempted - self.sources_succeeded
        self.sources_blocked = sum(1 for attempt in self.source_attempts if attempt.blocked)
        self.listing_urls_discovered = sum(attempt.discovered_links for attempt in self.source_attempts)
        self.failure_rate = (self.sources_failed / self.sources_attempted) if self.sources_attempted else 0.0


def clean_money(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    multiplier = 1
    if re.search(r"\bm\b|million", text, re.I):
        multiplier = 1_000_000
    elif re.search(r"\bk\b", text, re.I):
        multiplier = 1_000
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def clean_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^0-9.-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_money(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value:,.0f}"


def format_number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "property"


def stable_id(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8].upper()
    return f"AUTO-{digest}"


def normalize_url(value: str, base_url: str = "") -> str:
    raw = html.unescape(str(value or "").strip())
    if not raw or raw.startswith("#") or raw.lower().startswith(("mailto:", "tel:")):
        return ""
    if base_url:
        raw = urljoin(base_url, raw)
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw.split("#", 1)[0]


def fetch_url(url: str) -> FetchResult:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "CharlottePoloPropertyResearch/1.1 "
                "(+https://www.cltpolo.com/investors; public listing research)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=response.geturl(),
                ok=200 <= response.status < 400,
                status=response.status,
                text=response.read().decode(charset, errors="replace"),
            )
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        return FetchResult(url=url, ok=False, status=error.code, text=body, error=str(error))
    except (URLError, TimeoutError, OSError) as error:
        return FetchResult(url=url, ok=False, status=None, text="", error=str(error))


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_drive_minutes(miles: float | None) -> int | None:
    if miles is None:
        return None
    return round(max(18, miles * 1.28 + 8))


def nearest_i77_reference(lat: float | None, lng: float | None) -> tuple[str, int | None]:
    if lat is None or lng is None:
        return "Needs coordinates", None
    nearest = min(
        I77_REFERENCES,
        key=lambda item: haversine_miles(lat, lng, item[1], item[2]),
    )
    miles = haversine_miles(lat, lng, nearest[1], nearest[2])
    minutes = max(2, round(miles * 1.75 + 2))
    return f"{nearest[0]} ({miles:.1f} mi est.)", minutes


def walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def first_value(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).strip()
        if text:
            return html.unescape(re.sub(r"\s+", " ", text))
    return ""


def parse_jsonld_blocks(page_text: str) -> list[Any]:
    blocks = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_text,
        flags=re.I | re.S,
    ):
        raw = html.unescape(match.group(1).strip())
        if not raw:
            continue
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return blocks


def meta_content(page_text: str, *names: str) -> str:
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, page_text, flags=re.I | re.S)
            if match:
                return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())
    return ""


def extract_listing_links(page_text: str, base_url: str) -> list[str]:
    links = set()
    for match in re.finditer(r'<a\b[^>]+href=["\']([^"\']+)["\']', page_text, flags=re.I):
        url = normalize_url(match.group(1), base_url)
        if is_listing_url(url):
            links.add(url)
    for match in re.finditer(r'https?://[^\s"\'<>]+', page_text):
        url = normalize_url(match.group(0).rstrip("),.;"))
        if is_listing_url(url):
            links.add(url)
    return sorted(links)


def is_listing_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "landsearch.com" in host:
        return "/properties/" in path and re.search(r"/\d{6,}/?$", path) is not None
    if "land.com" in host:
        return "/property/" in path
    if "landwatch.com" in host:
        return "/pid/" in path or "/property/" in path
    if "zillow.com" in host:
        return "/homedetails/" in path and ("_zpid" in path or re.search(r"/\d+_", path) is not None)
    if "realtor.com" in host:
        return "/realestateandhomes-detail/" in path
    if "crexi.com" in host:
        return re.search(r"/properties/\d+", path) is not None
    if "loopnet.com" in host:
        return "/listing/" in path and re.search(r"/\d+/?$", path) is not None
    return False


def source_label_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "landsearch.com" in host:
        return "LandSearch"
    if "land.com" in host:
        return "Land.com"
    if "landwatch.com" in host:
        return "LandWatch"
    if "zillow.com" in host:
        return "Zillow"
    if "realtor.com" in host:
        return "Realtor.com"
    if "crexi.com" in host:
        return "Crexi"
    if "loopnet.com" in host:
        return "LoopNet"
    return "Listing Source"


def parse_listing_page(result: FetchResult, source: str = "") -> ListingCandidate:
    candidate = ListingCandidate(url=result.url, source=source, verified=result.ok)
    candidate.verification_status = (
        f"Verified HTTP {result.status}" if result.ok else f"Unable to verify: {result.error or result.status}"
    )
    text = result.text or ""

    candidate.title = first_value(meta_content(text, "og:title"), meta_content(text, "twitter:title"))
    candidate.description = first_value(
        meta_content(text, "og:description"), meta_content(text, "description")
    )

    for data in parse_jsonld_blocks(text):
        for item in walk_json(data):
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_type = " ".join(map(str, item_type))
            type_text = str(item_type).lower()
            if not any(token in type_text for token in ("offer", "product", "place", "residence", "realestate", "landform")):
                continue

            candidate.title = first_value(candidate.title, item.get("name"), item.get("headline"))
            candidate.description = first_value(candidate.description, item.get("description"))
            candidate.external_id = first_value(candidate.external_id, item.get("sku"), item.get("productID"), item.get("identifier"))

            offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
            candidate.price = candidate.price or clean_money(
                first_value(item.get("price"), offers.get("price"))
            )

            geo = item.get("geo") if isinstance(item.get("geo"), dict) else {}
            candidate.latitude = candidate.latitude or clean_number(geo.get("latitude"))
            candidate.longitude = candidate.longitude or clean_number(geo.get("longitude"))

            address = item.get("address")
            if isinstance(address, dict):
                candidate.address = first_value(
                    candidate.address,
                    address.get("streetAddress"),
                    address.get("name"),
                )
                candidate.city = first_value(candidate.city, address.get("addressLocality"))
                candidate.state = first_value(candidate.state, address.get("addressRegion"))
            elif address:
                candidate.address = first_value(candidate.address, address)

    title_blob = f"{candidate.title} {candidate.description}"
    if candidate.acres is None:
        acre_match = re.search(r"([0-9][0-9,.]*)\s*(?:\+\s*)?(?:acre|acres|ac\b)", title_blob, re.I)
        if acre_match:
            candidate.acres = clean_number(acre_match.group(1))

    if candidate.price is None:
        price_match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d+)?)\s*(?:million|m\b|k\b)?", title_blob, re.I)
        if price_match:
            candidate.price = clean_money(price_match.group(0))

    if candidate.latitude is None or candidate.longitude is None:
        coord_match = re.search(r'"latitude"\s*:\s*"?(-?\d+\.\d+)"?.*?"longitude"\s*:\s*"?(-?\d+\.\d+)"?', text, re.I | re.S)
        if coord_match:
            candidate.latitude = clean_number(coord_match.group(1))
            candidate.longitude = clean_number(coord_match.group(2))

    if not candidate.external_id:
        id_match = re.search(r"/(\d{6,})/?$", urlparse(candidate.url).path)
        candidate.external_id = id_match.group(1) if id_match else stable_id(candidate.url)

    infer_location(candidate)
    return candidate


def infer_location(candidate: ListingCandidate) -> None:
    blob = " ".join([candidate.title, candidate.description, candidate.address, candidate.url]).lower()
    if not candidate.city:
        for city in TARGET_CITIES:
            if city in blob:
                candidate.city = city.title()
                break
    if not candidate.county:
        for county in TARGET_COUNTIES:
            if county in blob:
                candidate.county = county.title()
                break
    if not candidate.state:
        candidate.state = "SC"


def is_target_candidate(candidate: ListingCandidate) -> bool:
    if candidate.acres is None or candidate.acres < TARGET_MIN_ACRES:
        return False

    location_blob = " ".join([candidate.city, candidate.county, candidate.address, candidate.title, candidate.url]).lower()
    in_target_market = any(county in location_blob for county in TARGET_COUNTIES) or any(
        city in location_blob for city in TARGET_CITIES
    )
    if not in_target_market:
        return False

    if candidate.latitude is not None and candidate.longitude is not None:
        miles = haversine_miles(
            UPTOWN_CHARLOTTE[0], UPTOWN_CHARLOTTE[1], candidate.latitude, candidate.longitude
        )
        drive = estimate_drive_minutes(miles)
        return bool(
            drive is not None
            and TARGET_MIN_DRIVE_MIN <= drive <= TARGET_MAX_DRIVE_MIN
        )

    return True


def score_candidate(candidate: ListingCandidate) -> float:
    score = 60.0
    if candidate.acres:
        score += min(20, max(0, (candidate.acres - 50) / 5))
    if candidate.latitude is not None and candidate.longitude is not None:
        miles = haversine_miles(
            UPTOWN_CHARLOTTE[0], UPTOWN_CHARLOTTE[1], candidate.latitude, candidate.longitude
        )
        drive = estimate_drive_minutes(miles) or 0
        if TARGET_MIN_DRIVE_MIN <= drive <= TARGET_MAX_DRIVE_MIN:
            score += 12
        _, i77 = nearest_i77_reference(candidate.latitude, candidate.longitude)
        if i77 and i77 <= 10:
            score += 8
    if candidate.price and candidate.acres:
        ppa = candidate.price / candidate.acres
        if ppa <= 10_000:
            score += 6
        elif ppa <= 20_000:
            score += 3
    return round(min(score, 99.0), 1)


def load_rows() -> list[dict[str, str]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}")
    with DATA_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {column: row.get(column, "") for column in TARGET_COLUMNS}
    acres = clean_number(normalized.get("Acres"))
    price = clean_money(normalized.get("List Price"))

    if acres and price and not str(normalized.get("Price / Acre", "")).strip():
        normalized["Price / Acre"] = format_money(price / acres)
    if not normalized.get("Property URL") and normalized.get("Source URL"):
        normalized["Property URL"] = normalized["Source URL"]
    if not normalized.get("Source URL") and normalized.get("Property URL"):
        normalized["Source URL"] = normalized["Property URL"]
    if not normalized.get("Listing Link Label") and normalized.get("Property URL"):
        normalized["Listing Link Label"] = "View Listing"
    if not normalized.get("Dashboard Include"):
        normalized["Dashboard Include"] = "Yes"
    if not normalized.get("Status"):
        normalized["Status"] = "Active - Pending daily source verification"
    if not normalized.get("Property Name"):
        normalized["Property Name"] = normalized.get("Address / Property", "")
    if not normalized.get("Dashboard Slug"):
        normalized["Dashboard Slug"] = slugify(normalized.get("Property Name") or normalized.get("Address / Property") or normalized.get("ID", ""))
    if not normalized.get("Last Researched"):
        normalized["Last Researched"] = TODAY
    return normalized


def is_dashboard_eligible(row: dict[str, str]) -> bool:
    """Return True only for visible investor rows that satisfy the 50-acre mandate."""
    include = first_value(row.get("Dashboard Include")).lower()
    if include in {"no", "false", "0"}:
        return True
    acres = clean_number(row.get("Acres"))
    return bool(acres is not None and acres >= TARGET_MIN_ACRES)


def row_key(row: dict[str, str]) -> str:
    for field_name in URL_FIELDS:
        value = normalize_url(row.get(field_name, ""))
        if value:
            return value.lower().rstrip("/")
    external_id = row.get("Listing External ID", "").strip()
    if external_id:
        return external_id.lower()
    return row.get("ID", "").lower()


def meaningful_row_snapshot(row: dict[str, str]) -> dict[str, str]:
    """Fields that indicate real listing data changed, excluding audit timestamps."""
    ignored = {"Last Researched", "Listing Verified At"}
    if row.get("ID") in AUDIT_ROW_IDS:
        return {}
    return {key: row.get(key, "") for key in TARGET_COLUMNS if key not in ignored}


def apply_candidate(row: dict[str, str], candidate: ListingCandidate, discovered: bool = False) -> dict[str, str]:
    acres = candidate.acres or clean_number(row.get("Acres"))
    price = candidate.price or clean_money(row.get("List Price"))
    lat = candidate.latitude or clean_number(row.get("Latitude"))
    lng = candidate.longitude or clean_number(row.get("Longitude"))
    miles = haversine_miles(UPTOWN_CHARLOTTE[0], UPTOWN_CHARLOTTE[1], lat, lng) if lat and lng else clean_number(row.get("Miles From Charlotte"))
    drive = estimate_drive_minutes(miles) if miles else clean_number(row.get("Drive Time From Charlotte") or row.get("Est. Drive Min to Charlotte"))
    i77_ref, i77_minutes = nearest_i77_reference(lat, lng)

    property_name = first_value(candidate.title, candidate.address, row.get("Property Name"), row.get("Address / Property"))
    address = first_value(candidate.address, row.get("Address / Property"), property_name)
    notes = first_value(
        row.get("Listing Notes"),
        candidate.description[:260],
        "Daily scraper discovered this listing; verify parcel boundaries and broker status.",
    )

    row.update(
        {
            "ID": row.get("ID") or stable_id(candidate.url),
            "Dashboard Slug": row.get("Dashboard Slug") or slugify(property_name),
            "Dashboard Include": row.get("Dashboard Include") or "Yes",
            "Priority": row.get("Priority") or ("Primary" if acres and acres >= TARGET_MIN_ACRES else "Research"),
            "Recommendation Tier": row.get("Recommendation Tier") or ("Tier 1 - Investor Shortlist" if acres and acres >= TARGET_MIN_ACRES else "Active Research"),
            "Weighted Polo Score": row.get("Weighted Polo Score") or str(score_candidate(candidate)),
            "Corridor": row.get("Corridor") or "35-55 Min Charlotte Ring",
            "Corridor Fit": row.get("Corridor Fit") or "Primary",
            "Address / Property": address,
            "City": first_value(candidate.city, row.get("City")),
            "County": first_value(candidate.county, row.get("County")),
            "State": first_value(
                candidate.state if candidate.verified else "",
                row.get("State"),
                candidate.state,
                "SC",
            ),
            "Acres": format_number(acres),
            "List Price": format_number(price, 0),
            "Price / Acre": format_money(price / acres) if acres and price else row.get("Price / Acre", ""),
            "Status": (
                "Active - Source verified today"
                if candidate.verified
                else row.get("Status") or "Active - Source check needs review"
            ),
            "Source": first_value(candidate.source, row.get("Source")),
            "Listing Link Label": "View Exact Listing",
            "Source URL": candidate.url,
            "Geocode Query": row.get("Geocode Query") or ", ".join(filter(None, [address, candidate.city, candidate.state])),
            "Geo Status": row.get("Geo Status") or ("Listing coordinates available / confirm in GIS" if lat and lng else "Needs parcel/geocode verification"),
            "Research Confidence": "High" if candidate.verified and lat and lng else row.get("Research Confidence") or "Medium",
            "Listing Notes": notes,
            "Polo / Investor Notes": row.get("Polo / Investor Notes") or "Daily agent match for the 35-55 minute Charlotte large-acreage thesis.",
            "Investor Narrative": row.get("Investor Narrative") or f"{format_number(acres)} acres near {first_value(candidate.city, candidate.county, 'the 35-55 minute Charlotte ring')}; confirm access, frontage, topography, and listing status.",
            "Est. Drive Min to Charlotte": format_number(drive, 0),
            "Est. Min to I-77": format_number(i77_minutes, 0),
            "Next Due Diligence": row.get("Next Due Diligence") or "Confirm active status with broker; pull parcel/GIS boundary; verify zoning, utilities, road frontage, wetlands/floodplain, and polo-field grading feasibility.",
            "Last Researched": TODAY,
            "Property Name": property_name,
            "Property URL": candidate.url,
            "Map URL": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}" if lat and lng else row.get("Map URL", ""),
            "Latitude": format_number(lat, 6),
            "Longitude": format_number(lng, 6),
            "Drive Time From Charlotte": format_number(drive, 0),
            "Miles From Charlotte": format_number(miles, 1),
            "Listing Verified At": NOW_ISO if candidate.verified else row.get("Listing Verified At", ""),
            "Listing External ID": first_value(candidate.external_id, row.get("Listing External ID")),
            "Listing Verification Status": (
                candidate.verification_status
                if candidate.verified
                else row.get("Listing Verification Status")
                or f"Latest automated check unavailable: {candidate.verification_status}; manual broker/source verification required."
            ),
            "Nearest I-77 Reference": i77_ref,
            "Scrape Source Name": (
                first_value(candidate.source_name, row.get("Scrape Source Name"))
                if candidate.verified
                else row.get("Scrape Source Name", "")
            ),
            "Scrape Source URL": (
                first_value(candidate.source_url, row.get("Scrape Source URL"))
                if candidate.verified
                else row.get("Scrape Source URL", "")
            ),
        }
    )

    if discovered:
        row["Listing Notes"] = first_value(
            candidate.description[:260],
            "New listing discovered by daily search-source scrape.",
        )
    return row


def tracked_listing_urls(rows: list[dict[str, str]]) -> list[str]:
    urls = set()
    for row in rows:
        for field_name in URL_FIELDS:
            url = normalize_url(row.get(field_name, ""))
            if is_listing_url(url):
                urls.add(url)
    return sorted(urls)


def scrape_candidates(rows: list[dict[str, str]], summary: RefreshSummary) -> tuple[list[ListingCandidate], list[str]]:
    candidates_by_url: dict[str, ListingCandidate] = {}
    audit_messages: list[str] = []
    listing_urls = set(tracked_listing_urls(rows))
    existing_keys = {row_key(row) for row in rows}
    summary.tracked_listing_urls = len(listing_urls)

    for source_config in SEARCH_SOURCES:
        result = fetch_url(source_config["url"])
        if result.ok:
            found_links = extract_listing_links(result.text, result.url)
            for link in found_links:
                listing_urls.add(link)
            attempt = SourceAttempt(
                name=source_config["name"],
                source=source_config["source"],
                url=source_config["url"],
                ok=True,
                status=result.status,
                discovered_links=len(found_links),
            )
            audit_messages.append(f"{source_config['name']}: {len(found_links)} listing links discovered")
        else:
            attempt = SourceAttempt(
                name=source_config["name"],
                source=source_config["source"],
                url=source_config["url"],
                ok=False,
                status=result.status,
                error=result.error or f"HTTP status {result.status}",
            )
            audit_messages.append(
                f"{source_config['name']}: source unavailable ({attempt.error})"
            )
        summary.source_attempts.append(attempt)
        time.sleep(REQUEST_PAUSE_SECONDS)

    source_by_label = {source["source"]: source for source in SEARCH_SOURCES}
    for url in sorted(listing_urls):
        result = fetch_url(url)
        source = source_label_for_url(url)
        candidate = parse_listing_page(result, source=source)
        source_match = source_by_label.get(source)
        if source_match:
            candidate.source_name = source_match["name"]
            candidate.source_url = source_match["url"]
        if is_target_candidate(candidate) or url.lower().rstrip("/") in existing_keys:
            candidates_by_url[candidate.url.lower().rstrip("/")] = candidate
        time.sleep(REQUEST_PAUSE_SECONDS)

    return list(candidates_by_url.values()), audit_messages


def update_no_results_audit_row(
    rows: list[dict[str, str]],
    audit_messages: list[str],
    qualifying_count: int,
    summary: RefreshSummary,
) -> None:
    audit_id = "SEARCH-50AC-AUDIT"
    message = "; ".join(audit_messages)[:1200]
    if summary.sources_attempted and summary.sources_succeeded == 0:
        status = "Daily search blocked/unavailable - no source succeeded; CSV listing data was not refreshed"
    elif summary.sources_attempted and summary.failure_rate >= 0.75:
        status = f"Daily search degraded - {summary.sources_failed}/{summary.sources_attempted} sources failed; review logs before treating data as refreshed"
    elif qualifying_count:
        status = f"Daily search completed - {qualifying_count} qualifying/tracked listing(s) processed"
    else:
        status = "Daily search completed - no qualifying 50+ acre listings discovered 35-55 minutes from Charlotte"

    audit_row = next((row for row in rows if row.get("ID") in AUDIT_ROW_IDS), None)
    if audit_row is None:
        audit_row = {column: "" for column in TARGET_COLUMNS}
        rows.append(audit_row)
    audit_row.update(
        {
            "ID": audit_id,
            "Dashboard Slug": "daily-50-acre-land-search-audit",
            "Dashboard Include": "No",
            "Priority": "Audit",
            "Recommendation Tier": "Search Audit",
            "Corridor": "Charlotte Region",
            "Corridor Fit": "Data Quality",
            "Address / Property": "Daily 50+ acre land-source search audit",
            "City": "Charlotte Region",
            "County": "35-55 min Charlotte ring",
            "State": "NC / SC",
            "Status": status,
            "Source": "Automated search sources",
            "Listing Link Label": "Search Sources",
            "Source URL": SEARCH_SOURCES[0]["url"],
            "Research Confidence": "System Audit",
            "Listing Notes": message or "No source responses recorded.",
            "Polo / Investor Notes": "Hidden dashboard audit row that separates source failures from no-result searches and does not prove new listings were found.",
            "Investor Narrative": status,
            "Next Due Diligence": "Review GitHub Actions logs, source failures, and newly discovered URLs before investor distribution.",
            "Last Researched": TODAY,
            "Property Name": "Daily 50+ Acre Search Audit",
            "Property URL": SEARCH_SOURCES[0]["url"],
            "Listing Verified At": NOW_ISO,
            "Listing External ID": f"sources={summary.sources_attempted};succeeded={summary.sources_succeeded};failed={summary.sources_failed};urls={summary.listing_urls_discovered}",
            "Listing Verification Status": status,
            "Scrape Source Name": " | ".join(source["name"] for source in SEARCH_SOURCES),
            "Scrape Source URL": " | ".join(source["url"] for source in SEARCH_SOURCES),
        }
    )


def write_rows(rows: list[dict[str, str]]) -> None:
    with DATA_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TARGET_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    visible_rows = [
        row for row in rows
        if first_value(row.get("Dashboard Include")).lower() not in {"no", "false", "0"}
    ]
    for row in visible_rows:
        acres = clean_number(row.get("Acres"))
        if acres is None or acres < TARGET_MIN_ACRES:
            errors.append(f"{row.get('ID') or row.get('Property Name')}: visible row has {row.get('Acres') or 'missing'} acres")
        if not row.get("Property URL") or not row.get("Listing Verification Status"):
            errors.append(f"{row.get('ID') or row.get('Property Name')}: missing source URL or verification status")
    return errors


def print_summary(summary: RefreshSummary, audit_messages: list[str]) -> None:
    summary.finalize()
    print("Property refresh summary")
    print(f"- sources attempted: {summary.sources_attempted}")
    print(f"- sources succeeded: {summary.sources_succeeded}")
    print(f"- sources failed: {summary.sources_failed}")
    print(f"- sources blocked/unavailable: {summary.sources_blocked}")
    print(f"- tracked listing URLs: {summary.tracked_listing_urls}")
    print(f"- listing URLs discovered: {summary.listing_urls_discovered}")
    print(f"- candidates processed: {summary.candidates_processed}")
    print(f"- rows added: {summary.rows_added}")
    print(f"- rows updated: {summary.rows_updated}")
    print(f"- audit-only changes: {'yes' if summary.audit_only_changes else 'no'}")
    print(f"- CSV written: {'yes' if summary.csv_written else 'no'}")
    if summary.dry_run:
        print("- mode: dry-run (no CSV write)")
    print("Source results:")
    for attempt in summary.source_attempts:
        if attempt.ok:
            print(f"  OK {attempt.status} {attempt.name}: {attempt.discovered_links} listing link(s)")
        else:
            print(f"  FAIL {attempt.status or 'network'} {attempt.name}: {attempt.error}")
    if audit_messages:
        print("Audit messages:")
        for message in audit_messages:
            print(f"  - {message}")


def summary_json(summary: RefreshSummary) -> dict[str, Any]:
    summary.finalize()
    data = asdict(summary)
    data["source_attempts"] = [asdict(attempt) for attempt in summary.source_attempts]
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the Charlotte Polo investor property CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Run discovery and validation without writing the CSV.")
    parser.add_argument("--allow-audit-only", action="store_true", help="Write the audit row even when no listing rows were added or meaningfully updated.")
    parser.add_argument("--allow-source-failures", action="store_true", help="Do not fail the process when most search sources are blocked/unavailable.")
    parser.add_argument("--max-source-failure-rate", type=float, default=0.75, help="Fail when this fraction of sources fail unless --allow-source-failures is set.")
    parser.add_argument("--summary-path", type=Path, help="Optional JSON file for the refresh summary.")
    parser.add_argument("--validate-only", action="store_true", help="Validate the existing CSV and exit without network discovery.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [normalize_row(row) for row in load_rows()]

    if args.validate_only:
        errors = validate_rows(rows)
        if errors:
            print("CSV validation failed:")
            for error in errors:
                print(f"- {error}")
            raise SystemExit(1)
        print(f"CSV validation passed: {len(rows)} total rows; visible rows are 50+ acres and have source status.")
        return

    original_snapshots = {row_key(row): meaningful_row_snapshot(row) for row in rows if row_key(row)}
    summary = RefreshSummary(dry_run=args.dry_run)
    candidates, audit_messages = scrape_candidates(rows, summary)
    summary.finalize()
    summary.candidates_processed = len(candidates)

    rows_by_key = {row_key(row): row for row in rows if row_key(row)}
    touched_keys = set()

    for candidate in candidates:
        key = candidate.url.lower().rstrip("/")
        row = rows_by_key.get(key)
        discovered = row is None
        if row is None:
            row = {column: "" for column in TARGET_COLUMNS}
            rows.append(row)
            rows_by_key[key] = row
        before_snapshot = meaningful_row_snapshot(row)
        apply_candidate(row, candidate, discovered=discovered)
        after_key = row_key(row)
        after_snapshot = meaningful_row_snapshot(row)
        touched_keys.add(after_key)
        if discovered:
            summary.rows_added += 1
        elif before_snapshot != after_snapshot or original_snapshots.get(after_key) != after_snapshot:
            summary.rows_updated += 1

    # Preserve existing valid rows that were not reached. Do not stamp them as
    # researched merely because the agent ran; that made audit-only refreshes look
    # like successful data updates.
    for row in rows:
        if row.get("ID") in AUDIT_ROW_IDS:
            continue
        if row_key(row) not in touched_keys and row.get("Property URL"):
            row["Listing Verification Status"] = row.get("Listing Verification Status") or "Not reached in latest scrape; preserve link and verify manually."

    update_no_results_audit_row(rows, audit_messages, len(candidates), summary)
    rows = [normalize_row(row) for row in rows]
    rows = [row for row in rows if is_dashboard_eligible(row)]

    validation_errors = validate_rows(rows)
    if validation_errors:
        print_summary(summary, audit_messages)
        print("CSV validation failed:")
        for error in validation_errors:
            print(f"- {error}")
        raise SystemExit(1)

    summary.audit_only_changes = summary.rows_added == 0 and summary.rows_updated == 0
    should_fail_sources = (
        not args.allow_source_failures
        and summary.sources_attempted > 0
        and summary.failure_rate >= args.max_source_failure_rate
        and summary.rows_added == 0
    )

    if should_fail_sources:
        print_summary(summary, audit_messages)
        print(
            "Source reliability gate failed: "
            f"{summary.sources_failed}/{summary.sources_attempted} sources failed and no new listing rows were added. "
            "Use --allow-source-failures only for an intentional audit run."
        )
        if args.summary_path:
            args.summary_path.write_text(json.dumps(summary_json(summary), indent=2), encoding="utf-8")
        raise SystemExit(2)

    if args.dry_run:
        summary.csv_written = False
    elif summary.audit_only_changes and not args.allow_audit_only:
        summary.csv_written = False
    else:
        write_rows(rows)
        summary.csv_written = True

    if args.summary_path:
        args.summary_path.write_text(json.dumps(summary_json(summary), indent=2), encoding="utf-8")

    print_summary(summary, audit_messages)
    if summary.audit_only_changes and not args.allow_audit_only:
        print("Skipped CSV write: only the hidden audit row/timestamps would have changed.")
    elif summary.csv_written:
        print(f"Updated {DATA_PATH}")


if __name__ == "__main__":
    main()
