"""Bounded public-source research, durable health reporting, and an atomic UI snapshot.

No browser impersonation, CAPTCHA bypass, API key, or model subscription is used.
CSV remains the editable research ledger; the web page consumes one JSON snapshot.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data/charlotte_polo_properties.csv'
SNAPSHOT = ROOT / 'data/property-research.json'
BRIEF = ROOT / 'data/property-search-brief.json'
AGENT = 'CLTPoloResearch/2.0 (+https://charlottepolo.com/contact)'
MAX_BYTES = 2_000_000
CHECK_FIELDS = {'Listing Checked At', 'Source Check Outcome'}

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def number(value):
    value = str(value if value is not None else '').strip().replace(',', '').replace('$', '')
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value): return None
    result = float(value)
    return result if math.isfinite(result) else None

def safe_url(value, hosts=None):
    try:
        url = urlparse(str(value or '').strip())
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None, 443): return ''
        host = url.hostname.lower()
        if hosts is not None and host not in hosts: return ''
        if not re.fullmatch(r'[a-z0-9.-]+', host) or host in {'localhost'}: return ''
        return urlunparse((url.scheme, url.netloc, url.path, '', url.query, ''))
    except ValueError: return ''

def identity(row):
    return (safe_url(row.get('Property URL') or row.get('Source URL')).rstrip('/') or row.get('ID', '')).lower()

def is_audit(row):
    return bool(re.fullmatch(r'SEARCH-.*-AUDIT', row.get('ID', ''))) or row.get('Priority', '').lower() == 'audit'

def load_ledger(path=LEDGER):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, strict=True)
        fields, rows = reader.fieldnames or [], list(reader)
    if not fields or len(set(fields)) != len(fields): raise ValueError('Missing or duplicate ledger columns')
    if any(None in row or any(v is None for v in row.values()) for row in rows): raise ValueError('Invalid ledger row width')
    seen = set()
    for row in rows:
        if is_audit(row): continue
        key = identity(row)
        if not key or key in seen: raise ValueError('Missing or duplicate property identity')
        seen.add(key)
        if row.get('Acres') and (number(row['Acres']) is None or number(row['Acres']) <= 0): raise ValueError('Invalid acreage')
    return fields, rows

def atomic_json(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)

def write_ledger(path, fields, rows):
    fields = list(dict.fromkeys(fields + [key for row in rows for key in row]))
    temp = path.with_suffix('.csv.tmp')
    try:
        with temp.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        load_ledger(temp)
        temp.replace(path)
    finally: temp.unlink(missing_ok=True)

class Page(HTMLParser):
    """Visible text, primary H1, and exact listing links; scripts are never evaluated."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.heading = [], [], []
        self.skip = 0; self.in_h1 = False; self.h1_done = False
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag in {'script', 'style', 'noscript'}: self.skip += 1
        if self.skip: return
        if tag == 'h1' and not self.h1_done: self.in_h1 = True
        if tag == 'a' and data.get('href'): self.links.append(data['href'])
        if tag in {'div', 'p', 'br', 'li', 'h1', 'h2', 'h3', 'dt', 'dd', 'span'}: self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.skip: self.skip -= 1
        if tag == 'h1' and self.in_h1: self.in_h1 = False; self.h1_done = True
        if not self.skip: self.parts.append(' ')
    def handle_data(self, data):
        if self.skip: return
        self.parts.append(data)
        if self.in_h1: self.heading.append(data)
    @property
    def text(self): return re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
    @property
    def title(self): return re.sub(r'\s+', ' ', ''.join(self.heading)).strip()

class PublicClient:
    """Allowlisted HTTPS, same-allowlist redirects, robots rules, and host circuit breaker."""
    def __init__(self, hosts, pause=0.5):
        self.hosts = set(hosts); self.pause = pause; self.blocked = {}; self.robots = {}; self.last_request = 0
    def raw(self, url):
        url = safe_url(url, self.hosts)
        if not url: raise ValueError('Source URL is outside the configured HTTPS allowlist')
        hosts = self.hosts
        class Redirects(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not safe_url(newurl, hosts): raise ValueError('Source redirected outside the allowlist')
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        time.sleep(max(0, self.pause - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            with build_opener(Redirects()).open(Request(url, headers={'User-Agent':AGENT, 'Accept':'text/html,text/plain;q=0.9'}), timeout=12) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES: return {'ok':False,'http':response.status,'reason':'Source exceeded the size limit'}
                return {'ok':True,'http':response.status,'body':body.decode('utf-8','replace'),'url':response.url}
        except HTTPError as error:
            if error.code in (401,403,429): self.blocked[urlparse(url).hostname] = error.code
            return {'ok':False,'http':error.code,'reason': 'Rate limited' if error.code==429 else 'Access denied' if error.code in (401,403) else 'Source HTTP error'}
        except (URLError, TimeoutError, OSError, ValueError):
            return {'ok':False,'http':None,'reason':'Network, timeout, or redirect failure'}
    def get(self, url):
        url = safe_url(url, self.hosts)
        if not url: return {'ok':False,'http':None,'reason':'Unsupported source host'}
        host = urlparse(url).hostname
        if host in self.blocked: return {'ok':False,'http':self.blocked[host],'reason':'Skipped after this host blocked the first request','skipped':True}
        if host not in self.robots:
            policy = self.raw('https://' + host + '/robots.txt')
            if not policy['ok'] and policy.get('http') != 404:
                self.robots[host] = None
            else:
                robot = RobotFileParser(); robot.parse(policy.get('body','User-agent: *\nDisallow:').splitlines()); self.robots[host] = robot
        robot = self.robots[host]
        if robot is None: return {'ok':False,'http':self.blocked.get(host),'reason':'Robots policy unavailable; no page crawl attempted'}
        if not robot.can_fetch(AGENT, url): return {'ok':False,'http':None,'reason':'Automated access disallowed by robots policy'}
        return self.raw(url)

def listing_links(page, source):
    host = urlparse(source['url']).hostname
    return sorted({url for href in page.links if (url := safe_url(urljoin(source['url'], href), {host})) and re.fullmatch(r'/property/[^/]+/\d+/', urlparse(url).path)})

def parse_broker_listing(markup, url, source, checked_at):
    page = Page(); page.feed(markup)
    if not page.title: return None
    # Ignore neighboring listing cards, footer claims, and unrelated JSON-LD organizations.
    body = page.text.split(page.title, 1)[-1].split('Description', 1)[0][:6000]
    labels = ['ID','Status','Price','Acres','Price Per Acre','Type','Address','City, State','County','Zip Code','Lat/Long','Presented By','Phone','Email']
    pattern = '|'.join(re.escape(label) for label in labels)
    facts = dict(re.findall(r'(' + pattern + r'):\s*(.*?)(?=\s+(?:' + pattern + r'):\s*|$)', body))
    acres = number(facts.get('Acres'))
    external_id = facts.get('ID','').strip()
    if acres is None or acres <= 0 or not external_id.isdigit() or not facts.get('County') or not facts.get('Status'): return None
    county = re.sub(r'\s+County$', '', facts['County'], flags=re.I).strip() + ' County'
    city_state = facts.get('City, State','').rsplit(',', 1)
    state = {'South Carolina':'SC','North Carolina':'NC','SC':'SC','NC':'NC'}.get(city_state[-1].strip(), '')
    if not state: return None
    description = page.text.split('Description', 1)[-1] if 'Description' in page.text else ''
    description = re.split(r'Ask .* About This Property|Nearby Properties|Additional Details', description)[0].strip()[:600]
    row = {'ID':'ALT-' + external_id, 'Dashboard Include':'Yes','Property Name':page.title,
           'Property URL':url,'Source URL':url,'Listing External ID':external_id,
           'Acres':str(acres),'County':county,'City':city_state[0].strip() if len(city_state)>1 else '', 'State':state,
           'Address / Property':facts.get('Address','').strip(), 'Status':facts['Status'].strip(),
           'Source':'Advance Land & Timber','Listing Notes':description,
           'Listing Checked At':checked_at,'Source Check Outcome':'Public broker page parsed; suitability unverified',
           'Listing Verification Status':'Broker source retrieved; confirm availability directly. Terrain, route and polo layout are not verified.',
           'Scrape Source Name':source['name'],'Scrape Source URL':source['url']}
    price = number(facts.get('Price'))
    if price is not None and price>0: row['List Price']=str(price)
    coords = re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*',facts.get('Lat/Long',''))
    if coords and -90<=float(coords[1])<=90 and -180<=float(coords[2])<=180:
        row['Latitude'], row['Longitude'] = coords[1],coords[2]
    return row

def in_discovery_scope(row, brief):
    acres = number(row.get('Acres')); lat = number(row.get('Latitude'))
    return (acres is not None and acres>=brief['minimumAcres'] and row.get('State') in brief['discoveryStates']
            and row.get('County') in brief['discoveryCounties']
            and (lat is None or brief['southernLatitude']<=lat<=brief['origin']['latitude']))

def merge_row(old, observed):
    merged = dict(old)
    # Preserve manual exclusion, analyst IDs, and separately documented site evidence.
    observed = {k:v for k,v in observed.items() if v!='' and k not in {'Dashboard Include','ID'}}
    geometry_changed = any(number(old.get(k)) != number(observed[k]) for k in ('Acres','Latitude','Longitude') if k in observed)
    merged.update(observed)
    if geometry_changed:
        for key in ('Terrain Status','Arena Fit','Grass Fit','Corridor Status','Expansion Status'): merged[key]='unverified'
        merged['Verified Drive Minutes']=''; merged['Usable Flat Acres']=''
    return merged

def refresh(rows, brief, client, checked_at, limit=24):
    results = [dict(row) for row in rows]; indexes = {identity(row):i for i,row in enumerate(rows) if not is_audit(row)}
    health = {'status':'unknown','attemptedAt':checked_at,'finishedAt':None,'sources':[], 'listingChecks':[],
              'rowsAdded':0,'rowsChanged':0,'listingsChecked':0,'coverage':'Limited public-broker discovery; not a complete market search.',
              'pausedPortals':brief.get('pausedPortals',[])}
    discovered = {}
    for source in brief.get('brokerSources',[]):
        response = client.get(source['url'])
        attempt = {'name':source['name'],'url':source['url'],'http':response.get('http'),'status':'failed','listingLinks':0,'note':response.get('reason','')}
        if response['ok']:
            page=Page(); page.feed(response['body']); links=listing_links(page,source)
            if links:
                attempt.update(status='read',listingLinks=len(links),note='Server-rendered listing links read; county and acreage are checked on each listing.')
                for link in links: discovered.setdefault(link, source)
            elif re.search(r'0\s*[-–]\s*0\s+of\s+0\s+Listings', page.text, re.I):
                attempt.update(status='empty-rendered',note='The public page rendered zero listings. Dynamically loaded inventory may be missing; this is not a complete no-results search.')
            else:
                attempt.update(status='unparsed',note='Page responded but no reliable listing inventory was parsed; not treated as an empty search.')
        health['sources'].append(attempt)
    # Recheck only supported broker records. Do not hammer blocked portal archives.
    for row in rows:
        url=safe_url(row.get('Property URL') or row.get('Source URL'))
        if not is_audit(row) and urlparse(url).hostname in client.hosts and '/property/' in url:
            discovered.setdefault(url, {'name':'Tracked broker listing','url':url})
    health['listingLimitReached']=len(discovered)>limit
    for url,source in list(discovered.items())[:limit]:
        response=client.get(url); observed=None
        if response['ok']: observed=parse_broker_listing(response['body'],url,source,checked_at)
        health['listingChecks'].append({'url':url,'http':response.get('http'),'status':'parsed' if observed else 'failed',
                                        'note':response.get('reason','Required listing facts missing' if observed is None else 'Public source facts read')})
        if observed is None: continue
        health['listingsChecked']+=1
        key=identity(observed)
        if key in indexes:
            index=indexes[key]; merged=merge_row(results[index],observed)
            before={k:v for k,v in results[index].items() if k not in CHECK_FIELDS}
            after={k:v for k,v in merged.items() if k not in CHECK_FIELDS}
            if before!=after: health['rowsChanged']+=1
            results[index]=merged
        elif in_discovery_scope(observed,brief):
            for field_name in ('Terrain Status','Arena Fit','Grass Fit','Corridor Status','Expansion Status'): observed[field_name]='unverified'
            observed['Next Due Diligence']='Confirm a contiguous flat arena/support footprint and a separate grass format; verify I-77 south access, a route within 45 minutes of Uptown Charlotte, drainage and permitted use.'
            indexes[key]=len(results);results.append(observed);health['rowsAdded']+=1
    readable=sum(source['status'] in {'read','empty-rendered'} for source in health['sources'])
    health['sourcesRead']=readable;health['sourcesAttempted']=len(health['sources'])
    failures=any(source['status'] in {'failed','unparsed'} for source in health['sources']) or any(row['status']=='failed' for row in health['listingChecks'])
    if not readable: health['status']='blocked'; health['message']='No discovery source produced readable inventory. Saved research is preserved; no successful search is implied.'
    elif failures: health['status']='partial'; health['message']='Some source checks failed. Readable broker records were retained; coverage remains limited.'
    else: health['status']='limited'; health['message']='Public broker pages checked. Major portals remain paused after access blocks; this is a limited search, not full market coverage.'
    health['finishedAt']=now_iso()
    return results,health

def validate_brief(brief):
    if number(brief.get('minimumAcres')) is None or brief['minimumAcres']<=0 or number(brief.get('maximumDriveMinutes')) is None or brief['maximumDriveMinutes']<=0: raise ValueError('Invalid acquisition thresholds')
    if not isinstance(brief.get('weights'),dict) or sum(brief['weights'].values())!=100: raise ValueError('Invalid scoring weights')
    for source in brief.get('brokerSources',[]):
        if not safe_url(source.get('url'), {'www.advancelandandtimber.com'}): raise ValueError('Unsupported broker source')
    return brief

def build_snapshot(rows, brief, health, ledger_path=LEDGER):
    properties=[row for row in rows if not is_audit(row)]
    reviews=[row.get('Listing Checked At') or row.get('Listing Verified At') or row.get('Last Researched','') for row in properties]
    return {'schemaVersion':2,'generatedAt':now_iso(),'brief':brief,'properties':properties,'health':health,
            'ledgerSha256':hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            'latestListingReviewAt':max((date for date in reviews if date),default=None),
            'workflowRunId':os.environ.get('GITHUB_RUN_ID'), 'codeRevision':os.environ.get('GITHUB_SHA')}

def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--snapshot-only',action='store_true');arg.add_argument('--validate-only',action='store_true')
    arg.add_argument('--dry-run',action='store_true');arg.add_argument('--max-listings',type=int,default=24)
    arg.add_argument('--summary-path',type=Path,default=ROOT/'property-refresh-summary.json')
    args=arg.parse_args()
    if not 1<=args.max_listings<=100:arg.error('--max-listings must be between 1 and 100')
    brief=validate_brief(json.loads(BRIEF.read_text()));fields,rows=load_ledger()
    if args.validate_only:
        if SNAPSHOT.exists():
            snapshot=json.loads(SNAPSHOT.read_text())
            if snapshot.get('schemaVersion')!=2 or snapshot['brief']!=brief or snapshot['ledgerSha256']!=hashlib.sha256(LEDGER.read_bytes()).hexdigest(): raise SystemExit('Snapshot is inconsistent with the ledger/brief')
        print('Research ledger and available snapshot validated');return
    previous={}
    if SNAPSHOT.exists():
        try: previous=json.loads(SNAPSHOT.read_text()).get('health',{})
        except (ValueError,AttributeError): pass
    health=previous or {'status':'not-run','message':'This version has not completed a source check. Saved listing dates are unchanged.','sources':[],'pausedPortals':brief.get('pausedPortals',[])}
    updated=rows
    if not args.snapshot_only:
        try:
            hosts={urlparse(source['url']).hostname for source in brief.get('brokerSources',[])}
            updated,health=refresh(rows,brief,PublicClient(hosts),now_iso(),args.max_listings)
        except Exception as exc:
            # Persist an honest failure snapshot even for unexpected parser bugs.
            updated=rows;health={'status':'error','attemptedAt':now_iso(),'finishedAt':now_iso(),'message':'Research job failed; last saved records retained.','errorType':type(exc).__name__,'sources':[],'pausedPortals':brief.get('pausedPortals',[])}
    if not args.dry_run:
        if updated!=rows: write_ledger(LEDGER,fields,updated)
        atomic_json(SNAPSHOT,build_snapshot(updated,brief,health))
    atomic_json(args.summary_path,health)
    print(json.dumps(health,indent=2))
    if health.get('status') in {'blocked','error'} and not args.snapshot_only: raise SystemExit(2)

if __name__=='__main__':main()
