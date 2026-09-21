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
CHECK_FIELDS = {'Listing Checked At', 'Source Check Outcome', 'Last Source Attempt At', 'Last Source Attempt Outcome'}
# Publisher identity is selected by a fixed host allowlist, never guessed from a title.
BROKERS = {
    'www.advancelandandtimber.com': ('ALT', 'Advance Land & Timber'),
    'www.mossyoakproperties.com': ('MOP', 'Mossy Oak Properties'),
}

def canonical_listing_url(value):
    url = safe_url(value, set(BROKERS))
    parsed = urlparse(url)
    if not re.fullmatch(r'/property/[^/]+/[0-9]+/?', parsed.path): return ''
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/')+'/', '', '', ''))


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
    url = safe_url(row.get('Property URL') or row.get('Source URL'))
    canonical = canonical_listing_url(url)
    if canonical:
        parsed = urlparse(canonical)
        return parsed.hostname + ':' + parsed.path.rstrip('/').split('/')[-1]
    return (url.rstrip('/') or row.get('ID', '')).lower()

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
        self.skip = 0; self.in_h1 = False; self.h1_done = False; self.heading_end = None
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag in {'script', 'style', 'noscript'}: self.skip += 1
        if self.skip: return
        if tag == 'h1' and not self.h1_done: self.in_h1 = True
        if tag == 'a' and data.get('href'): self.links.append(data['href'])
        if tag in {'div', 'p', 'br', 'li', 'h1', 'h2', 'h3', 'dt', 'dd', 'span'}: self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.skip: self.skip -= 1
        if tag == 'h1' and self.in_h1:
            self.in_h1 = False; self.h1_done = True; self.heading_end = len(self.parts)
        if not self.skip: self.parts.append(' ')
    def handle_data(self, data):
        if self.skip: return
        self.parts.append(data)
        if self.in_h1: self.heading.append(data)
    @property
    def text(self): return re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
    @property
    def title(self): return re.sub(r'\s+', ' ', ''.join(self.heading)).strip()
    @property
    def primary_text(self):
        return re.sub(r'\s+', ' ', ''.join(self.parts[self.heading_end:])).strip() if self.heading_end is not None else ''

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
    return sorted({url for href in page.links
                   if (url := canonical_listing_url(urljoin(source['url'], href)))
                   and urlparse(url).hostname == host})

def source_constraints(description):
    """Paraphrase explicit terrain/access signals, never claim a surveyed flat site.

    Read the complete primary description before summarizing, so a constraint near
    the end is not lost to an arbitrary leading-character truncation. Do not copy
    the broker's marketing description into the public research ledger.
    """
    text = re.sub(r'\b(?:no|not|without)\s+(?:rolling|steep|hilly)(?:\s+(?:hills|terrain|slopes))?', '', description, flags=re.I)
    notes = []
    if re.search(r'\b(?:rolling|sloping|hilly)\s+(?:topography|terrain|land|pasture|hills?)\b|\bgently rolling\b|\bsteep slopes?\b', text, re.I):
        notes.append('Broker describes rolling terrain; a flat usable polo footprint has not been established.')
    elif re.search(r'\b(?:flat|level)\s+(?:land|terrain|topography|pasture)\b|\b(?:lays|lies|is)\s+(?:nearly\s+)?(?:flat|level)\b', text, re.I):
        notes.append('Broker describes flat or level land; that claim is not independent flatness verification.')
    if re.search(r'\b(?:wetlands?|floodplain|flood plain)\b', text, re.I):
        notes.append('Broker mentions wetlands or floodplain; review usable area and drainage.')
    if re.search(r'\bconservation easement\b', text, re.I):
        notes.append('Broker mentions a conservation easement; review permitted development.')
    # Narrow textual signals only, not a geocoded route estimate. Store no minutes
    # as verified evidence. Both common forms below explicitly exceed 45 minutes.
    distant = bool(re.search(r'\b(?:an?|one) hour (?:away )?from Charlotte\b', text, re.I)
                   or re.search(r'\bCharlotte (?:are |is )?(?:both )?(?:just )?(?:over |more than )?(?:an?|one) hour away\b', text, re.I))
    if distant:
        notes.append('Broker describes about an hour or longer from Charlotte; the 45-minute route requirement is not demonstrated.')
    return notes, distant

def parse_broker_listing(markup, url, source, checked_at):
    url = canonical_listing_url(url)
    if not url: return None
    publisher = BROKERS[urlparse(url).hostname]
    page = Page(); page.feed(markup)
    if not page.title: return None
    # Start AFTER the actual H1, not a repeated title in head/navigation markup.
    body = re.split(r'\bDescription\b|\bNearby Properties\b', page.primary_text, maxsplit=1)[0][:8000]
    # External ID/MLS is a real optional label. Without it, the old parser consumed
    # it into the ID value and rejected otherwise valid individual property pages.
    labels = ['External ID/MLS','Price Per Acre','City, State','Presented By','Zip Code',
              'Lat/Long','Status','Price','Acres','Type','Address','County','Phone','Email','ID']
    pattern = '|'.join(re.escape(label) for label in sorted(labels,key=len,reverse=True))
    matches = re.findall(r'(?:^|\s)(' + pattern + r'):\s*(.*?)(?=\s+(?:' + pattern + r'):\s*|$)', body)
    facts = {}
    for key,value in matches:
        if key in facts and facts[key] != value.strip(): return None
        facts[key] = value.strip()
    acres = number(facts.get('Acres'))
    external_id = facts.get('ID','')
    expected_id = urlparse(url).path.rstrip('/').split('/')[-1]
    if acres is None or acres<=0 or not external_id.isdigit() or external_id!=expected_id or not facts.get('County') or not facts.get('Status'): return None
    county = re.sub(r'\s+County$', '', facts['County'], flags=re.I).strip() + ' County'
    city_state = facts.get('City, State','').rsplit(',',1)
    state = {'South Carolina':'SC','North Carolina':'NC','SC':'SC','NC':'NC'}.get(city_state[-1].strip(),'')
    if not state: return None
    description = page.primary_text.split('Description',1)[-1] if 'Description' in page.primary_text else ''
    description = re.split(r'\bMaps\b|Ask .*? About This Property|Nearby Properties|Additional Details',description,maxsplit=1)[0]
    signals,distant = source_constraints(description)
    row = {'ID':publisher[0]+'-'+external_id,'Dashboard Include':'Yes','Property Name':page.title,
           'Property URL':url,'Source URL':url,'Listing External ID':external_id,
           'Acres':str(acres),'County':county,'City':city_state[0].strip() if len(city_state)>1 else '', 'State':state,
           'Address / Property':facts.get('Address',''), 'Status':facts['Status'],
           'Source':publisher[1], 'Listing Notes':' '.join(['Broker lists '+str(acres)+' acres.']+signals+['Polo layout and I-77 access require independent review.']),
           'Listing Checked At':checked_at,'Source Check Outcome':'Public broker facts parsed; suitability unverified',
           'Listing Verification Status':'Broker source retrieved; confirm availability directly. Terrain, route and polo layout are not verified.',
           'Scrape Source Name':source['name'],'Scrape Source URL':source['url'], 'Source Drive Conflict':''}
    if facts.get('External ID/MLS'): row['MLS / External Reference'] = facts['External ID/MLS']
    if distant:
        # An explicitly attributed source conflict, NOT a measured drive time.
        row['Source Drive Conflict'] = 'Broker describes about an hour or longer from Charlotte'
    price = number(facts.get('Price'))
    if price is not None and price>0: row['List Price']=str(price)
    coords = re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*',facts.get('Lat/Long',''))
    if coords and -90<=float(coords[1])<=90 and -180<=float(coords[2])<=180:
        row['Latitude'],row['Longitude']=coords[1],coords[2]
    return row


def in_discovery_scope(row, brief):
    acres = number(row.get('Acres')); lat = number(row.get('Latitude'))
    return (acres is not None and acres>=brief['minimumAcres'] and row.get('State') in brief['discoveryStates']
            and row.get('County') in brief['discoveryCounties']
            and (lat is None or brief['southernLatitude']<=lat<=brief['origin']['latitude']))

def merge_row(old, observed):
    merged = dict(old)
    if 'Source Drive Conflict' in observed: merged['Source Drive Conflict']=observed['Source Drive Conflict']
    # Preserve manual exclusion, analyst IDs, and separately documented site evidence.
    observed = {k:v for k,v in observed.items() if v!='' and k not in {'Dashboard Include','ID'}}
    geometry_changed = any(number(old.get(k)) != number(observed[k]) for k in ('Acres','Latitude','Longitude') if k in observed)
    merged.update(observed)
    if geometry_changed:
        for key in ('Terrain Status','Arena Fit','Grass Fit','Corridor Status','Expansion Status'): merged[key]='unverified'
        merged['Verified Drive Minutes']=''; merged['Usable Flat Acres']=''
    return merged

def refresh(rows, brief, client, checked_at, limit=24, offset=0):
    results=[dict(row) for row in rows]
    indexes={identity(row):i for i,row in enumerate(rows) if not is_audit(row)}
    health={'status':'unknown','attemptedAt':checked_at,'finishedAt':None,'sources':[], 'listingChecks':[],
            'rowsAdded':0,'rowsChanged':0,'listingsChecked':0,'listingPagesAttempted':0,
            'outOfScope':0,'unavailableNewListingsExcluded':0,'changes':[],
            'coverage':'Configured public broker inventory only; not a complete MLS or market search.',
            'pausedPortals':brief.get('pausedPortals',[])}
    discovered={}
    for source in brief.get('brokerSources',[]):
        response=client.get(source['url'])
        attempt={'name':source['name'],'url':source['url'],'http':response.get('http'),
                 'status':'failed','listingLinks':0,'note':response.get('reason','')}
        if response['ok']:
            page=Page();page.feed(response['body']);links=listing_links(page,source)
            count=re.search(r'(\d+)\s*[-–]\s*(\d+)\s+of\s+([\d,]+)\s+Listings',page.text,re.I)
            if count: attempt['reportedTotal']=int(count[3].replace(',',''))
            if links:
                attempt.update(status='read',listingLinks=len(links),note='Listing links collected; each property is parsed and screened separately.')
                if count and len(links)<attempt['reportedTotal']:
                    attempt['inventoryTruncated']=True
                    attempt['note']='Only part of this source inventory was collected; pagination coverage is incomplete.'
                for link in links:discovered.setdefault(link,source)
            elif count and int(count[3].replace(',',''))==0:
                attempt.update(status='empty-rendered',note='This broker county page reports zero listings; not evidence of zero listings in the market.')
            else:
                attempt.update(status='unparsed',note='Page responded but no reliable listing inventory was extracted.')
        health['sources'].append(attempt)
    # Keep established records current even when they drop out of discovery indexes.
    source_by_host={urlparse(s['url']).hostname:s for s in brief.get('brokerSources',[])}
    for row in rows:
        url=canonical_listing_url(row.get('Property URL') or row.get('Source URL'))
        if not is_audit(row) and url and urlparse(url).hostname in client.hosts:
            discovered.setdefault(url,source_by_host.get(urlparse(url).hostname,{'name':'Tracked broker listing','url':url}))
    # A changed title/URL slug on the same publisher listing must not duplicate a record.
    unique={}
    for url,source in discovered.items():unique.setdefault(identity({'Property URL':url}),(url,source))
    discovered=dict(unique.values())
    health['listingUrlsDiscovered']=len(discovered)
    health['listingLimitReached']=len(discovered)>limit
    candidates=list(discovered.items())
    start=(offset%len(candidates)) if candidates else 0
    candidates=(candidates[start:]+candidates[:start])[:limit]
    health['nextListingOffset']=((start+len(candidates))%len(discovered)) if discovered else 0
    for url,source in candidates:
        response=client.get(url);observed=None
        health['listingPagesAttempted']+=1
        if response['ok']:observed=parse_broker_listing(response['body'],url,source,checked_at)
        check={'url':url,'source':source['name'],'http':response.get('http'),'status':'parsed' if observed else 'failed',
               'note':response.get('reason','Required primary listing facts missing' if observed is None else 'Individual broker property facts read')}
        health['listingChecks'].append(check)
        if observed is None:continue
        health['listingsChecked']+=1
        key=identity(observed)
        if key in indexes:
            index=indexes[key];merged=merge_row(results[index],observed)
            before={k:v for k,v in results[index].items() if k not in CHECK_FIELDS}
            after={k:v for k,v in merged.items() if k not in CHECK_FIELDS}
            if before!=after:
                health['rowsChanged']+=1
                fields=[k for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
                health['changes'].append({'id':results[index]['ID'],'kind':'updated','fields':fields})
            results[index]=merged;check['result']='existing-record-rechecked'
        elif not in_discovery_scope(observed,brief):
            health['outOfScope']+=1;check['result']='outside-discovery-scope'
        elif re.search(r'\b(?:sold|under contract|pending|withdrawn|off[ -]market)\b',observed['Status'],re.I):
            health['unavailableNewListingsExcluded']+=1;check['result']='unavailable-new-record-excluded'
        else:
            for name in ('Terrain Status','Arena Fit','Grass Fit','Corridor Status','Expansion Status'):observed[name]='unverified'
            observed['Next Due Diligence']='Confirm a contiguous flat arena/support footprint and separate grass format; verify I-77 south access, an Uptown route within 45 minutes, drainage and permitted use.'
            indexes[key]=len(results);results.append(observed);health['rowsAdded']+=1
            health['changes'].append({'id':observed['ID'],'kind':'added','fields':[]});check['result']='new-unverified-research-record'
    readable=sum(s['status'] in {'read','empty-rendered'} for s in health['sources'])
    health['sourcesRead']=readable;health['sourcesAttempted']=len(health['sources'])
    health['listingRefreshSucceeded']=health['listingsChecked']>0
    failures=any(s['status'] in {'failed','unparsed'} or s.get('inventoryTruncated') for s in health['sources']) or any(r['status']=='failed' for r in health['listingChecks'])
    if not readable and not health['listingsChecked']:
        health['status']='blocked';health['message']='No discovery source or tracked property produced usable listing data. Saved research retained.'
    elif not health['listingsChecked']:
        health['status']='error';health['message']='No individual listing pages were successfully parsed. Index pages responded, but no listings were refreshed. Saved research retained.'
    else:
        health['status']='partial' if failures or health['listingLimitReached'] else 'limited'
        health['message']=f"Parsed {health['listingsChecked']} individual listing pages; added {health['rowsAdded']} research records and changed {health['rowsChanged']} existing records. Broker coverage is limited; source facts are not verified polo suitability."
        if failures:health['message']+=' Some source pages failed or inventory is incomplete.'
    health['finishedAt']=now_iso()
    return results,health

def validate_brief(brief):
    if number(brief.get('minimumAcres')) is None or brief['minimumAcres']<=0 or number(brief.get('maximumDriveMinutes')) is None or brief['maximumDriveMinutes']<=0: raise ValueError('Invalid acquisition thresholds')
    if not isinstance(brief.get('weights'),dict) or sum(brief['weights'].values())!=100: raise ValueError('Invalid scoring weights')
    for source in brief.get('brokerSources',[]):
        if not safe_url(source.get('url'), set(BROKERS)): raise ValueError('Unsupported broker source')
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
            updated,health=refresh(rows,brief,PublicClient(hosts),now_iso(),args.max_listings,offset=int(previous.get('nextListingOffset',0)))
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
