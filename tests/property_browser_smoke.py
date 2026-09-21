"""Real checked-in UI and styles; external services are deterministic mocks."""
import base64,functools,json,os,re,shutil,threading
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
state={'active_run':1,'next_run':42,'dispatch_fails':True,'api_fails':False,'contents_reads':0}
def data(run_id):
    return {'schemaVersion':2,'generatedAt':datetime.now(timezone.utc).isoformat(),'brief':BRIEF,'properties':properties,'health':{'status':'limited','message':'Only the configured broker sources were checked.','sources':[],'attemptedAt':datetime.now(timezone.utc).isoformat()},'latestListingReviewAt':'2026-05-11T22:30:00Z','workflowRunId':str(run_id)}
def fulfill(route,payload,status=200):
    route.fulfill(status=status,content_type='application/json',headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET,POST,OPTIONS','Access-Control-Allow-Headers':'content-type'},body=json.dumps(payload))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("const real=setTimeout;window.setTimeout=(fn,ms,...args)=>real(fn,[5000,30000].includes(ms)?25:ms,...args);")
    page.route(re.compile(r'^https://unpkg\.com/'),lambda route:route.abort())
    # Deliberately stale CDN response even AFTER the workflow finishes.
    page.route(re.compile(r'^https://raw\.githubusercontent\.com/.*/property-research\.json'),lambda route:fulfill(route,data(1)))
    def contents(route):
        state['contents_reads']+=1
        if state['api_fails']:fulfill(route,{'message':'Rate limited'},403)
        else:fulfill(route,{'encoding':'base64','content':base64.b64encode(json.dumps(data(state['active_run'])).encode()).decode()})
    page.route(re.compile(r'^https://api\.github\.com/.*/contents/data/property-research\.json'),contents)
    def runs(route):
        fulfill(route,{'workflow_runs':[{'id':state['active_run'],'head_branch':'main','event':'workflow_dispatch','created_at':datetime.now(timezone.utc).isoformat(),'status':'completed','conclusion':'success'}]})
    page.route(re.compile(r'^https://api\.github\.com/.*/runs\?'),runs)
    def worker(route):
        if route.request.url.endswith('/votes'):fulfill(route,{'message':'Use POST'},405)
        elif state['dispatch_fails']:fulfill(route,{'message':'Unavailable'},405)
        else:state['active_run']=state['next_run'];fulfill(route,{'message':'Accepted'},202)
    page.route(re.compile(r'^https://refresh-properties\.charlottepolo-refresh\.workers\.dev'),worker)
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/investors/')
        page.locator('#investorCode').fill('wrong');page.get_by_role('button',name='Open research').click();assert page.locator('#investorCodeError').is_visible()
        page.locator('#investorCode').fill('cltpolo123!');page.get_by_role('button',name='Open research').click()
        page.wait_for_function("document.querySelectorAll('.property-card').length===2 && document.getElementById('voteServiceStatus').textContent.includes('unavailable')")
        assert not page.locator('#propertyGrid img').count();assert page.evaluate('window.injected') is None
        assert 'Map unavailable' in page.locator('#mapStatus').inner_text();assert not page.locator('[data-vote-id]').count()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.locator('[data-save-id]').first.click();page.locator('#researchView').select_option('saved');assert page.locator('.property-card').count()==1
        page.reload();page.wait_for_selector('.property-card');page.wait_for_function("document.getElementById('voteServiceStatus').textContent.includes('unavailable')")
        page.locator('#researchView').select_option('saved');assert page.locator('.property-card').count()==1
        page.locator('#researchView').select_option('outside');assert page.locator('.property-card').count()==1
        page.locator('#investorSearch').fill('no-such-property');page.wait_for_function("document.querySelectorAll('.property-card').length===0");assert page.locator('#investorEmpty').is_visible()
        page.locator('#resetFilters').click();page.wait_for_function("document.querySelectorAll('.property-card').length===2")
        page.locator('#runPropertyAgent').click();page.wait_for_function("document.getElementById('propertyAgentStatus').textContent.includes('HTTP 405')")
        assert page.locator('#runPropertyAgent').is_enabled();assert len(page.context.pages)==1
        state['dispatch_fails']=False
        page.locator('#runPropertyAgent').click()
        page.wait_for_function("document.getElementById('propertyAgentStatus').dataset.completedRunId==='42' && document.getElementById('investorDashboard').dataset.snapshotRunId==='42'")
        assert state['contents_reads']>0,'Did not exercise stale-CDN fallback'
        assert page.locator('#propertyAgentStatus').get_attribute('data-status')!='error'
        assert page.locator('#runPropertyAgent').is_enabled();assert len(page.context.pages)==1
        state['next_run']=43;state['api_fails']=True
        page.locator('#runPropertyAgent').click()
        page.wait_for_function("document.getElementById('propertyAgentStatus').textContent.includes('matching results snapshot is not available')")
        assert page.locator('#propertyAgentStatus').get_attribute('data-completed-run-id') is None,'Unpublished run must not be labeled loaded'
        assert page.locator('#investorDashboard').get_attribute('data-snapshot-run-id')=='1'
        assert page.locator('#runPropertyAgent').is_enabled();assert not errors,errors
        out=ROOT/'artifacts';out.mkdir(exist_ok=True);page.screenshot(path=str(out/'research-mobile.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':1000});page.locator('#researchView').select_option('all');assert page.locator('.property-card').count()==3
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path=str(out/'research-desktop.png'),full_page=True)
    except Exception:
        print('PAGE ERRORS',errors);print('PAGE STATUS',page.locator('#propertyAgentStatus').text_content())
        out=ROOT/'artifacts';out.mkdir(exist_ok=True);page.screenshot(path=str(out/'research-failure.png'),full_page=True)
        raise
    finally:browser.close();server.shutdown()
print('Browser smoke passed: actual HTML/CSS/JS; mobile/desktop, gate, filters, XSS, local saves, failed services, stale CDN recovery, exact run-ID handoff, and no false success when publication fails. Services mocked.')
