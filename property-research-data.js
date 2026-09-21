/* Pure snapshot/refresh helpers: no credentials, external dependencies or implicit success. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PoloResearchData = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function timestamp(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T|$)/.test(value)) return null;
    const time = Date.parse(value);
    return Number.isFinite(time) ? time : null;
  }
  function validate(snapshot) {
    if (!snapshot || snapshot.schemaVersion !== 2 || !Array.isArray(snapshot.properties)) throw new Error('Unsupported research snapshot');
    const b = snapshot.brief;
    if (!b || b.minimumAcres !== 20 || b.maximumDriveMinutes !== 45 || !b.origin || !b.weights || b.expansionRequired !== false) throw new Error('Snapshot does not match the current brief');
    if (snapshot.properties.some(row => !row || typeof row !== 'object' || Array.isArray(row) || Object.values(row).some(value => typeof value !== 'string'))) throw new Error('Invalid property records');
    if (timestamp(snapshot.generatedAt) === null || !snapshot.health || typeof snapshot.health !== 'object') throw new Error('Snapshot is missing health metadata');
    return snapshot;
  }
  function freshness(row, staleDays = 30, now = Date.now()) {
    const date = row['Listing Checked At'] || row['Listing Verified At'] || row['Last Researched'];
    const time = timestamp(date);
    if (time === null || time > now + 300000) return {state:'unknown',date:null,days:null,label:'Source review date unverified'};
    const days = Math.max(0,Math.floor((now-time)/86400000));
    return {state:days>staleDays?'stale':'recent',date,days,label:days>staleDays?`Source review is ${days} days old`:'Source page checked recently — availability still needs confirmation'};
  }
  function latestRun(runs) {
    return (Array.isArray(runs)?runs:[]).filter(run=>run.head_branch==='main').sort((a,b)=>Number(b.id)-Number(a.id))[0] || null;
  }
  function dispatchedRun(runs, requestedAt, baseline = []) {
    return (Array.isArray(runs)?runs:[]).filter(run=>run.head_branch==='main' && run.event==='workflow_dispatch' && !baseline.includes(run.id) && (timestamp(run.created_at)??0)>=requestedAt-5000).sort((a,b)=>Number(a.id)-Number(b.id))[0] || null;
  }
  function workflowLabel(run) {
    if (!run) return 'Workflow status unavailable';
    if (run.status !== 'completed') return run.status === 'queued' ? 'Research check queued' : 'Research check running';
    return run.conclusion === 'success' ? 'Workflow finished — check source coverage below' : `Workflow ${run.conclusion || 'ended'} — saved research retained`;
  }
  function healthLabel(health) {
    return ({'limited':'Limited source coverage','partial':'Some source checks failed','blocked':'Discovery sources unavailable','error':'Research check failed','not-run':'Source check not run yet'})[health?.status] || 'Source health unknown';
  }
  return {timestamp,validate,freshness,latestRun,dispatchedRun,workflowLabel,healthLabel};
});
