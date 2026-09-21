/* Shared, dependency-free research rules. Legacy scores never establish suitability. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PoloResearch = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const text = (value) => value == null ? "" : String(value).trim();
  function field(row, keys) {
    for (const key of keys) if (text(row[key])) return text(row[key]);
    return "";
  }
  function number(value) {
    const cleaned = text(value).replace(/[$,]/g, "");
    if (!/^-?\d+(?:\.\d+)?$/.test(cleaned)) return null;
    const result = Number(cleaned);
    return Number.isFinite(result) ? result : null;
  }
  function minutes(value) {
    const cleaned = text(value).replace(/\s*(?:minutes?|mins?)\s*$/i, "");
    const match = cleaned.match(/^(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)$/);
    const valueNumber = match ? Math.max(Number(match[1]), Number(match[2])) : number(cleaned);
    return valueNumber !== null && valueNumber > 0 ? valueNumber : null;
  }
  function safeUrl(value) {
    try {
      const url = new URL(text(value));
      return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
    } catch { return ""; }
  }
  function evidence(row, prefix, today) {
    const url = safeUrl(row[`${prefix} Evidence`]);
    const date = text(row[`${prefix} Checked At`]);
    const parsed = /^\d{4}-\d{2}-\d{2}$/.test(date) ? new Date(`${date}T00:00:00Z`) : null;
    const valid = parsed && Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date && date <= today;
    return {valid: Boolean(url && valid), url, date};
  }
  function coordinates(row) {
    const lat = number(row.Latitude), lng = number(row.Longitude);
    return lat !== null && lng !== null && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180 && (lat !== 0 || lng !== 0)
      ? {lat, lng} : null;
  }
  function evaluate(row, brief, today = new Date().toISOString().slice(0, 10)) {
    const checks = [];
    const add = (key, label, state, note, proof = {}) => checks.push({key, label, state, note, ...proof});
    const acres = number(field(row, ["Acres", "Acreage"]));
    const acreagePass = acres !== null && acres >= brief.minimumAcres;
    add("acreage", "Parcel acreage", acreagePass ? "pass" : acres === null ? "unknown" : "fail",
      acres === null ? "Acreage not established" : `${acres} acres; minimum ${brief.minimumAcres}`);

    const location = coordinates(row);
    const corridorStatus = text(row["Corridor Status"]).toLowerCase();
    const corridorProof = evidence(row, "Corridor", today);
    const corridorVerified = corridorStatus === "verified" && corridorProof.valid;
    const legacyCorridor = text(row.Corridor);
    const northOrSouth = location && (location.lat > brief.origin.latitude || location.lat < brief.southernLatitude);
    const otherCorridor = /\bi[ -]?77\s+north\b|\bus[ -]?521\b|\bi[ -]?85\b|\bwestern\b/i.test(legacyCorridor);
    const corridorFail = corridorStatus === "outside" || northOrSouth || (otherCorridor && !corridorVerified);
    add("corridor", "Southern I-77 corridor", corridorFail ? "fail" : corridorVerified ? "pass" : "unknown",
      corridorFail ? "Recorded location/corridor is outside the southern I-77 brief; verify location before reconsidering"
        : corridorVerified ? "Southern I-77 access documented" : "Verify parcel access to I-77 south; a county or nearby map pin is not proof", corridorProof);

    const driveProof = evidence(row, "Drive", today);
    const recordedDrive = minutes(row["Verified Drive Minutes"]);
    const rightOrigin = text(row["Drive Origin"]).toLowerCase() === brief.driveOrigin.toLowerCase();
    const driveVerified = recordedDrive !== null && rightOrigin && driveProof.valid;
    const legacyDrive = minutes(field(row, ["Drive Time From Charlotte", "Est. Drive Min to Charlotte"]));
    const drive = driveVerified ? recordedDrive : legacyDrive;
    const driveFail = drive !== null && drive > brief.maximumDriveMinutes;
    const driveLabel = drive === null ? "Route time unverified" : `${drive} min${driveVerified ? " · route checked" : " · unverified estimate"}`;
    add("drive", `Within ${brief.maximumDriveMinutes} minutes`, driveFail ? "fail" : driveVerified ? "pass" : "unknown",
      `${driveLabel} from ${brief.driveOrigin}${driveFail ? "; outside the current time screen" : "; check the intended day and departure time"}`, driveProof);

    const terrainProof = evidence(row, "Terrain", today);
    const terrainStatus = text(row["Terrain Status"]).toLowerCase();
    const terrainVerified = terrainStatus === "verified-flat" && terrainProof.valid;
    const terrainText = field(row, ["Terrain Notes", "Listing Notes"])
      .replace(/\b(?:no|not|without)\s+(?:steep|rolling|hilly)(?:\s+(?:hills|terrain|slopes))?/gi, "");
    const terrainConflict = /\brolling\s+(?:pasture|hills?|terrain|land)\b|\bhilly\b|\bsteep\s+(?:slopes?|terrain)\b|\bsloping\s+terrain\b/i.test(terrainText);
    const terrainFail = terrainStatus === "unsuitable" || (terrainConflict && !terrainVerified);
    add("terrain", "Flat usable polo footprint", terrainFail ? "fail" : terrainVerified ? "pass" : "unknown",
      terrainFail ? "Terrain conflict: flat polo footprint has not been demonstrated"
        : terrainVerified ? "Contiguous flat usable footprint documented; engineering and drainage review still required"
          : terrainStatus === "claimed-flat" ? "Flatness claimed, not independently established" : "Flatness unverified; pasture, parcel size and old terrain scores are not evidence", terrainProof);

    const layoutProof = evidence(row, "Layout", today);
    const arena = text(row["Arena Fit"]).toLowerCase();
    const grass = text(row["Grass Fit"]).toLowerCase();
    const arenaPass = arena === "verified" && layoutProof.valid;
    const grassPass = ["verified-training", "verified-full-field"].includes(grass) && layoutProof.valid;
    add("arena", "Arena-first layout", arena === "unsuitable" ? "fail" : arenaPass ? "pass" : "unknown",
      arenaPass ? "Arena, safe access and support footprint documented" : arena === "unsuitable" ? "Arena layout recorded as unsuitable" : "Lay out the arena first, with horse/trailer circulation, parking and support areas", layoutProof);
    add("grass", "Grass polo format", grass === "unsuitable" ? "fail" : grassPass ? "pass" : "unknown",
      grassPass ? grass === "verified-full-field" ? "Full-field grass footprint documented" : "Training / reduced grass format documented; not a full-size field"
        : grass === "unsuitable" ? "Grass format recorded as unsuitable" : "Assess a grass format separately; 20 total acres does not establish a usable field layout", layoutProof);

    const expansionProof = evidence(row, "Expansion", today);
    const expansion = text(row["Expansion Status"]).toLowerCase();
    const expansionPass = expansion === "verified" && expansionProof.valid;
    const hidden = /^(?:no|false|0)$/i.test(text(row["Dashboard Include"]));
    const inactive = /\b(?:sold|withdrawn|off[ -]market|under contract|pending sale)\b/i.test(text(row.Status));
    if (hidden || inactive) add("availability", "Research availability", "fail", hidden ? "Manually excluded from the working shortlist" : "Recorded listing status is not an available opportunity");
    const failures = checks.filter((check) => check.state === "fail");
    const unknown = checks.filter((check) => check.state === "unknown");
    const status = failures.length ? "outside" : unknown.length ? "research" : "eligible";
    const weights = brief.weights;
    const score = (terrainVerified ? weights.terrain : 0) + (arenaPass ? weights.arena : 0)
      + (grassPass ? weights.grass : 0) + (corridorVerified && driveVerified && !driveFail && !corridorFail ? weights.access : 0)
      + (acreagePass ? weights.acreage : 0) + (expansionPass ? weights.expansion : 0);
    return {status, score, acres, drive, driveVerified, driveLabel, location, checks, failures, unknown,
      terrainVerified, arenaPass, grassPass, expansionPass,
      expansionLabel: expansionPass ? "Documented expansion room (optional)" : expansion === "unavailable" ? "No expansion documented — not disqualifying" : "Expansion unverified — optional",
      label: {eligible: "Meets documented brief", research: "Needs verification", outside: "Outside current brief"}[status]};
  }
  function parseCSV(csv) {
    const rows = [], headers = [];
    let row = [], value = "", quoted = false;
    const pushRow = () => { row.push(value); if (row.some((cell) => cell.trim())) rows.push(row); row = []; value = ""; };
    for (let i = 0; i < csv.length; i++) {
      const c = csv[i];
      if (c === '"') { if (quoted && csv[i + 1] === '"') { value += '"'; i++; } else quoted = !quoted; }
      else if (c === "," && !quoted) { row.push(value); value = ""; }
      else if ((c === "\n" || c === "\r") && !quoted) { if (c === "\r" && csv[i + 1] === "\n") i++; pushRow(); }
      else value += c;
    }
    if (quoted) throw new Error("The research CSV has an unclosed quoted field.");
    if (value || row.length) pushRow();
    if (!rows.length) return [];
    headers.push(...rows.shift().map((header) => header.replace(/^\uFEFF/, "").trim()));
    if (new Set(headers).size !== headers.length) throw new Error("The research CSV has duplicate columns.");
    return rows.map((cells) => {
      if (cells.length !== headers.length) throw new Error("The research CSV has a row with missing or extra columns.");
      return Object.fromEntries(headers.map((header, index) => [header, cells[index].trim()]));
    });
  }
  function isAudit(row) { return /^SEARCH-.*-AUDIT$/.test(text(row.ID)) || text(row.Priority).toLowerCase() === "audit"; }
  function compare(a, b, sort = "fit") {
    const rank = {eligible: 0, research: 1, outside: 2};
    if (rank[a.fit.status] !== rank[b.fit.status]) return rank[a.fit.status] - rank[b.fit.status];
    if (sort === "drive") return (a.fit.drive ?? Infinity) - (b.fit.drive ?? Infinity) || b.fit.score - a.fit.score;
    if (sort === "price") {
      const pa = number(a.row["List Price"]), pb = number(b.row["List Price"]);
      return (pa > 0 ? pa : Infinity) - (pb > 0 ? pb : Infinity) || b.fit.score - a.fit.score;
    }
    if (sort === "acres") return (b.fit.acres ?? -1) - (a.fit.acres ?? -1) || b.fit.score - a.fit.score;
    return b.fit.score - a.fit.score || (a.fit.drive ?? Infinity) - (b.fit.drive ?? Infinity);
  }
  return {text, field, number, minutes, safeUrl, evidence, coordinates, evaluate, parseCSV, isAudit, compare};
});
