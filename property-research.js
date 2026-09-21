/* Original investor presentation; source reports and listing changes stay distinct. */
(function () {
  'use strict';
  const R = window.PoloResearch, D = window.PoloResearchData, O = window.PoloResearchOutcome;
  const $ = id => document.getElementById(id);
  const RAW = 'https://raw.githubusercontent.com/Ballzatram/cltpolo/main/';
  const RUNS = 'https://api.github.com/repos/Ballzatram/cltpolo/actions/workflows/267977853/runs?branch=main&per_page=5';
  const agent = $('runPropertyAgent'), reload = $('refreshInvestorData');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const slug = value => String(value ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  const name = row => R.field(row, ['Property Name','Address / Property','ID']) || 'Unnamed research lead';
  const id = row => slug(R.field(row, ['ID','Listing External ID','Dashboard Slug','Property URL','Source URL']) || name(row));
  const date = value => D.timestamp(value) === null ? 'Not established' : new Intl.DateTimeFormat('en-US', {dateStyle:'medium',timeZone:'America/New_York'}).format(new Date(value));
  const money = value => { const n = R.number(value); return n > 0 ? new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(n) : 'Not established'; };
  function read(key, session = false) { try { return JSON.parse((session ? sessionStorage : localStorage).getItem(key) || 'null'); } catch { return null; } }
  function write(key, value, session = false) { try { (session ? sessionStorage : localStorage).setItem(key, JSON.stringify(value)); } catch { /* Page-local state remains usable. */ } }
  let saved = read('cltPoloSavedResearch');
  if (!Array.isArray(saved)) saved = [];
  saved = new Set(saved.filter(value => typeof value === 'string'));
  let userVotes = read('cltPoloPropertyVotes');
  if (!userVotes || typeof userVotes !== 'object' || Array.isArray(userVotes)) userVotes = {};
  let snapshot, entries = [], map, markers, sequence = 0, tallies = {}, votesAvailable = false, watch = null, watchTimer = null;
  let miniMaps = [], miniObserver;
  const pendingVotes = new Set();
  function notice(message, type = 'info') {
    $('propertyAgentStatus').hidden = false;
    $('propertyAgentStatus').textContent = message;
    $('propertyAgentStatus').dataset.status = type;
  }
  async function request(url, options = {}) {
    const {text = false, ...fetchOptions} = options;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(url, {cache:'no-store',credentials:'omit',...fetchOptions,signal:controller.signal});
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = typeof body?.message === 'string' ? `: ${body.message.slice(0,250)}` : '';
        const error = new Error(`HTTP ${response.status}${detail}`); error.status = response.status; throw error;
      }
      return await (text ? response.text() : response.json());
    } finally { clearTimeout(timer); }
  }
  function route(row) {
    const loc = R.coordinates(row);
    const destination = loc ? `${loc.lat},${loc.lng}` : [R.field(row,['Address / Property','Property Name']),row.City,row.State].filter(Boolean).join(', ');
    return `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent('Uptown Charlotte, NC')}&destination=${encodeURIComponent(destination)}&travelmode=driving`;
  }
  function filtered() {
    const query = $('investorSearch').value.trim().toLowerCase(), view = $('researchView').value, terrain = $('terrainFilter').value;
    return entries.filter(({row,fit}) => (view === 'all' || view === 'active' && fit.status !== 'outside' || view === 'saved' && saved.has(id(row)) || view === fit.status)
      && (!terrain || (terrain === 'verified') === fit.terrainVerified)
      && (!query || Object.values(row).join(' ').toLowerCase().includes(query)))
      .sort((a,b) => R.compare(a,b,$('sortFilter').value));
  }
  function sourceHealth(origin) {
    const health = snapshot.health || {};
    $('healthTitle').textContent = D.healthLabel(health);
    $('healthMessage').textContent = health.message || 'No source-health report is available. Loading saved records does not reverify them.';
    $('refreshOutcome').textContent = O.summary(health);
    $('lastAttempt').textContent = O.checkTime(health.attemptedAt);
    $('lastReview').textContent = date(snapshot.latestListingReviewAt);
    $('dataOrigin').textContent = origin;
    $('lastLoaded').textContent = `Results loaded: ${O.checkTime(new Date().toISOString())}. Showing report ${snapshot.workflowRunId ? '#' + snapshot.workflowRunId : 'without a recorded workflow ID'}.`;
    const sources = Array.isArray(health.sources) ? health.sources : [];
    const paused = Array.isArray(health.pausedPortals) ? health.pausedPortals : snapshot.brief.pausedPortals || [];
    $('sourceHealth').innerHTML = sources.map(source => `<div class="source-row"><strong>${escape(source.name)} · ${escape(source.status)}${source.http ? ` · HTTP ${escape(source.http)}` : ''}</strong><p>${escape(source.note || '')}</p></div>`).join('')
      + paused.map(source => `<div class="source-row"><strong>${escape(source.name)} · paused</strong><p>${escape(source.reason)}</p></div>`).join('')
      + `<p>${escape(health.coverage || 'Configured pages do not cover the full land market.')}</p>`;
    $('browseSources').innerHTML = (snapshot.brief.sources || []).slice(0,3).map(source => {
      const url = R.safeUrl(source.url);
      return url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(source.name)}</a>` : '';
    }).join('');
  }
  function card({row,fit,fresh}, index) {
    const key = id(row), url = R.safeUrl(R.field(row,['Property URL','Source URL'])), cardId = `property-${key}-${index}`;
    const checks = fit.checks.map(check => `<div class="check"><strong>${escape(check.label)} · ${check.state === 'pass' ? 'Documented' : check.state === 'fail' ? 'Conflict' : 'Unverified'}</strong><p>${escape(check.note)}</p>${check.valid ? `<a href="${escape(check.url)}" target="_blank" rel="noopener noreferrer">Evidence · ${escape(check.date)}</a>` : ''}</div>`).join('');
    const tally = tallies[key] || {};
    return `<article class="property-card" id="${cardId}">
      <div class="property-card-visual">
        <div class="property-card-map property-card-map-real"><div class="property-mini-map" id="mini-${cardId}" data-item-index="${index}"></div><div class="property-map-chips"><span>${escape(row.Corridor || 'Corridor unverified')}</span></div></div>
        <div class="property-map-summary"><h3>${escape(name(row))}</h3><div class="drive-badge"><strong>${escape(fit.driveLabel)}</strong></div><p class="source-note">${escape([row.City,row.County,row.State].filter(Boolean).join(' · '))}</p></div>
      </div>
      <div class="property-card-body">
        <div class="badges"><span class="badge" data-state="${fit.status}">${escape(fit.label)}</span>${fresh.state !== 'recent' ? `<span class="badge" data-state="${fresh.state}">${fresh.state === 'stale' ? 'Old source review' : 'Review date unknown'}</span>` : ''}</div>
        <dl class="card-facts"><div><dt>Parcel acreage</dt><dd>${fit.acres ?? 'Not established'}</dd></div><div><dt>Recorded asking price</dt><dd>${escape(money(row['List Price']))}</dd></div><div class="wide"><dt>Flat usable footprint</dt><dd>${fit.terrainVerified ? 'Documented — see evidence' : 'Not verified'}${row['Usable Flat Acres'] ? ` · ${escape(row['Usable Flat Acres'])} recorded acres` : ''}</dd></div></dl>
        ${fit.failures.length ? `<p class="conflicts">${escape(fit.failures.slice(0,2).map(check => check.note).join(' · '))}</p>` : ''}
        <p class="source-note">${escape(fresh.label)}${fresh.date ? ` · ${escape(date(fresh.date))}` : ''}. Confirm availability with the broker.</p>
        <details><summary>Required checks${fit.unknown.length ? ` · ${fit.unknown.length} unverified` : ''}</summary>${checks}<p>${escape(fit.expansionLabel)}. ${fit.score}/100 documented research points; not an appraisal.</p></details>
        <details><summary>Source notes &amp; next steps</summary><p>${escape(row['Listing Notes'] || 'No source notes recorded.')}</p><p><strong>Recorded status:</strong> ${escape(row.Status || 'Unverified')}</p><p>${escape(row['Listing Verification Status'] || 'Source details require review.')}</p><p><strong>Next step:</strong> ${escape(row['Next Due Diligence'] || 'Confirm flat footprint, arena/grass layout, access, drainage, permitted use and availability.')}</p></details>
        <div class="card-links">${url ? `<a class="button button-primary" href="${escape(url)}" target="_blank" rel="noopener noreferrer">View source</a>` : ''}<a class="button button-secondary" href="${escape(route(row))}" target="_blank" rel="noopener noreferrer">Check drive</a></div>
        <button class="button button-secondary save-property" type="button" data-save-id="${escape(key)}" aria-pressed="${saved.has(key)}">${saved.has(key) ? 'Saved on this device' : 'Save for review'}</button>
        ${votesAvailable ? `<div class="team-vote" data-vote-panel="${key}"><span>Team preference — not suitability evidence</span><div><button class="button button-secondary" type="button" data-vote-id="${key}" data-vote="1" aria-pressed="${Number(userVotes[key]) === 1}" ${pendingVotes.has(key) ? 'disabled' : ''}>Upvote</button> <button class="button button-secondary" type="button" data-vote-id="${key}" data-vote="-1" aria-pressed="${Number(userVotes[key]) === -1}" ${pendingVotes.has(key) ? 'disabled' : ''}>Downvote</button></div><span role="status" data-vote-summary>${Number(tally.up) || 0} up · ${Number(tally.down) || 0} down</span></div>` : ''}
      </div></article>`;
  }
  function propertyIcon(fit) {
    return window.L.divIcon({className:`leaflet-property-marker${fit.status === 'eligible' ? ' leaflet-property-marker-priority' : fit.status === 'outside' ? ' leaflet-property-marker-archive' : ''}`,html:'<span></span>',iconSize:[28,28],iconAnchor:[14,14]});
  }
  function renderMap(items) {
    const located = items.filter(item => item.fit.location);
    $('mapStatus').textContent = `${located.length} of ${items.length} visible records have coordinates. Outside-brief pins are references, not qualifying matches.`;
    if (typeof window.L === 'undefined') { $('mapStatus').textContent += ' Map unavailable; each property still has a driving-route link.'; return; }
    const L = window.L;
    if (!map) {
      map = L.map('investorMap',{scrollWheelZoom:false}).setView([35.02,-80.99],9);
      const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
      tiles.on('tileerror',() => { $('mapStatus').textContent = 'Map tiles could not load. Driving-route links remain available.'; });
      markers = L.layerGroup().addTo(map);
    }
    markers.clearLayers();
    const origin = [snapshot.brief.origin.latitude,snapshot.brief.origin.longitude], bounds = [origin];
    const originIcon = L.divIcon({className:'leaflet-clt-marker',html:'<span>CLT</span>',iconSize:[48,48],iconAnchor:[24,24]});
    L.marker(origin,{icon:originIcon}).addTo(markers).bindPopup('Uptown Charlotte — drive origin');
    items.forEach(({row,fit},index) => {
      if (!fit.location) return;
      const position = [fit.location.lat,fit.location.lng]; bounds.push(position);
      L.marker(position,{icon:propertyIcon(fit)}).addTo(markers).bindPopup(`<div class="map-popup"><strong>${escape(name(row))}</strong><p>${escape(fit.label)}</p><a href="#property-${id(row)}-${index}">View checks</a></div>`);
    });
    if (bounds.length > 1) map.fitBounds(bounds,{padding:[25,25],maxZoom:11}); else map.setView([35.02,-80.99],9);
    setTimeout(() => map.invalidateSize(),100);
  }
  function destroyMiniMaps() { miniObserver?.disconnect(); miniMaps.forEach(mini => mini.remove()); miniMaps = []; }
  function renderMiniMaps(items) {
    const nodes = [...document.querySelectorAll('.property-mini-map')];
    function mount(node) {
      const fit = items[Number(node.dataset.itemIndex)].fit;
      if (!fit.location || typeof window.L === 'undefined') {
        node.innerHTML = '<div class="mini-map-missing"><span>Location reference</span><strong>Use the Check drive link</strong></div>'; return;
      }
      const L = window.L, position = [fit.location.lat,fit.location.lng];
      const mini = L.map(node,{scrollWheelZoom:false,dragging:false,zoomControl:false,doubleClickZoom:false,touchZoom:false,boxZoom:false,keyboard:false,attributionControl:true}).setView(position,11);
      miniMaps.push(mini);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(mini);
      L.marker(position,{icon:propertyIcon(fit)}).addTo(mini);
    }
    if (typeof window.IntersectionObserver === 'function' && typeof window.L !== 'undefined') {
      miniObserver = new IntersectionObserver(changes => changes.forEach(change => { if (change.isIntersecting) { miniObserver.unobserve(change.target); mount(change.target); } }),{rootMargin:'200px'});
      nodes.forEach(node => miniObserver.observe(node));
    } else nodes.forEach(mount);
  }
  function render() {
    if (!snapshot) return;
    const items = filtered(), active = entries.filter(e => e.fit.status !== 'outside').length, outside = entries.length - active;
    $('investorStats').innerHTML = [['Documented fit',entries.filter(e => e.fit.status === 'eligible').length],['Needs verification',entries.filter(e => e.fit.status === 'research').length],['Outside brief',outside],['Old / unknown source reviews',entries.filter(e => e.fresh.state !== 'recent').length]].map(([label,count]) => `<article class="investor-stat-card"><span>${label}</span><strong>${count}</strong></article>`).join('');
    const visibleOutside = items.filter(e => e.fit.status === 'outside').length;
    $('resultCount').textContent = `${items.length} shown · ${entries.length} tracked · ${visibleOutside} shown outside the brief`;
    $('scopeNotice').textContent = active === 0 && outside > 0 ? `No in-brief leads are recorded yet. ${outside} archived properties remain available for reference; they are not qualified matches.` : `${active} in-brief leads (including unverified research) · ${outside} outside-brief records. Saved preferences apply only to this device.`;
    destroyMiniMaps();
    $('propertyGrid').innerHTML = items.map(card).join('');
    $('investorEmpty').hidden = items.length > 0;
    $('emptyTitle').textContent = $('researchView').value === 'saved' ? 'No saved properties in this view' : 'No properties in this view';
    $('emptyMessage').textContent = entries.length ? 'No records match these filters. Review the archive or reset filters. An empty view does not mean suitable land does not exist.' : 'No research records loaded yet. Source failures and empty searches are reported separately; no shortlist is invented.';
    renderMap(items); renderMiniMaps(items);
  }
  async function contentsSnapshot() {
    const data = await request(`https://api.github.com/repos/Ballzatram/cltpolo/contents/data/property-research.json?ref=main&t=${Date.now()}`);
    if (data.encoding !== 'base64' || typeof data.content !== 'string') throw new Error('Snapshot content is unavailable');
    const bytes = Uint8Array.from(atob(data.content.replace(/\s/g,'')),character => character.charCodeAt(0));
    return D.validate(JSON.parse(new TextDecoder().decode(bytes)));
  }
  async function load(expectedRunId = null, options = {}) {
    const ticket = ++sequence, before = snapshot;
    $('investorLoading').hidden = false; $('propertyGrid').setAttribute('aria-busy','true');
    if (options.announce) { reload.disabled = true; reload.textContent = 'Loading latest report…'; notice('Loading the latest published results; this does not start a new property search.','pending'); }
    try {
      let next, origin = 'Repository snapshot';
      if (options.fresh) { try { next = await contentsSnapshot(); origin = 'Latest repository content'; } catch { /* Fall back to the public snapshot if API access is limited. */ } }
      if (!next) {
        try { next = D.validate(await request(`${RAW}data/property-research.json?t=${Date.now()}`)); }
        catch {
          try { next = D.validate(await request(`/data/property-research.json?t=${Date.now()}`)); origin = 'Deployed fallback — latest repository snapshot unavailable'; }
          catch {
            const [brief,csv] = await Promise.all([request(`${RAW}data/property-search-brief.json?t=${Date.now()}`),request(`${RAW}data/charlotte_polo_properties.csv?t=${Date.now()}`,{text:true})]);
            const rows = R.parseCSV(csv).filter(row => !R.isAudit(row));
            next = D.validate({schemaVersion:2,generatedAt:'1970-01-01T00:00:00Z',brief,properties:rows,health:{status:'not-run',message:'Showing the saved ledger because the report is unavailable. No new source check is implied.',sources:[],pausedPortals:brief.pausedPortals},latestListingReviewAt:rows.map(row => row['Listing Checked At'] || row['Listing Verified At'] || row['Last Researched'] || '').sort().at(-1) || null});
            origin = 'Ledger fallback — source report unavailable';
          }
        }
      }
      if (expectedRunId && String(next.workflowRunId) !== String(expectedRunId)) {
        try { next = await contentsSnapshot(); origin = 'Latest repository content — refresh handoff'; } catch { /* Keep a truthful older report while waiting for publication. */ }
      }
      if (ticket !== sequence) return null;
      const chosen = O.newer(snapshot,next);
      if (chosen !== next) origin = 'Retained newer loaded report — the server returned an older snapshot';
      snapshot = chosen;
      $('investorDashboard').dataset.snapshotRunId = String(snapshot.workflowRunId || '');
      entries = snapshot.properties.map(row => ({row,fit:R.evaluate(row,snapshot.brief),fresh:D.freshness(row,snapshot.brief.listingStaleDays || 30)}));
      sourceHealth(origin); render();
      if (options.announce) notice(O.reloadMessage(before,snapshot));
      return snapshot;
    } catch (error) {
      if (ticket === sequence) notice(`Saved research could not be loaded (${error.message}). Any visible results are the last successfully loaded report.`, 'error');
      return null;
    } finally {
      if (options.announce) { reload.disabled = false; reload.textContent = 'Reload results'; }
      if (ticket === sequence) { $('investorLoading').hidden = true; $('propertyGrid').setAttribute('aria-busy','false'); }
    }
  }
  async function getRuns() { const data = await request(`${RUNS}&t=${Date.now()}`); return Array.isArray(data.workflow_runs) ? data.workflow_runs : []; }
  async function refreshWorkflowLabel() { try { $('workflowStatus').textContent = D.workflowLabel(D.latestRun(await getRuns())); } catch { $('workflowStatus').textContent = 'Live workflow status unavailable. The saved source report remains displayed.'; } }
  function stopWatching() { clearTimeout(watchTimer); watch = null; write('cltPoloResearchWatch',null,true); agent.disabled = false; agent.textContent = 'Check for new properties'; }
  async function poll() {
    if (!watch) return;
    const current = watch;
    if (Date.now() - current.requestedAt > 12 * 60000) { notice('Stopped checking progress after 12 minutes. The workflow may still be running; reload results to check again.'); stopWatching(); return; }
    try {
      const runs = await getRuns(); if (watch !== current) return;
      const run = current.runId ? runs.find(r => r.id === current.runId) : D.dispatchedRun(runs,current.requestedAt,current.baseline);
      if (run) {
        current.runId = run.id; write('cltPoloResearchWatch',current,true); $('workflowStatus').textContent = D.workflowLabel(run);
        if (run.status === 'completed') {
          const loaded = await load(run.id); if (watch !== current) return;
          if (loaded && String(loaded.workflowRunId) === String(run.id)) {
            $('propertyAgentStatus').dataset.completedRunId = String(run.id);
            notice(`Report #${run.id} loaded. ${run.conclusion === 'success' ? '' : D.workflowLabel(run) + '. '}${O.summary(loaded.health)}`,run.conclusion === 'success' ? 'info' : 'error');
            stopWatching(); return;
          }
          current.publishChecks = (current.publishChecks || 0) + 1;
          if (current.publishChecks >= 4) { notice(`${D.workflowLabel(run)}. The matching results snapshot is not available yet; the last successfully loaded report is retained.`,'error'); stopWatching(); return; }
          notice('The job finished. Waiting for its published report; existing property records remain displayed.','pending');
        } else notice(`${D.workflowLabel(run)}. Request made at ${O.checkTime(new Date(current.requestedAt).toISOString())}.`,'pending');
      } else notice('Request accepted. Waiting for the new run to appear; no listing changes have been confirmed.','pending');
    } catch (error) { notice(`Progress could not be checked (${error.message}). The refresh may still be running; saved research is retained.`,'error'); stopWatching(); return; }
    if (watch === current) watchTimer = setTimeout(poll,30000);
  }
  agent.addEventListener('click',async () => {
    if (watch) return;
    delete $('propertyAgentStatus').dataset.completedRunId;
    agent.disabled = true; agent.textContent = 'Starting source check…';
    notice('Starting a source check. New listings will appear only if the collector finds and publishes them.','pending');
    const requestedAt = Date.now(); let baseline = [];
    try { baseline = (await getRuns()).map(run => run.id); } catch { /* Timestamp prevents selecting an old completed run. */ }
    try {
      await request(agent.dataset.refreshEndpoint,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify({source:'investor-dashboard'})});
      watch = {requestedAt,baseline}; write('cltPoloResearchWatch',watch,true);
      agent.textContent = 'Source check in progress'; notice('Request accepted — not a completed search. Progress and change counts will appear here.','pending'); watchTimer = setTimeout(poll,5000);
    } catch (error) { notice(`The refresh service could not start a check (${error.message}). Saved research is unchanged.`,'error'); stopWatching(); }
  });
  async function loadVotes() {
    try {
      const data = await request(agent.dataset.voteEndpoint);
      if (!data || !data.votes || typeof data.votes !== 'object' || Array.isArray(data.votes)) throw new Error('Invalid vote response');
      tallies = data.votes; votesAvailable = true; $('voteServiceStatus').textContent = 'Shared voting is available. Votes are preferences, not evidence.';
    } catch { votesAvailable = false; $('voteServiceStatus').textContent = 'Shared voting is unavailable from the deployed service. Save for review still works locally on this device.'; }
    render();
  }
  async function vote(button) {
    const key = button.dataset.voteId; if (pendingVotes.has(key)) return;
    pendingVotes.add(key);
    const before = [1,-1].includes(Number(userVotes[key])) ? Number(userVotes[key]) : 0, next = before === Number(button.dataset.vote) ? 0 : Number(button.dataset.vote);
    const panel = button.closest('[data-vote-panel]'); panel.querySelectorAll('button').forEach(b => b.disabled = true);
    try {
      const data = await request(agent.dataset.voteEndpoint,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify({propertyId:key,vote:next,previousVote:before})});
      if (!data?.votes?.[key]) throw new Error('No updated totals');
      tallies[key] = data.votes[key]; if (next) userVotes[key] = next; else delete userVotes[key];
      write('cltPoloPropertyVotes',userVotes); pendingVotes.delete(key); render();
    } catch (error) { panel.querySelector('[data-vote-summary]').textContent = `Vote was not saved (${error.message}).`; }
    finally { pendingVotes.delete(key); panel.querySelectorAll('button').forEach(b => b.disabled = false); }
  }
  $('propertyGrid').addEventListener('click',event => {
    const save = event.target.closest('[data-save-id]');
    if (save) { const key = save.dataset.saveId; if (saved.has(key)) saved.delete(key); else saved.add(key); write('cltPoloSavedResearch',[...saved]); render(); return; }
    const button = event.target.closest('button[data-vote-id]'); if (button && !button.disabled) vote(button);
  });
  ['researchView','terrainFilter','sortFilter'].forEach(key => $(key).addEventListener('change',render));
  let searchTimer;
  $('investorSearch').addEventListener('input',() => { clearTimeout(searchTimer); searchTimer = setTimeout(render,120); });
  reload.addEventListener('click',() => { load(null,{fresh:true,announce:true}); refreshWorkflowLabel(); });
  function reset(view = 'all') { $('researchView').value = view; $('terrainFilter').value = ''; $('investorSearch').value = ''; render(); }
  $('showOutside').addEventListener('click',() => reset('outside')); $('resetFilters').addEventListener('click',() => reset());
  document.querySelector('.map-details').addEventListener('toggle',() => { if (map) setTimeout(() => map.invalidateSize(),100); });
  const nav = document.querySelector('.nav-toggle');
  nav?.addEventListener('click',() => { const open = $('siteNav').classList.toggle('open'); nav.setAttribute('aria-expanded',String(open)); });
  function unlock() {
    if (!R || !D || !O) { $('investorCodeError').hidden = false; $('investorCodeError').textContent = 'Research scripts could not load. Reload the page to retry.'; return; }
    $('investorLock').hidden = true; $('investorDashboard').hidden = false;
    load(); loadVotes(); refreshWorkflowLabel();
    const resume = read('cltPoloResearchWatch',true);
    if (resume && Number.isFinite(resume.requestedAt) && Array.isArray(resume.baseline) && Date.now() - resume.requestedAt < 12 * 60000) { watch = resume; agent.disabled = true; agent.textContent = 'Checking existing refresh'; poll(); }
  }
  $('investorCodeForm').addEventListener('submit',event => {
    event.preventDefault();
    if ($('investorCode').value.trim() === 'cltpolo123!') { try { sessionStorage.setItem('cltPoloInvestorAccess','true'); } catch {} $('investorCodeError').hidden = true; unlock(); }
    else { $('investorCodeError').hidden = false; $('investorCode').value = ''; $('investorCode').focus(); }
  });
  try { if (sessionStorage.getItem('cltPoloInvestorAccess') === 'true') unlock(); } catch { /* Gate works without browser storage. */ }
})();
