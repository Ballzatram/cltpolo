"""Update the investor property CSV from tracked listings and search pages.

The script is intentionally dependency-free so it can run reliably from GitHub
Actions. It politely fetches public listing/search pages, extracts durable listing
identifiers and investor-relevant fields when they are present in JSON-LD/meta
markup, merges those findings into the existing research CSV, and still stamps the
CSV when a source returns no qualifying results or the network is unavailable.
"""

import csv
import hashlib
import html
import json
import math
import re
import time
from dataclasses import dataclass
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
                "CharlottePoloPropertyResearch/1.0 "
                "(+https://www.cltpolo.com/investors)"
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
        return "/pid/" in path
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
    for field in URL_FIELDS:
        value = normalize_url(row.get(field, ""))
        if value:
            return value.lower().rstrip("/")
    external_id = row.get("Listing External ID", "").strip()
    if external_id:
        return external_id.lower()
    return row.get("ID", "").lower()


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
            "Recommendation Tier": row.get("Recommendation Tier") or "Tier 1 - Investor Shortlist" if acres and acres >= TARGET_MIN_ACRES else row.get("Recommendation Tier") or "Active Research",
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
        for field in URL_FIELDS:
            url = normalize_url(row.get(field, ""))
            if is_listing_url(url):
                urls.add(url)
    return sorted(urls)


def scrape_candidates(rows: list[dict[str, str]]) -> tuple[list[ListingCandidate], list[str]]:
    candidates_by_url: dict[str, ListingCandidate] = {}
    audit_messages: list[str] = []
    listing_urls = set(tracked_listing_urls(rows))

    for source_config in SEARCH_SOURCES:
        result = fetch_url(source_config["url"])
        if result.ok:
            found_links = extract_listing_links(result.text, result.url)
            for link in found_links:
                listing_urls.add(link)
            audit_messages.append(f"{source_config['name']}: {len(found_links)} listing links discovered")
        else:
            audit_messages.append(
                f"{source_config['name']}: source unavailable ({result.error or result.status})"
            )
        time.sleep(REQUEST_PAUSE_SECONDS)

    for url in sorted(listing_urls):
        result = fetch_url(url)
        source = source_label_for_url(url)
        candidate = parse_listing_page(result, source=source)
        source_match = next((s for s in SEARCH_SOURCES if s["source"] == source), None)
        if source_match:
            candidate.source_name = source_match["name"]
            candidate.source_url = source_match["url"]
        if is_target_candidate(candidate) or url.lower().rstrip("/") in {row_key(row) for row in rows}:
            candidates_by_url[candidate.url.lower().rstrip("/")] = candidate
        time.sleep(REQUEST_PAUSE_SECONDS)

    return list(candidates_by_url.values()), audit_messages


def update_no_results_audit_row(rows: list[dict[str, str]], audit_messages: list[str], qualifying_count: int) -> None:
    audit_id = "SEARCH-50AC-AUDIT"
    previous_audit_ids = {"SEARCH-100AC-AUDIT", audit_id}
    message = "; ".join(audit_messages)[:900]
    status = (
        f"Daily search completed - {qualifying_count} qualifying/tracked listing(s) processed"
        if qualifying_count
        else "Daily search completed - no qualifying 50+ acre listings discovered 35-55 minutes from Charlotte"
    )
    audit_row = next((row for row in rows if row.get("ID") in previous_audit_ids), None)
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
            "Polo / Investor Notes": "Hidden dashboard audit row that proves the 35-55 minute / 50+ acre search ran even when no new investor-grade listings are found.",
            "Investor Narrative": status,
            "Next Due Diligence": "Review audit status, any source failures, and newly discovered URLs before investor distribution.",
            "Last Researched": TODAY,
            "Property Name": "Daily 50+ Acre Search Audit",
            "Property URL": SEARCH_SOURCES[0]["url"],
            "Listing Verified At": NOW_ISO,
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


def main() -> None:
    rows = [normalize_row(row) for row in load_rows()]
    candidates, audit_messages = scrape_candidates(rows)

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
        apply_candidate(row, candidate, discovered=discovered)
        touched_keys.add(row_key(row))

    for row in rows:
        if row.get("ID") in {"SEARCH-100AC-AUDIT", "SEARCH-50AC-AUDIT"}:
            continue
        if row_key(row) not in touched_keys:
            row["Last Researched"] = TODAY
            if row.get("Property URL"):
                row["Listing Verification Status"] = row.get("Listing Verification Status") or "Not reached in latest scrape; preserve link and verify manually."

    update_no_results_audit_row(rows, audit_messages, len(candidates))
    rows = [normalize_row(row) for row in rows]
    rows = [row for row in rows if is_dashboard_eligible(row)]
    write_rows(rows)

    print(f"Updated {DATA_PATH}")
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(TARGET_COLUMNS)}")
    print(f"Candidates processed: {len(candidates)}")
    for message in audit_messages:
        print(f"- {message}")


if __name__ == "__main__":
    main()
