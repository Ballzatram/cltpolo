/* Investor-only controller. Public pages retain their existing script.js bundle. */
(function () {
  "use strict";
  const R = window.PoloResearch;
  const $ = (id) => document.getElementById(id);
  const escape = (value) => R.text(value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const slug = (value) => R.text(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const money = (value) => { const n = R.number(value); return n !== null && n > 0 ? new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:0}).format(n) : "Not established"; };
  const name = (row) => R.field(row, ["Property Name", "Address / Property", "ID"]) || "Unnamed research lead";
  const voteId = (row) => slug(R.field(row, ["ID", "Listing External ID", "Dashboard Slug", "Property URL", "Source URL"]) || name(row));
  const agent = $("runPropertyAgent");
  let brief, entries = [], map, markers, loadSequence = 0, tallies = {}, votesAvailable = false;
  const pendingVotes = new Set();
  function stored(key) { try { return window.localStorage.getItem(key); } catch { return null; } }
  function store(key, value) { try { window.localStorage.setItem(key, value); } catch { /* Page-local state still works. */ } }
  let userVotes = {};
  try { const saved = JSON.parse(stored("cltPoloPropertyVotes") || "{}"); if (saved && typeof saved === "object" && !Array.isArray(saved)) userVotes = saved; } catch { /* Ignore corrupt local state. */ }
  function status(message, type = "info") {
    $("propertyAgentStatus").hidden = false;
    $("propertyAgentStatus").textContent = message;
    $("propertyAgentStatus").dataset.status = type;
  }
  async function responseData(url, kind = "json", options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, {cache:"no-store", ...options, signal:controller.signal});
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      return await (kind === "text" ? response.text() : response.json());
    } finally { window.clearTimeout(timeout); }
  }
  function routeUrl(row) {
    const loc = R.coordinates(row);
    const destination = loc ? `${loc.lat},${loc.lng}` : [R.field(row, ["Address / Property", "Property Name"]),row.City,row.State].filter(Boolean).join(", ");
    return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(`${brief.driveOrigin}, NC`)}&destination=${encodeURIComponent(destination)}&travelmode=driving`;
  }
  function filtered() {
    const query = $("investorSearch").value.trim().toLowerCase(), view = $("researchView").value, terrain = $("terrainFilter").value;
    return entries.filter(({row, fit}) => (view === "all" || view === "active" && fit.status !== "outside" || fit.status === view)
      && (!terrain || (terrain === "verified") === fit.terrainVerified)
      && (!query || Object.values(row).join(" ").toLowerCase().includes(query)))
      .sort((a,b) => R.compare(a,b,$("sortFilter").value));
  }
  function tally(id) { const raw = tallies[id] || {}; return {up: Math.max(0, Number(raw.up) || 0), down: Math.max(0, Number(raw.down) || 0)}; }
  function voteSummary(id) { if (!votesAvailable) return "Vote totals unavailable"; const t = tally(id); return `${t.up} up · ${t.down} down · preference only`; }
  function renderCard({row, fit}, index) {
    const id = voteId(row), listing = R.safeUrl(R.field(row,["Property URL","Source URL"]));
    const proof = fit.checks.map((check) => `<div class="research-check" data-state="${check.state}"><strong>${escape(check.label)} · ${check.state === "pass" ? "Documented" : check.state === "fail" ? "Conflict" : "Unverified"}</strong><p>${escape(check.note)}</p>${check.valid ? `<small><a href="${escape(check.url)}" target="_blank" rel="noopener noreferrer">Review evidence</a> · ${escape(check.date)}</small>` : ""}</div>`).join("");
    const drive = `${fit.driveLabel} from ${brief.driveOrigin}`;
    return `<article class="property-card" id="research-property-${index}">
      <div class="research-card-head"><span class="research-badge" data-state="${fit.status}">${escape(fit.label)}</span><h3>${escape(name(row))}</h3><p>${escape([row.City,row.County,row.State].filter(Boolean).join(" · "))}</p><strong>${fit.status === "outside" ? "Not eligible for the active brief" : `${fit.score}/100 documented-fit points`}</strong></div>
      <div class="property-card-body"><div class="property-meta-grid"><div class="property-meta"><span>Parcel acres</span><strong>${fit.acres ?? "Unverified"}</strong></div><div class="property-meta"><span>List price</span><strong>${escape(money(row["List Price"]))}</strong></div><div class="property-meta property-meta-wide"><span>Drive-time screen</span><strong>${escape(drive)}</strong></div><div class="property-meta property-meta-wide"><span>Usable flat acres</span><strong>${escape(row["Usable Flat Acres"] || "Not established — total acreage is not usable acreage")}</strong></div></div>
      <div class="research-checks">${proof}</div><p class="property-note"><strong>Expansion:</strong> ${escape(fit.expansionLabel)}</p>
      <details><summary>Source notes and diligence</summary><p>${escape(row["Listing Notes"] || "No source notes recorded.")}</p><p><strong>Recorded listing status:</strong> ${escape(row.Status || "Unverified")}</p><p><strong>Source check:</strong> ${escape(row["Listing Verification Status"] || "Unverified")}</p><p><strong>Last source review:</strong> ${escape(row["Listing Verified At"] || row["Last Researched"] || "Not recorded")}</p><p><strong>Next step:</strong> ${escape(row["Next Due Diligence"] || "Confirm contours, drainage, arena/grass layout, access, permitted use, utilities and listing availability.")}</p><p>Historic scores and investor narratives are retained in the CSV but do not control this brief.</p></details>
      <div class="research-card-links">${listing ? `<a class="button button-primary" href="${escape(listing)}" target="_blank" rel="noopener noreferrer">Open source page</a>` : ""}<a class="button button-secondary" href="${escape(routeUrl(row))}" target="_blank" rel="noopener noreferrer">Check driving route</a></div>
      <div class="property-vote" data-vote-panel="${escape(id)}"><span>Team preference — does not verify suitability</span><div><button type="button" class="button button-secondary" data-vote-id="${escape(id)}" data-vote="1" aria-pressed="${Number(userVotes[id]) === 1}" ${votesAvailable && !pendingVotes.has(id) ? "" : "disabled"}>Upvote</button> <button type="button" class="button button-secondary" data-vote-id="${escape(id)}" data-vote="-1" aria-pressed="${Number(userVotes[id]) === -1}" ${votesAvailable && !pendingVotes.has(id) ? "" : "disabled"}>Downvote</button></div><p class="research-vote-status" data-vote-summary role="status">${escape(voteSummary(id))}</p></div></div></article>`;
  }
  function renderMap(items) {
    const located = items.filter(({fit}) => fit.location);
    $("mapStatus").textContent = `${located.length} of ${items.length} visible properties have usable map coordinates. Pin positions are unverified location references.`;
    if (typeof window.L === "undefined") { $("mapStatus").textContent += " Map tiles are unavailable; source and driving-route links still work."; return; }
    const L = window.L;
    if (!map) {
      map = L.map("investorMap", {scrollWheelZoom:false}).setView([35.02,-80.99],9);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom:18, attribution:"&copy; OpenStreetMap contributors"}).addTo(map);
      markers = L.layerGroup().addTo(map);
    }
    markers.clearLayers();
    const origin = [brief.origin.latitude, brief.origin.longitude];
    L.marker(origin).addTo(markers).bindPopup(escape(brief.driveOrigin));
    const bounds = [origin];
    items.forEach(({row,fit},index) => {
      if (!fit.location) return;
      const position = [fit.location.lat,fit.location.lng]; bounds.push(position);
      L.marker(position).addTo(markers).bindPopup(`<strong>${escape(name(row))}</strong><p>${escape(fit.label)} · ${escape(fit.driveLabel)}</p><a href="#research-property-${index}">View property checks</a>`);
    });
    if (bounds.length > 1) map.fitBounds(bounds, {padding:[30,30],maxZoom:11});
    else map.setView([35.02,-80.99],9);
    window.setTimeout(() => map.invalidateSize(),100);
  }
  function render() {
    if (!brief) return;
    const items = filtered();
    const stats = [["Meets documented brief","eligible"],["Needs verification","research"],["Outside brief","outside"]]
      .map(([label,state]) => [label,entries.filter(({fit}) => fit.status === state).length]);
    stats.push(["Tracked properties",entries.length]);
    $("investorStats").innerHTML = stats.map(([label,n]) => `<article class="investor-stat-card"><span>${label}</span><strong>${n}</strong></article>`).join("");
    $("resultCount").textContent = `${items.length} shown of ${entries.length} tracked · brief ${brief.version}`;
    $("propertyGrid").innerHTML = items.map(renderCard).join("");
    $("investorEmpty").hidden = items.length > 0;
    renderMap(items);
  }
  async function load() {
    const sequence = ++loadSequence;
    $("investorLoading").hidden = false; $("propertyGrid").setAttribute("aria-busy","true");
    try {
      const [config,csv] = await Promise.all([responseData("/data/property-search-brief.json"),responseData("/data/charlotte_polo_properties.csv","text")]);
      if (sequence !== loadSequence) return;
      if (!(config.minimumAcres > 0 && config.maximumDriveMinutes > 0 && config.origin && config.weights)) throw new Error("Invalid search brief");
      const nextEntries = R.parseCSV(csv).filter((row) => !R.isAudit(row)).map((row) => ({row,fit:R.evaluate(row,config)}));
      brief = config; entries = nextEntries; votesAvailable = false; render();
      try {
        const data = await responseData(agent.dataset.voteEndpoint);
        if (sequence !== loadSequence) return;
        tallies = data && data.votes && typeof data.votes === "object" ? data.votes : {};
        votesAvailable = true;
      } catch { votesAvailable = false; }
      render();
    } catch (error) { status(`Research data could not be reloaded: ${error.message}. Any visible results are the last successfully loaded snapshot.`,"error"); }
    finally { if (sequence === loadSequence) { $("investorLoading").hidden = true; $("propertyGrid").setAttribute("aria-busy","false"); } }
  }
  async function vote(button) {
    const id = button.dataset.voteId, selected = Number(button.dataset.vote);
    if (pendingVotes.has(id)) return;
    pendingVotes.add(id);
    const previousVote = [1,-1].includes(Number(userVotes[id])) ? Number(userVotes[id]) : 0;
    const nextVote = previousVote === selected ? 0 : selected;
    const panel = button.closest("[data-vote-panel]");
    panel.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      const data = await responseData(agent.dataset.voteEndpoint,"json",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({propertyId:id,vote:nextVote,previousVote})});
      if (!data || !data.votes || !data.votes[id]) throw new Error("No updated vote totals returned");
      tallies[id] = data.votes[id]; if (nextVote) userVotes[id] = nextVote; else delete userVotes[id];
      store("cltPoloPropertyVotes",JSON.stringify(userVotes));
      panel.querySelector("[data-vote-summary]").textContent = voteSummary(id);
      panel.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed",String(Number(b.dataset.vote) === nextVote)));
    } catch (error) { panel.querySelector("[data-vote-summary]").textContent = `Vote not saved: ${error.message}`; }
    finally { pendingVotes.delete(id); panel.querySelectorAll("button").forEach((b) => { b.disabled = false; }); }
  }
  agent.addEventListener("click", async () => {
    agent.disabled = true;
    status("Requesting the property refresh workflow. Results are not updated until the job commits listing changes.","pending");
    try {
      await responseData(agent.dataset.refreshEndpoint,"json",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify({source:"investor-dashboard"})});
      status(`Workflow dispatch accepted, not a completed search. Check ${agent.dataset.actionsUrl}, then reload committed data after completion.`,"success");
    } catch (error) { status(`Could not start the CSV refresh: ${error.message}`,"error"); }
    finally { agent.disabled = false; }
  });
  $("propertyGrid").addEventListener("click",(event) => { const button = event.target.closest("button[data-vote-id]"); if (button && !button.disabled) vote(button); });
  ["researchView","terrainFilter","sortFilter"].forEach((id) => $(id).addEventListener("change",render));
  $("investorSearch").addEventListener("input",render);
  $("refreshInvestorData").addEventListener("click",load);
  $("showOutside").addEventListener("click",() => { $("researchView").value = "outside"; $("terrainFilter").value = ""; $("investorSearch").value = ""; render(); });
  function unlock() { $("investorLock").hidden = true; $("investorLock").style.display = "none"; $("investorDashboard").hidden = false; $("investorDashboard").style.display = "block"; load(); }
  $("investorCodeForm").addEventListener("submit",(event) => {
    event.preventDefault();
    if ($("investorCode").value.trim() === "cltpolo123!") {
      try { window.sessionStorage.setItem("cltPoloInvestorAccess","true"); } catch { /* Continue for this page view. */ }
      $("investorCodeError").hidden = true; unlock();
    } else { $("investorCodeError").hidden = false; $("investorCode").value = ""; $("investorCode").focus(); }
  });
  const nav = document.querySelector(".nav-toggle");
  nav?.addEventListener("click",() => { const open = document.querySelector(".site-nav").classList.toggle("open"); nav.setAttribute("aria-expanded",String(open)); });
  try { if (window.sessionStorage.getItem("cltPoloInvestorAccess") === "true") unlock(); } catch { /* Keep the gate usable with blocked storage. */ }
})();
