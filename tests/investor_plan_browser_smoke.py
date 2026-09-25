"""Deterministic local browser coverage; external property services are deliberately blocked."""
import functools,json,re,threading,os,shutil
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/investors/'
with sync_playwright() as p:
    binary=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
    b=p.chromium.launch(headless=True,**({'executable_path':binary} if binary else {}))
    page=b.new_page(viewport={'width':1440,'height':1000})
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.route(re.compile(r'^https://'),lambda r:r.abort())
    page.add_init_script("sessionStorage.setItem('cltPoloInvestorAccess','true')")
    page.goto(url);page.wait_for_selector('#investmentPlan[data-ready=true]')
    assert page.locator('#ipCompare .ip-property').count()==3
    assert page.locator('#ipSources .ip-source').count()==19
    assert 'Awaiting inputs' in page.locator('#ipCompare').inner_text()
    for width in (360,390,768,1024,1440):
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),f'Page overflow at {width}'
    page.set_viewport_size({'width':1440,'height':1000})
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/'investment-desktop.png'))
    page.locator('#ip-compare').screenshot(path=str(out/'investment-compare.png'))
    page.locator('[data-site="name"]').fill('York trial site <script>alert(1)</script>')
    page.locator('[data-site="name"]').blur()
    assert '<script>' in page.locator('#ipCompare').inner_text()
    assert page.locator('#ipCompare script').count()==0
    page.locator('[data-site="state"]').select_option('SC')
    page.locator('#ipEditor details').first.locator('summary').click()
    for key,value in [('landPrice','1000000'),('taxValue','2000000'),('taxRate','300')]:
        page.locator(f'[data-site="{key}"]').fill(value);page.locator(f'[data-site="{key}"]').blur()
    assert '$36,000' in page.locator('#ipTaxResult').inner_text()
    page.locator('[data-site="taxRate"]').fill('');page.locator('[data-site="taxRate"]').blur()
    assert 'Awaiting inputs' in page.locator('#ipTaxResult').inner_text()
    page.locator('[data-site="taxRate"]').fill('300');page.locator('[data-site="taxRate"]').blur()
    page.locator('[data-site="landPrice"]').fill('-1');page.locator('[data-site="landPrice"]').blur()
    assert page.locator('#ipError').is_visible()
    saved=page.evaluate("JSON.parse(localStorage.getItem('cltPoloInvestmentPlan.v1'))")
    assert saved['sites'][0]['landPrice']==1000000
    page.locator('[data-site="landPrice"]').fill('1000000');page.locator('[data-site="landPrice"]').blur()
    page.locator('#ipSiteTabs [data-select="1"]').click()
    assert page.locator('[data-site="landPrice"]').input_value()==''
    page.locator('[data-site="name"]').fill('Site B independent');page.locator('[data-site="name"]').blur()
    page.reload();page.wait_for_selector('#investmentPlan[data-ready=true]')
    assert 'York trial site' in page.locator('#ipCompare').inner_text()
    assert 'Site B independent' in page.locator('#ipCompare').inner_text()
    with page.expect_download() as download:page.locator('#ipExport').click()
    exported=json.loads(Path(download.value.path()).read_text());assert len(exported['sites'])==3
    page.on('dialog',lambda dialog:dialog.accept())
    snapshot=out/'investment-test-snapshot.json';snapshot.write_text(json.dumps(exported))
    page.locator('#ipImportFile').set_input_files(snapshot)
    page.wait_for_function("document.getElementById('ipSaveStatus').textContent.includes('Saved')")
    bad=out/'investment-invalid.json';bad.write_text('{"version":1,"release":"wrong","sites":[]}')
    page.locator('#ipImportFile').set_input_files(bad)
    page.wait_for_function("document.getElementById('ipError').textContent.includes('Import not applied')")
    # Restore untouched public research for final screenshots and print verification.
    page.evaluate("localStorage.removeItem('cltPoloInvestmentPlan.v1')")
    page.reload();page.wait_for_selector('#investmentPlan[data-ready=true]')
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'investment-mobile.png'))
    page.locator('#ip-capital').screenshot(path=str(out/'investment-capital-mobile.png'))
    page.set_viewport_size({'width':1440,'height':1000});page.locator('#ip-economics').screenshot(path=str(out/'investment-economics.png'))
    page.pdf(path=str(out/'investment-research-preview.pdf'),print_background=True,prefer_css_page_size=True)
    assert not errors,errors
    print('PASS: viewport widths 360/390/768/1024/1440; site isolation; null taxes; invalid inputs; XSS text; local persistence; JSON export/import; print rendering.')
    b.close()
server.shutdown()
