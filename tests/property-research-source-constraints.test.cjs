const test = require('node:test');
const assert = require('node:assert/strict');
const R = require('../property-research-core.js');
const brief = require('../data/property-search-brief.json');
const claim = 'Broker describes about an hour or longer from Charlotte';
test('an explicit broker travel conflict is outside the time screen, not a fabricated measured route', () => {
  const fit=R.evaluate({Acres:'35.9','Source Drive Conflict':claim},brief,'2026-09-21');
  assert.equal(fit.status,'outside');assert.equal(fit.drive,null);assert.equal(fit.driveVerified,false);
  assert.match(fit.checks.find(c=>c.key==='drive').note,/source claim, not a measured route/);
});
test('a documented within-limit route can resolve the source claim', () => {
  const fit=R.evaluate({Acres:'35.9','Source Drive Conflict':claim,'Verified Drive Minutes':'40','Drive Origin':'Uptown Charlotte','Drive Evidence':'https://example.org/route','Drive Checked At':'2026-09-21'},brief,'2026-09-21');
  assert.equal(fit.checks.find(c=>c.key==='drive').state,'pass');
});
test('scraped rolling signal never counts as terrain qualification', () => {
  const fit=R.evaluate({Acres:'22.5','Listing Notes':'Broker describes rolling terrain; a flat usable footprint has not been established.'},brief);
  assert.equal(fit.status,'outside');assert.equal(fit.terrainVerified,false);
});
