"""In-memory DOM integration tests for environments with managed navigation restrictions.

Runs the actual page assets with deterministic transport/storage test doubles.
This is not a live-network end-to-end test. The HTTP browser smoke test is separate.
"""
import base64
import json
import os
import re
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'investors/index.html').read_text()
SCRIPTS = re.findall(r'<script src="(/[^"?]+)[^"]*" defer></script>', HTML)
HTML = re.sub(r'<script.*?</script>', '', HTML, flags=re.S)
HTML = re.sub(r'<link[^>]+rel="stylesheet"[^>]*>', '', HTML)
STYLES = '\n'.join((ROOT / f).read_text() for f in ['style.css', 'property-research.css', 'investor-plan.css'])
IMAGE = 'data:image/png;base64,' + base64.b64encode((ROOT / 'Assets/polo_main.png').read_bytes()).decode()
STYLES = STYLES.replace("url('/Assets/polo_main.png')", f"url('{IMAGE}')")
HTML = HTML.replace('</head>', f'<style>{STYLES}</style></head>')


def mount(browser, initial=None):
    page = browser.new_page(viewport={'width':1440, 'height':1000})
    page.set_content(HTML)
    page.evaluate('''([store,plan,properties])=>{
      window.__testStore=store;
      const storage=s=>({getItem:k=>s[k]??null,setItem:(k,v)=>s[k]=String(v),removeItem:k=>delete s[k],clear:()=>Object.keys(s).forEach(k=>delete s[k])});
      Object.defineProperty(window,'localStorage',{value:storage(store),configurable:true});
      Object.defineProperty(window,'sessionStorage',{value:storage({cltPoloInvestorAccess:'true'}),configurable:true});
      window.fetch=async url=>{
        if(String(url).includes('investor-plan.json'))return new Response(JSON.stringify(plan));
        if(String(url).includes('property-research.json'))return new Response(JSON.stringify(properties));
        throw new Error('External service unavailable in deterministic test');
      };
    }''', [initial or {}, json.loads((ROOT/'data/investor-plan.json').read_text()), json.loads((ROOT/'data/property-research.json').read_text())])
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for path in SCRIPTS:
        page.add_script_tag(content=(ROOT/path.lstrip('/')).read_text())
    page.wait_for_selector('#investmentPlan[data-ready=true]')
    return page, errors


def main():
    with sync_playwright() as p:
        binary = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        browser = p.chromium.launch(headless=True, **({'executable_path':binary} if binary else {}))
        page, errors = mount(browser)
        assert page.locator('#ipCompare .ip-property').count() == 3
        assert page.locator('#ipSources .ip-source').count() == 34
        assert page.locator('#ipLand .ip-land-card').count() == 3
        assert '4252-1 Reid Rd' in page.locator('#ipLand').inner_text()
        assert '1700 Westbrook Rd' in page.locator('#ipLand').inner_text()
        for width in (360,390,768,1024,1440):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'), width
        page.locator('[data-site="name"]').fill('York trial <script>alert(1)</script>')
        page.locator('[data-site="name"]').blur()
        assert '<script>' in page.locator('#ipCompare').inner_text()
        assert page.locator('#ipCompare script').count() == 0
        page.locator('[data-site="state"]').select_option('SC')
        page.locator('#ipEditor details').first.locator('summary').click()
        for key,value in [('landPrice','1000000'),('taxValue','2000000'),('taxRate','300')]:
            page.locator(f'[data-site="{key}"]').fill(value)
            page.locator(f'[data-site="{key}"]').blur()
        assert '$36,000' in page.locator('#ipTaxResult').inner_text()
        page.locator('[data-site="taxRate"]').fill('')
        page.locator('[data-site="taxRate"]').blur()
        assert 'Awaiting inputs' in page.locator('#ipTaxResult').inner_text()
        page.locator('[data-site="landPrice"]').fill('-1')
        page.locator('[data-site="landPrice"]').blur()
        assert page.locator('#ipError').is_visible()
        saved = page.evaluate("JSON.parse(localStorage.getItem('cltPoloInvestmentPlan.v1'))")
        assert saved['sites'][0]['landPrice'] == 1000000
        page.locator('#ipSiteTabs [data-select="1"]').click()
        assert page.locator('[data-site="landPrice"]').input_value() == '2106000'
        page.locator('[data-site="name"]').fill('Site B independent')
        page.locator('[data-site="name"]').blur()
        store = page.evaluate('__testStore')
        assert not errors, errors
        page.close()
        page, errors = mount(browser, store)
        assert 'York trial' in page.locator('#ipCompare').inner_text()
        assert 'Site B independent' in page.locator('#ipCompare').inner_text()
        with page.expect_download() as download:
            page.locator('#ipExport').click()
        exported = json.loads(Path(download.value.path()).read_text())
        assert len(exported['sites']) == 3
        page.on('dialog', lambda dialog: dialog.accept())
        page.locator('#ipImportFile').set_input_files({'name':'snapshot.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
        page.wait_for_function("document.getElementById('ipSaveStatus').textContent.includes('Saved')")
        page.locator('#ipImportFile').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':b'{"version":1,"release":"wrong","sites":[]}'})
        page.wait_for_function("document.getElementById('ipError').textContent.includes('Import not applied')")
        assert not errors, errors
        browser.close()
        print('PASS: five viewports, independent sites, tax nullability, validation, escaped text, snapshot reconstruction, JSON export/import.')


if __name__ == '__main__':
    main()
