"""Actual checked-in UI/CSS/rules, mocked external services; never exercises paid APIs."""
import functools,json,os,re,shutil,threading
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
BRIEF=json.loads((ROOT/'data/property-search-brief.json').read_text())
TODAY=datetime.now(timezone.utc).date().isoformat()
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base={'ID':'fixture-flat','Property Name':'Documented arena candidate','Acres':'20','Latitude':'35.01','Longitude':'-80.95','City':'Rock Hill','County':'York County','State':'SC','Status':'Available','Property URL':'https://example.org/land','Terrain Status':'verified-flat','Terrain Evidence':'https://example.org/survey','Terrain Checked At':TODAY,'Corridor Status':'verified','Corridor Evidence':'https://example.org/access','Corridor Checked At':TODAY,'Verified Drive Minutes':'45','Drive Origin':'Uptown Charlotte','Drive Evidence':'https://example.org/route','Drive Checked At':TODAY,'Arena Fit':'verified','Grass Fit':'verified-training','Layout Evidence':'https://example.org/layout','Layout Checked At':TODAY,'Listing Verified At':'2026-05-11T22:30:00Z'}
properties=[base,{**base,'ID':'fixture-unknown','Property Name':'<img src=x onerror="window.injected=true">','Terrain Status':'unverified'},{**base,'ID':'fixture-small','Property Name':'Too small','Acres':'19.9'}]
state={'started':False,'dispatch_fails':True}
def data():
    return {'schemaVersion':2,'generatedAt':datetime.now(timezone.utc).isoformat(),'brief':BRIEF,'properties':properties,'health':{'status':'limited','message':'Only the configured broker sources were checked.','sources':[],'attemptedAt':datetime.now(timezone.utc).isoformat()},'latestListingReviewAt':'2026-05-11T22:30:00Z','workflowRunId':'42' if state['started'] else '1'}
def fulfill(route,payload,status=200):
    route.fulfill(status=status,content_type='application/json',headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'content-type'},body=json.dumps(payload))
with sync_playwright() as p:
    executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
    browser=p.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("const real=setTimeout;window.setTimeout=(fn,ms,...args)=>real(fn,[5000,30000].includes(ms)?25:ms,...args);")
    page.route(re.compile(r'^https://unpkg\.com/'),lambda route:route.abort())
    page.route(re.compile(r'^https://raw\.githubusercontent\.com/.*/property-research\.json'),lambda route:fulfill(route,data()))
    def runs(route):
        run={'id':42 if state['started'] else 1,'head_branch':'main','event':'workflow_dispatch','created_at':datetime.now(timezone.utc).isoformat(),'status':'completed','conclusion':'success'}
        fulfill(route,{'workflow_runs':[run]})
    page.route(re.compile(r'^https://api\.github\.com/.*/runs\?'),runs)
    def worker(route):
        if route.request.url.endswith('/votes'):fulfill(route,{'message':'Use POST'},405)
        elif state['dispatch_fails']:fulfill(route,{'message':'Service unavailable'},405)
        else:state['started']=True;fulfill(route,{'message':'Accepted'},202)
    page.route(re.compile(r'^https://refresh-properties\.charlottepolo-refresh\.workers\.dev'),worker)
    page.goto(f'http://127.0.0.1:{server.server_port}/investors/')
    page.locator('#investorCode').fill('wrong');page.get_by_role('button',name='Open research').click();assert page.locator('#investorCodeError').is_visible()
    page.locator('#investorCode').fill('cltpolo123!');page.get_by_role('button',name='Open research').click()
    try:
        page.wait_for_function("document.querySelectorAll('.property-card').length===2",timeout=10000)
    except Exception:
        print('BROWSER ERRORS',errors)
        print('LOAD NOTICE',page.locator('#propertyAgentStatus').text_content())
        print('BODY',page.locator('body').inner_text()[:5000])
        out=ROOT/'artifacts';out.mkdir(exist_ok=True)
        page.screenshot(path=str(out/'research-failure.png'),full_page=True)
        raise
    assert not page.locator('#propertyGrid img').count();assert page.evaluate('window.injected') is None
    assert 'Map unavailable' in page.locator('#mapStatus').inner_text()
    assert 'unavailable' in page.locator('#voteServiceStatus').inner_text()
    assert not page.locator('[data-vote-id]').count()
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.locator('[data-save-id]').first.click();page.locator('#researchView').select_option('saved');assert page.locator('.property-card').count()==1
    page.reload();page.wait_for_selector('.property-card');page.locator('#researchView').select_option('saved');assert page.locator('.property-card').count()==1
    page.locator('#researchView').select_option('outside');assert page.locator('.property-card').count()==1
    page.locator('#investorSearch').fill('no-such-property');page.wait_for_function("document.querySelectorAll('.property-card').length===0");assert page.locator('#investorEmpty').is_visible()
    page.locator('#resetFilters').click();page.wait_for_function("document.querySelectorAll('.property-card').length===2")
    page.locator('#runPropertyAgent').click();page.wait_for_function("document.getElementById('propertyAgentStatus').textContent.includes('HTTP 405')")
    assert page.locator('#runPropertyAgent').is_enabled();assert len(page.context.pages)==1
    state['dispatch_fails']=False
    page.locator('#runPropertyAgent').click();page.wait_for_function("document.getElementById('propertyAgentStatus').textContent.includes('Workflow finished')")
    assert page.locator('#runPropertyAgent').is_enabled();assert len(page.context.pages)==1
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/'research-mobile.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1000});page.locator('#researchView').select_option('all');assert page.locator('.property-card').count()==3
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.screenshot(path=str(out/'research-desktop.png'),full_page=True)
    assert not errors,errors
    browser.close()
server.shutdown()
print('Browser smoke passed: real UI/rules/CSS; mobile/desktop layout, gate, archive/empty filters, XSS escaping, local saves, missing map/vote services, failed dispatch, in-page completion and no new windows. External services were mocked.')
