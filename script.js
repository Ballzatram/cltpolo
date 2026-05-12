const navToggle = document.querySelector(".nav-toggle");
const siteNav = document.querySelector(".site-nav");

if (navToggle && siteNav) {
  navToggle.addEventListener("click", () => {
    siteNav.classList.toggle("open");
  });
}

const contactForm = document.getElementById("contactForm");

if (contactForm) {
  contactForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submitButton = contactForm.querySelector('button[type="submit"]');
    const originalButtonText = submitButton ? submitButton.textContent : "Submit";

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Sending...";
    }

    const formData = new FormData(contactForm);

    try {
      const response = await fetch(contactForm.action, {
        method: "POST",
        body: formData,
        headers: {
          Accept: "application/json"
        }
      });

      if (response.ok) {
        window.location.href = "thank-you.html";
        return;
      }

      const data = await response.json().catch(() => null);

      if (data && data.errors && Array.isArray(data.errors)) {
        alert(data.errors.map((error) => error.message).join(", "));
      } else {
        alert("Something went wrong. Please try again.");
      }
    } catch (error) {
      alert("Something went wrong. Please check your connection and try again.");
    }

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  });
}

/* ================================
   Investor Portal
================================ */

const INVESTOR_ACCESS_CODE = "cltpolo123!";
const INVESTOR_ACCESS_KEY = "cltPoloInvestorAccess";
const INVESTOR_API_URL = "/data/charlotte_polo_properties.csv";
const INVESTOR_MIN_ACRES = 50;

const UPTOWN_CHARLOTTE = {
  latitude: 35.2271,
  longitude: -80.8431
};

const PROPERTY_LINK_FIELDS = [
  "Property URL",
  "Property Link",
  "Listing URL",
  "Listing Link",
  "Listing",
  "URL",
  "url",
  "Website",
  "Source URL",
  "Zillow URL",
  "LandWatch URL",
  "Land.com URL",
  "Realtor URL",
  "LoopNet URL"
];

const MAP_LINK_FIELDS = [
  "Map URL",
  "Google Maps",
  "Google Maps URL",
  "Map Link",
  "map_url",
  "Maps URL",
  "Directions URL"
];

const investorLock = document.getElementById("investorLock");
const investorDashboard = document.getElementById("investorDashboard");
const investorCodeForm = document.getElementById("investorCodeForm");
const investorCodeInput = document.getElementById("investorCode");
const investorCodeError = document.getElementById("investorCodeError");
const investorLoading = document.getElementById("investorLoading");
const investorEmpty = document.getElementById("investorEmpty");
const propertyGrid = document.getElementById("propertyGrid");
const investorStats = document.getElementById("investorStats");
const refreshInvestorData = document.getElementById("refreshInvestorData");
const runPropertyAgent = document.getElementById("runPropertyAgent");
const propertyAgentStatus = document.getElementById("propertyAgentStatus");
const investorMapElement = document.getElementById("investorMap");

const investorSearch = document.getElementById("investorSearch");
const corridorFilter = document.getElementById("corridorFilter");
const tierFilter = document.getElementById("tierFilter");
const sortFilter = document.getElementById("sortFilter");

if (window.location.pathname.endsWith("/investors.html")) {
  window.history.replaceState(null, "", "/investors");
}

let investorProperties = [];
let investorMap = null;
let investorMapLayer = null;
let propertyMiniMaps = [];

function normalizeInvestorValue(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function parseInvestorNumber(value) {
  const cleaned = normalizeInvestorValue(value).replace(/[$,% ,]/g, "");
  const parsed = Number(cleaned);

  return Number.isFinite(parsed) ? parsed : 0;
}

function formatCurrency(value) {
  const number = parseInvestorNumber(value);

  if (!number) {
    return "TBD";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(number);
}

function formatNumber(value, maximumFractionDigits = 0) {
  const number = parseInvestorNumber(value);

  if (!number) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits
  }).format(number);
}

function getPropertyField(property, possibleKeys) {
  for (const key of possibleKeys) {
    if (
      property[key] !== undefined &&
      property[key] !== null &&
      property[key] !== ""
    ) {
      return property[key];
    }
  }

  return "";
}

function normalizeUrl(value) {
  const rawUrl = normalizeInvestorValue(value);

  if (!rawUrl) {
    return "";
  }

  if (
    rawUrl.startsWith("http://") ||
    rawUrl.startsWith("https://") ||
    rawUrl.startsWith("mailto:")
  ) {
    return rawUrl;
  }

  if (rawUrl.includes(".") && !rawUrl.includes(" ")) {
    return `https://${rawUrl}`;
  }

  return "";
}

function getListingUrl(property) {
  const url = normalizeUrl(getPropertyField(property, PROPERTY_LINK_FIELDS));

  if (!url) {
    return "";
  }

  const lowerUrl = url.toLowerCase();

  const blockedListingFallbacks = [
    "google.com/maps",
    "maps.google.com",
    "bing.com/maps",
    "apple.com/maps",
    "openstreetmap.org",
    "google.com/search",
    "duckduckgo.com",
    "bing.com/search"
  ];

  if (blockedListingFallbacks.some((blocked) => lowerUrl.includes(blocked))) {
    return "";
  }

  const isLandWatchUrl = lowerUrl.includes("landwatch.com");
  const isDirectLandWatchListing = lowerUrl.includes("/pid/");

  if (isLandWatchUrl && !isDirectLandWatchListing) {
    return "";
  }

  return url;
}

function getMapUrl(property) {
  const explicitMapUrl = normalizeUrl(getPropertyField(property, MAP_LINK_FIELDS));

  if (explicitMapUrl) {
    return explicitMapUrl;
  }

  const lat = getLatitude(property);
  const lng = getLongitude(property);

  if (lat && lng) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      `${lat},${lng}`
    )}`;
  }

  const address = normalizeInvestorValue(
    getPropertyField(property, [
      "Address",
      "Property Address",
      "Location",
      "Site Address",
      "Full Address"
    ])
  );

  if (address) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      address
    )}`;
  }

  return "";
}

function getPropertyDisplayName(property, fallback = "Unnamed Property") {
  return (
    normalizeInvestorValue(
      getPropertyField(property, [
        "Property Name",
        "Name",
        "Address",
        "Property Address",
        "Location",
        "property_name"
      ])
    ) || fallback
  );
}

function parseCSV(csvText) {
  const rows = [];
  let currentRow = [];
  let currentValue = "";
  let insideQuotes = false;

  for (let i = 0; i < csvText.length; i++) {
    const char = csvText[i];
    const nextChar = csvText[i + 1];

    if (char === '"' && insideQuotes && nextChar === '"') {
      currentValue += '"';
      i++;
      continue;
    }

    if (char === '"') {
      insideQuotes = !insideQuotes;
      continue;
    }

    if (char === "," && !insideQuotes) {
      currentRow.push(currentValue.trim());
      currentValue = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !insideQuotes) {
      if (char === "\r" && nextChar === "\n") {
        i++;
      }

      currentRow.push(currentValue.trim());

      if (currentRow.some((value) => value !== "")) {
        rows.push(currentRow);
      }

      currentRow = [];
      currentValue = "";
      continue;
    }

    currentValue += char;
  }

  if (currentValue || currentRow.length) {
    currentRow.push(currentValue.trim());

    if (currentRow.some((value) => value !== "")) {
      rows.push(currentRow);
    }
  }

  if (rows.length < 2) {
    return [];
  }

  const headers = rows[0].map((header) => header.trim());

  return rows.slice(1).map((row) => {
    return headers.reduce((object, header, index) => {
      object[header] = row[index] || "";
      return object;
    }, {});
  });
}

function slugify(value) {
  return normalizeInvestorValue(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function getLatitude(property) {
  return parseInvestorNumber(
    getPropertyField(property, ["Latitude", "Lat", "latitude", "lat"])
  );
}

function getLongitude(property) {
  return parseInvestorNumber(
    getPropertyField(property, [
      "Longitude",
      "Lng",
      "Lon",
      "longitude",
      "lng",
      "lon"
    ])
  );
}

function estimateMilesFromCharlotte(property) {
  const explicitMiles = parseInvestorNumber(
    getPropertyField(property, [
      "Miles From Charlotte",
      "Distance From Charlotte",
      "Distance Miles",
      "Miles",
      "miles_from_charlotte"
    ])
  );

  if (explicitMiles) {
    return explicitMiles;
  }

  const lat = getLatitude(property);
  const lng = getLongitude(property);

  if (!lat || !lng) {
    return 0;
  }

  return haversineMiles(
    UPTOWN_CHARLOTTE.latitude,
    UPTOWN_CHARLOTTE.longitude,
    lat,
    lng
  );
}

function getDriveTimeMinutes(property) {
  const explicitDriveTime = parseInvestorNumber(
    getPropertyField(property, [
      "Drive Time From Charlotte",
      "Drive Time",
      "Drive Time Minutes",
      "Estimated Drive Time",
      "drive_time"
    ])
  );

  if (explicitDriveTime) {
    return explicitDriveTime;
  }

  const miles = estimateMilesFromCharlotte(property);

  if (!miles) {
    return 0;
  }

  return Math.round(Math.max(18, miles * 1.28 + 8));
}

function formatDriveTime(property) {
  const minutes = getDriveTimeMinutes(property);

  if (!minutes) {
    return "Drive TBD";
  }

  return `${minutes} min`;
}

function getDriveBand(property) {
  const minutes = getDriveTimeMinutes(property);

  if (!minutes) {
    return "Drive TBD";
  }

  if (minutes <= 35) {
    return "Core access";
  }

  if (minutes <= 55) {
    return "Destination fit";
  }

  return "Strategic distance";
}

function haversineMiles(lat1, lon1, lat2, lon2) {
  const radius = 3958.8;
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
    Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) *
    Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return radius * c;
}

function isShortlistProperty(property) {
  const tier = normalizeInvestorValue(
    getPropertyField(property, ["Recommendation Tier", "Tier", "tier"])
  ).toLowerCase();

  return (
    tier.includes("shortlist") ||
    tier.includes("high") ||
    tier.includes("priority") ||
    tier.includes("tier 1")
  );
}

function showInvestorDashboard() {
  if (!investorLock || !investorDashboard) {
    return;
  }

  investorLock.style.display = "none";
  investorLock.hidden = true;

  investorDashboard.hidden = false;
  investorDashboard.style.display = "block";

  loadInvestorProperties();
}

async function loadInvestorProperties() {
  if (!propertyGrid || !investorLoading) {
    return;
  }

  investorLoading.hidden = false;
  investorLoading.textContent = "Loading investor dashboard...";
  investorEmpty.hidden = true;
  propertyGrid.innerHTML = "";

  try {
    const response = await fetch(INVESTOR_API_URL, {
      headers: {
        Accept: "text/csv"
      }
    });

    if (!response.ok) {
      throw new Error("Could not load investor data.");
    }

    const csvText = await response.text();

    investorProperties = parseCSV(csvText);

    populateInvestorFilters(investorProperties);
    renderInvestorDashboard();
  } catch (error) {
    investorLoading.hidden = false;
    investorLoading.textContent =
      "Investor data could not be loaded. Check that data/charlotte_polo_properties.csv exists and is committed to the repo.";
  }
}

function setPropertyAgentStatus(message, statusType = "info") {
  if (!propertyAgentStatus) {
    return;
  }

  propertyAgentStatus.hidden = false;
  propertyAgentStatus.textContent = message;
  propertyAgentStatus.dataset.status = statusType;
}

async function triggerPropertyAgentRefresh() {
  if (!runPropertyAgent) {
    return;
  }

  const repo = runPropertyAgent.dataset.githubRepo;
  const workflow = runPropertyAgent.dataset.githubWorkflow;
  const ref = runPropertyAgent.dataset.githubRef || "main";

  if (!repo || !workflow) {
    setPropertyAgentStatus(
      "Agent refresh is not configured. Add the GitHub repository and workflow file to this button.",
      "error"
    );
    return;
  }

  const token = window.prompt(
    "Paste a GitHub token with Actions write access to start the property CSV refresh agent. The token is used once and is not stored."
  );

  if (!token) {
    setPropertyAgentStatus(
      "Agent refresh canceled. No GitHub token was provided.",
      "warning"
    );
    return;
  }

  const originalButtonText = runPropertyAgent.textContent;
  runPropertyAgent.disabled = true;
  runPropertyAgent.textContent = "Starting Agent...";
  setPropertyAgentStatus(
    "Starting the property CSV refresh agent in GitHub Actions...",
    "pending"
  );

  try {
    const response = await fetch(
      `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
      {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${token.trim()}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ ref })
      }
    );

    if (response.status !== 204) {
      const errorData = await response.json().catch(() => null);
      const errorMessage = errorData && errorData.message
        ? errorData.message
        : "GitHub did not accept the workflow dispatch request.";

      throw new Error(errorMessage);
    }

    setPropertyAgentStatus(
      "CSV refresh agent started. When the GitHub Actions run finishes and Pages redeploys, use Reload Committed Data to load the updated CSV.",
      "success"
    );
  } catch (error) {
    setPropertyAgentStatus(
      `Could not start the CSV refresh agent: ${error.message}`,
      "error"
    );
  } finally {
    runPropertyAgent.disabled = false;
    runPropertyAgent.textContent = originalButtonText;
  }
}

function populateInvestorFilters(properties) {
  if (!corridorFilter || !tierFilter) {
    return;
  }

  const currentCorridor = corridorFilter.value;
  const currentTier = tierFilter.value;

  const corridors = new Set();
  const tiers = new Set();

  properties.forEach((property) => {
    const corridor = normalizeInvestorValue(
      getPropertyField(property, ["Corridor", "corridor"])
    );

    const tier = normalizeInvestorValue(
      getPropertyField(property, ["Recommendation Tier", "Tier", "tier"])
    );

    if (corridor) {
      corridors.add(corridor);
    }

    if (tier) {
      tiers.add(tier);
    }
  });

  corridorFilter.innerHTML = '<option value="">All Corridors</option>';
  tierFilter.innerHTML = '<option value="">All Tiers</option>';

  [...corridors].sort().forEach((corridor) => {
    const option = document.createElement("option");
    option.value = corridor;
    option.textContent = corridor;
    corridorFilter.appendChild(option);
  });

  [...tiers].sort().forEach((tier) => {
    const option = document.createElement("option");
    option.value = tier;
    option.textContent = tier;
    tierFilter.appendChild(option);
  });

  corridorFilter.value = currentCorridor;
  tierFilter.value = currentTier;
}

function getFilteredInvestorProperties() {
  const searchValue = investorSearch
    ? investorSearch.value.toLowerCase().trim()
    : "";

  const corridorValue = corridorFilter ? corridorFilter.value : "";
  const tierValue = tierFilter ? tierFilter.value : "";
  const sortValue = sortFilter ? sortFilter.value : "score-desc";

  const filtered = investorProperties.filter((property) => {
    const includeValue = normalizeInvestorValue(
      getPropertyField(property, [
        "Dashboard Include",
        "dashboard_include",
        "include"
      ])
    ).toLowerCase();

    const isIncluded =
      includeValue === "true" ||
      includeValue === "yes" ||
      includeValue === "1" ||
      includeValue === "";

    if (!isIncluded) {
      return false;
    }

    const acres = parseInvestorNumber(
      getPropertyField(property, ["Acreage", "Acres", "acres"])
    );

    if (acres < INVESTOR_MIN_ACRES) {
      return false;
    }

    const corridor = normalizeInvestorValue(
      getPropertyField(property, ["Corridor", "corridor"])
    );

    const tier = normalizeInvestorValue(
      getPropertyField(property, ["Recommendation Tier", "Tier", "tier"])
    );

    const searchableText = Object.values(property).join(" ").toLowerCase();

    const matchesSearch = !searchValue || searchableText.includes(searchValue);
    const matchesCorridor = !corridorValue || corridor === corridorValue;
    const matchesTier = !tierValue || tier === tierValue;

    return matchesSearch && matchesCorridor && matchesTier;
  });

  filtered.sort((a, b) => {
    const scoreA = parseInvestorNumber(
      getPropertyField(a, ["Weighted Polo Score", "Score", "score"])
    );

    const scoreB = parseInvestorNumber(
      getPropertyField(b, ["Weighted Polo Score", "Score", "score"])
    );

    const priceA = parseInvestorNumber(
      getPropertyField(a, ["List Price", "Price", "price"])
    );

    const priceB = parseInvestorNumber(
      getPropertyField(b, ["List Price", "Price", "price"])
    );

    const acresA = parseInvestorNumber(
      getPropertyField(a, ["Acreage", "Acres", "acres"])
    );

    const acresB = parseInvestorNumber(
      getPropertyField(b, ["Acreage", "Acres", "acres"])
    );

    const driveA = getDriveTimeMinutes(a);
    const driveB = getDriveTimeMinutes(b);

    const updatedA =
      new Date(
        getPropertyField(a, ["Listing Verified At", "Last Researched", "Last Updated", "Updated", "updated_at"])
      ).getTime() || 0;

    const updatedB =
      new Date(
        getPropertyField(b, ["Listing Verified At", "Last Researched", "Last Updated", "Updated", "updated_at"])
      ).getTime() || 0;

    if (sortValue === "drive-asc") {
      return driveA - driveB;
    }

    if (sortValue === "price-asc") {
      return priceA - priceB;
    }

    if (sortValue === "acres-desc") {
      return acresB - acresA;
    }

    if (sortValue === "updated-desc") {
      return updatedB - updatedA;
    }

    return scoreB - scoreA;
  });

  return filtered;
}

function renderInvestorDashboard() {
  const filtered = getFilteredInvestorProperties();

  renderInvestorStats(filtered);
  renderInvestorMap(filtered);
  renderInvestorCards(filtered);

  if (investorLoading) {
    investorLoading.hidden = true;
  }

  if (investorEmpty) {
    investorEmpty.hidden = filtered.length > 0;
  }
}

function renderInvestorMap(properties) {
  if (!investorMapElement || typeof L === "undefined") {
    return;
  }

  const propertiesWithLocation = properties
    .map((property, index) => {
      const lat = getLatitude(property);
      const lng = getLongitude(property);

      if (!lat || !lng) {
        return null;
      }

      return {
        property,
        index,
        lat,
        lng
      };
    })
    .filter(Boolean);

  if (!investorMap) {
    investorMap = L.map(investorMapElement, {
      scrollWheelZoom: false,
      zoomControl: true
    }).setView([UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude], 9);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(investorMap);

    investorMapLayer = L.layerGroup().addTo(investorMap);
  }

  investorMapLayer.clearLayers();

  const uptownIcon = L.divIcon({
    className: "leaflet-clt-marker",
    html: "<span>CLT</span>",
    iconSize: [48, 48],
    iconAnchor: [24, 24]
  });

  L.marker([UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude], {
    icon: uptownIcon
  })
    .addTo(investorMapLayer)
    .bindPopup("<strong>Uptown Charlotte</strong><br>Drive-time reference point");

  L.circle([UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude], {
    radius: 56327,
    className: "leaflet-drive-ring leaflet-drive-ring-one",
    fill: false
  }).addTo(investorMapLayer);

  L.circle([UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude], {
    radius: 88514,
    className: "leaflet-drive-ring leaflet-drive-ring-two",
    fill: false
  }).addTo(investorMapLayer);

  propertiesWithLocation.forEach(({ property, index, lat, lng }) => {
    const name = getPropertyDisplayName(property, `Site ${index + 1}`);
    const corridor =
      normalizeInvestorValue(getPropertyField(property, ["Corridor", "corridor"])) ||
      "Corridor TBD";
    const score =
      normalizeInvestorValue(
        getPropertyField(property, ["Weighted Polo Score", "Score", "score"])
      ) || "—";
    const driveTime = formatDriveTime(property);
    const acres = getPropertyField(property, ["Acreage", "Acres", "acres"]);
    const price = getPropertyField(property, ["List Price", "Price", "price"]);
    const listingUrl = getListingUrl(property);
    const cardId = slugify(name) || `property-${index + 1}`;

    const icon = L.divIcon({
      className: isShortlistProperty(property)
        ? "leaflet-property-marker leaflet-property-marker-priority"
        : "leaflet-property-marker",
      html: "<span></span>",
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    const listingAction = listingUrl
      ? `<a href="${escapeAttribute(listingUrl)}" target="_blank" rel="noopener noreferrer">Open Listing</a>`
      : "";

    const popup = `
      <div class="map-popup">
        <strong>${escapeHtml(name)}</strong>
        <span>${escapeHtml(corridor)} · ${escapeHtml(driveTime)} · Score ${escapeHtml(score)}</span>
        <div class="map-popup-meta">
          <small>${formatNumber(acres, 1)} acres</small>
          <small>${formatCurrency(price)}</small>
        </div>
        <div class="map-popup-actions">
          <button type="button" data-target="${escapeAttribute(cardId)}">View Card</button>
          ${listingAction}
        </div>
      </div>
    `;

    const marker = L.marker([lat, lng], { icon })
      .addTo(investorMapLayer)
      .bindPopup(popup);

    marker.on("popupopen", () => {
      const popupElement = document.querySelector(".leaflet-popup-content");
      const button = popupElement
        ? popupElement.querySelector(`button[data-target="${cardId}"]`)
        : null;

      if (button) {
        button.addEventListener("click", () => {
          const target = document.getElementById(cardId);

          if (target) {
            target.scrollIntoView({
              behavior: "smooth",
              block: "center"
            });

            target.classList.add("property-card-highlight");

            window.setTimeout(() => {
              target.classList.remove("property-card-highlight");
            }, 1400);
          }
        });
      }
    });
  });

  const boundsItems = [
    [UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude],
    ...propertiesWithLocation.map((item) => [item.lat, item.lng])
  ];

  if (boundsItems.length > 1) {
    investorMap.fitBounds(boundsItems, {
      padding: [42, 42],
      maxZoom: 10
    });
  } else {
    investorMap.setView([UPTOWN_CHARLOTTE.latitude, UPTOWN_CHARLOTTE.longitude], 9);
  }

  window.setTimeout(() => {
    investorMap.invalidateSize();
  }, 150);
}

function renderInvestorStats(properties) {
  if (!investorStats) {
    return;
  }

  const totalSites = properties.length;

  const shortlistSites = properties.filter((property) => {
    return isShortlistProperty(property);
  }).length;

  const scores = properties
    .map((property) =>
      parseInvestorNumber(
        getPropertyField(property, ["Weighted Polo Score", "Score", "score"])
      )
    )
    .filter(Boolean);

  const avgScore = scores.length
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : 0;

  const totalAcres = properties.reduce((sum, property) => {
    return (
      sum +
      parseInvestorNumber(
        getPropertyField(property, ["Acreage", "Acres", "acres"])
      )
    );
  }, 0);

  investorStats.innerHTML = `
    <article class="investor-stat-card">
      <span>50+ Acre Sites</span>
      <strong>${totalSites}</strong>
    </article>

    <article class="investor-stat-card">
      <span>Shortlist Sites</span>
      <strong>${shortlistSites}</strong>
    </article>

    <article class="investor-stat-card">
      <span>Avg. Score</span>
      <strong>${avgScore ? avgScore.toFixed(1) : "—"}</strong>
    </article>

    <article class="investor-stat-card">
      <span>Total 50+ Acres</span>
      <strong>${formatNumber(totalAcres)}</strong>
    </article>
  `;
}

function destroyPropertyMiniMaps() {
  propertyMiniMaps.forEach((miniMap) => {
    if (miniMap && typeof miniMap.remove === "function") {
      miniMap.remove();
    }
  });

  propertyMiniMaps = [];
}

function renderInvestorCards(properties) {
  if (!propertyGrid) {
    return;
  }

  destroyPropertyMiniMaps();

  propertyGrid.innerHTML = properties
    .map((property, index) => {
      const name = getPropertyDisplayName(property);

      const corridor =
        normalizeInvestorValue(
          getPropertyField(property, ["Corridor", "corridor"])
        ) || "Corridor TBD";

      const tier =
        normalizeInvestorValue(
          getPropertyField(property, ["Recommendation Tier", "Tier", "tier"])
        ) || "Review";

      const score =
        normalizeInvestorValue(
          getPropertyField(property, ["Weighted Polo Score", "Score", "score"])
        ) || "—";

      const acreage = getPropertyField(property, ["Acreage", "Acres", "acres"]);

      const price = getPropertyField(property, [
        "List Price",
        "Price",
        "price"
      ]);

      const pricePerAcre = getPropertyField(property, [
        "Price / Acre",
        "Price Per Acre",
        "Price/Acre",
        "price_per_acre"
      ]);

      const county =
        normalizeInvestorValue(
          getPropertyField(property, ["County", "county"])
        ) || "—";

      const status =
        normalizeInvestorValue(
          getPropertyField(property, ["Status", "status"])
        ) || "Active Review";

      const notes =
        normalizeInvestorValue(
          getPropertyField(property, [
            "Polo / Investor Notes",
            "Investor Narrative",
            "Listing Notes",
            "Investor Notes",
            "Notes",
            "notes",
            "Summary"
          ])
        ) || "No investor notes have been added yet.";

      const diligence =
        normalizeInvestorValue(
          getPropertyField(property, [
            "Next Due Diligence",
            "Due Diligence",
            "next_steps"
          ])
        ) ||
        "Confirm listing status, zoning, utilities, access, and field development feasibility.";

      const verificationStatus =
        normalizeInvestorValue(
          getPropertyField(property, [
            "Listing Verification Status",
            "Verification Status",
            "verification_status"
          ])
        ) || "Verification status pending.";

      const listingExternalId = normalizeInvestorValue(
        getPropertyField(property, [
          "Listing External ID",
          "External Listing ID",
          "Listing ID",
          "listing_id"
        ])
      );

      const lastResearched = normalizeInvestorValue(
        getPropertyField(property, [
          "Last Researched",
          "Listing Verified At",
          "Last Updated",
          "Updated"
        ])
      );

      const nearestI77 = normalizeInvestorValue(
        getPropertyField(property, [
          "Nearest I-77 Reference",
          "I-77 Reference",
          "Nearest Interstate"
        ])
      );

      const sourceName = normalizeInvestorValue(
        getPropertyField(property, ["Source", "Scrape Source Name", "source"])
      );

      const listingUrl = getListingUrl(property);

      const driveTime = formatDriveTime(property);
      const driveBand = getDriveBand(property);
      const miles = estimateMilesFromCharlotte(property);
      const cardId = slugify(name) || `property-${index + 1}`;
      const miniMapId = `property-mini-map-${cardId}-${index}`;

      return `
        <article class="property-card" id="${escapeAttribute(cardId)}">
          <div class="property-card-visual">
            <div class="property-card-map property-card-map-real">
              <div class="property-mini-map" id="${escapeAttribute(miniMapId)}"></div>

              <div class="property-map-chips">
                <span>${escapeHtml(corridor)}</span>
                <span class="property-score">${escapeHtml(score)}</span>
              </div>
            </div>

            <div class="property-map-summary">
              <h3>${escapeHtml(name)}</h3>

              <div class="drive-badge">
                <strong>${escapeHtml(driveTime)}</strong>
                <span>${escapeHtml(driveBand)}</span>
              </div>
            </div>
          </div>

          <div class="property-card-body">
            <div class="property-meta-grid">
              <div class="property-meta">
                <span>Tier</span>
                <strong>${escapeHtml(tier)}</strong>
              </div>

              <div class="property-meta">
                <span>Status</span>
                <strong>${escapeHtml(status)}</strong>
              </div>

              <div class="property-meta">
                <span>Acres</span>
                <strong>${formatNumber(acreage, 1)}</strong>
              </div>

              <div class="property-meta">
                <span>County</span>
                <strong>${escapeHtml(county)}</strong>
              </div>

              <div class="property-meta">
                <span>List Price</span>
                <strong>${formatCurrency(price)}</strong>
              </div>

              <div class="property-meta">
                <span>Price / Acre</span>
                <strong>${formatCurrency(pricePerAcre)}</strong>
              </div>

              <div class="property-meta property-meta-wide">
                <span>From Uptown Charlotte</span>
                <strong>${escapeHtml(driveTime)}${miles ? ` · ${formatNumber(miles, 1)} mi` : ""}</strong>
              </div>
            </div>

            <p class="property-note">${escapeHtml(notes)}</p>

            <div class="property-diligence property-verification">
              <span>Source Verification</span>
              <p>${escapeHtml(verificationStatus)}</p>
              <small>
                ${lastResearched ? `Last researched: ${escapeHtml(lastResearched)}` : "Last researched: daily agent pending"}
                ${sourceName ? ` · Source: ${escapeHtml(sourceName)}` : ""}
                ${listingExternalId ? ` · Listing ID: ${escapeHtml(listingExternalId)}` : ""}
                ${nearestI77 ? ` · ${escapeHtml(nearestI77)}` : ""}
              </small>
            </div>

            <div class="property-diligence">
              <span>Next Diligence</span>
              <p>${escapeHtml(diligence)}</p>
            </div>

            <div class="property-actions property-actions-single">
              ${listingUrl
          ? `<a class="button button-primary" href="${escapeAttribute(
            listingUrl
          )}" target="_blank" rel="noopener noreferrer">View Property Listing</a>`
          : `<span class="button button-disabled">No Direct Listing Available</span>`
        }
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  renderPropertyMiniMaps(properties);
}

function renderPropertyMiniMaps(properties) {
  if (typeof L === "undefined") {
    return;
  }

  properties.forEach((property, index) => {
    const name = getPropertyDisplayName(property);
    const cardId = slugify(name) || `property-${index + 1}`;
    const miniMapId = `property-mini-map-${cardId}-${index}`;
    const mapElement = document.getElementById(miniMapId);

    if (!mapElement) {
      return;
    }

    const lat = getLatitude(property);
    const lng = getLongitude(property);

    if (!lat || !lng) {
      mapElement.innerHTML = `
        <div class="mini-map-missing">
          <span>Coordinates needed</span>
          <strong>Add Latitude + Longitude</strong>
        </div>
      `;
      return;
    }

    const miniMap = L.map(mapElement, {
      attributionControl: false,
      zoomControl: false,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      tap: false,
      touchZoom: false
    }).setView([lat, lng], 11);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18
    }).addTo(miniMap);

    const icon = L.divIcon({
      className: isShortlistProperty(property)
        ? "leaflet-property-marker leaflet-property-marker-priority"
        : "leaflet-property-marker",
      html: "<span></span>",
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    L.marker([lat, lng], { icon }).addTo(miniMap);

    propertyMiniMaps.push(miniMap);

    window.setTimeout(() => {
      miniMap.invalidateSize();
    }, 160);
  });
}

function escapeHtml(value) {
  return normalizeInvestorValue(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

if (investorCodeForm) {
  const hasAccess = sessionStorage.getItem(INVESTOR_ACCESS_KEY) === "true";

  if (hasAccess) {
    showInvestorDashboard();
  }

  investorCodeForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const enteredCode = investorCodeInput ? investorCodeInput.value.trim() : "";

    if (enteredCode === INVESTOR_ACCESS_CODE) {
      sessionStorage.setItem(INVESTOR_ACCESS_KEY, "true");

      if (investorLock) {
        investorLock.style.display = "none";
        investorLock.hidden = true;
      }

      if (investorDashboard) {
        investorDashboard.hidden = false;
        investorDashboard.style.display = "block";
      }

      loadInvestorProperties();
      return;
    }

    if (investorCodeError) {
      investorCodeError.hidden = false;
      investorCodeError.style.display = "block";
    }

    if (investorCodeInput) {
      investorCodeInput.value = "";
      investorCodeInput.focus();
    }
  });
}

[investorSearch, corridorFilter, tierFilter, sortFilter].forEach((control) => {
  if (control) {
    control.addEventListener("input", renderInvestorDashboard);
    control.addEventListener("change", renderInvestorDashboard);
  }
});

if (refreshInvestorData) {
  refreshInvestorData.addEventListener("click", loadInvestorProperties);
}

if (runPropertyAgent) {
  runPropertyAgent.addEventListener("click", triggerPropertyAgentRefresh);
}
