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
const INVESTOR_API_URL = "./data/charlotte_polo_properties.csv";

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

const investorSearch = document.getElementById("investorSearch");
const corridorFilter = document.getElementById("corridorFilter");
const tierFilter = document.getElementById("tierFilter");
const sortFilter = document.getElementById("sortFilter");

let investorProperties = [];

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

function showInvestorDashboard() {
  if (!investorLock || !investorDashboard) {
    return;
  }

  investorLock.hidden = true;
  investorDashboard.hidden = false;

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

    const updatedA =
      new Date(
        getPropertyField(a, ["Last Updated", "Updated", "updated_at"])
      ).getTime() || 0;

    const updatedB =
      new Date(
        getPropertyField(b, ["Last Updated", "Updated", "updated_at"])
      ).getTime() || 0;

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
  renderInvestorCards(filtered);

  if (investorLoading) {
    investorLoading.hidden = true;
  }

  if (investorEmpty) {
    investorEmpty.hidden = filtered.length > 0;
  }
}

function renderInvestorStats(properties) {
  if (!investorStats) {
    return;
  }

  const totalSites = properties.length;

  const shortlistSites = properties.filter((property) => {
    const tier = normalizeInvestorValue(
      getPropertyField(property, ["Recommendation Tier", "Tier", "tier"])
    ).toLowerCase();

    return (
      tier.includes("shortlist") ||
      tier.includes("high") ||
      tier.includes("priority")
    );
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
      <span>Total Sites</span>
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
      <span>Total Acres</span>
      <strong>${formatNumber(totalAcres)}</strong>
    </article>
  `;
}

function renderInvestorCards(properties) {
  if (!propertyGrid) {
    return;
  }

  propertyGrid.innerHTML = properties
    .map((property) => {
      const name =
        normalizeInvestorValue(
          getPropertyField(property, [
            "Property Name",
            "Name",
            "Address",
            "property_name"
          ])
        ) || "Unnamed Property";

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

      const listingUrl = normalizeInvestorValue(
        getPropertyField(property, [
          "Listing URL",
          "Listing Link",
          "URL",
          "url"
        ])
      );

      const mapUrl = normalizeInvestorValue(
        getPropertyField(property, [
          "Map URL",
          "Google Maps",
          "Map Link",
          "map_url"
        ])
      );

      return `
        <article class="property-card">
          <div class="property-card-top">
            <div class="property-card-kicker">
              <span>${escapeHtml(corridor)}</span>
              <span class="property-score">${escapeHtml(score)}</span>
            </div>

            <h3>${escapeHtml(name)}</h3>
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
            </div>

            <p class="property-note">${escapeHtml(notes)}</p>

            <div class="property-diligence">
              <span>Next Diligence</span>
              <p>${escapeHtml(diligence)}</p>
            </div>

            <div class="property-actions">
              ${
                listingUrl
                  ? `<a class="button button-primary" href="${escapeAttribute(
                      listingUrl
                    )}" target="_blank" rel="noopener noreferrer">View Listing</a>`
                  : ""
              }

              ${
                mapUrl
                  ? `<a class="button button-secondary" href="${escapeAttribute(
                      mapUrl
                    )}" target="_blank" rel="noopener noreferrer">View Map</a>`
                  : ""
              }
            </div>
          </div>
        </article>
      `;
    })
    .join("");
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

    const enteredCode = investorCodeInput ? investorCodeInput.value : "";

    if (enteredCode === INVESTOR_ACCESS_CODE) {
      sessionStorage.setItem(INVESTOR_ACCESS_KEY, "true");
      showInvestorDashboard();
      return;
    }

    if (investorCodeError) {
      investorCodeError.hidden = false;
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