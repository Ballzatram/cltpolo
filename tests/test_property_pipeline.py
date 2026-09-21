import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import property_pipeline as P
BRIEF=json.loads((ROOT/'data/property-search-brief.json').read_text())
URL='https://www.advancelandandtimber.com/property/test-york-south-carolina/123456/'
SOURCE={'name':'Test broker','url':'https://www.advancelandandtimber.com/property-listings/south-carolina/york-county/'}
HTML='''<h1>Test parcel</h1><div>ID: 123456</div><div>Status: Available</div><div>Price: $500,000</div><div>Acres: 20</div><div>Price Per Acre: $25,000</div><div>Type: Land</div><div>Address: Test Road</div><div>City, State: Rock Hill, South Carolina</div><div>County: York</div><div>Zip Code: 29730</div><div>Lat/Long: 35.01, -80.95</div><div>Presented By: Test broker</div><h2>Description</h2><p>Listing claims flat land; needs review.</p>'''
class Client:
    hosts={'www.advancelandandtimber.com'}
    def __init__(self,responses): self.responses=responses
    def get(self,url): return self.responses.get(url,{'ok':False,'http':403,'reason':'Access denied'})
class PipelineTests(unittest.TestCase):
    def candidate(self):return P.parse_broker_listing(HTML,URL,SOURCE,'2026-09-21T12:00:00Z')
    def test_parses_primary_listing_not_price_per_acre(self):
        row=self.candidate();self.assertEqual(row['List Price'],'500000.0');self.assertEqual(row['Acres'],'20.0');self.assertEqual(row['County'],'York County')
    def test_price_per_acre_never_becomes_total_price(self):
        row=P.parse_broker_listing(HTML.replace('<div>Price: $500,000</div>',''),URL,SOURCE,'2026-09-21');self.assertNotIn('List Price',row)
    def test_missing_required_facts_not_a_listing(self):self.assertIsNone(P.parse_broker_listing('<h1>Land</h1>20 acres from $1',URL,SOURCE,'2026-09-21'))
    def test_scripts_do_not_supply_listing_facts(self):self.assertIsNone(P.parse_broker_listing('<h1>Land</h1><script>'+HTML+'</script>',URL,SOURCE,'2026-09-21'))
    def test_county_and_state_both_required(self):self.assertIsNone(P.parse_broker_listing(HTML.replace('South Carolina','Texas'),URL,SOURCE,'2026-09-21'))
    def test_twenty_is_inclusive(self):self.assertTrue(P.in_discovery_scope(self.candidate(),BRIEF))
    def test_under_twenty_not_discovered(self):row=self.candidate();row['Acres']='19.99';self.assertFalse(P.in_discovery_scope(row,BRIEF))
    def test_wrong_county_excluded(self):row=self.candidate();row['County']='Union County';self.assertFalse(P.in_discovery_scope(row,BRIEF))
    def test_north_excluded(self):row=self.candidate();row['Latitude']='35.9';self.assertFalse(P.in_discovery_scope(row,BRIEF))
    def test_https_allowlist(self):
        for url in ['http://example.org','https://user:pass@example.org','https://localhost/x','javascript:alert(1)','https://127.0.0.1/a']:
            self.assertEqual(P.safe_url(url,{'www.advancelandandtimber.com'}),'')
    def test_discovery_links_stay_on_broker_host(self):
        page=P.Page();page.feed(f'<a href="{URL}">yes</a><a href="https://example.org/property/a/123/">no</a><a href="/property-listings/">no</a>');self.assertEqual(P.listing_links(page,SOURCE),[URL])
    def test_blocked_source_preserves_rows(self):
        old=[{'ID':'x','Acres':'100','Property URL':'https://www.landsearch.com/properties/x/123456','Last Researched':'2026-05-13'}]
        rows,health=P.refresh(old,BRIEF,Client({}),'2026-09-21');self.assertEqual(rows,old);self.assertEqual(health['status'],'blocked')
    def test_http200_without_inventory_is_not_success(self):
        rows,health=P.refresh([],{'brokerSources':[SOURCE]},Client({SOURCE['url']:{'ok':True,'http':200,'body':'<h1>Access challenge</h1>'}}),'2026-09-21');self.assertEqual(health['status'],'blocked');self.assertEqual(health['sources'][0]['status'],'unparsed')
    def test_rendered_zero_is_limited_not_market_zero(self):
        rows,health=P.refresh([],{'brokerSources':[SOURCE]},Client({SOURCE['url']:{'ok':True,'http':200,'body':'<h1>York</h1>0 - 0 of 0 Listings'}}),'2026-09-21');self.assertEqual(health['status'],'limited');self.assertIn('Dynamically',health['sources'][0]['note'])
    def test_new_lead_never_verifies_flatness_or_route(self):
        brief={**BRIEF,'brokerSources':[SOURCE]};client=Client({SOURCE['url']:{'ok':True,'http':200,'body':f'<a href="{URL}">Property</a>'},URL:{'ok':True,'http':200,'body':HTML}})
        rows,health=P.refresh([],brief,client,'2026-09-21');self.assertEqual(health['rowsAdded'],1);self.assertEqual(rows[0]['Terrain Status'],'unverified');self.assertNotIn('Verified Drive Minutes',rows[0])
    def test_manual_exclusion_and_custom_notes_survive(self):
        old={'ID':'keep','Dashboard Include':'No','Acres':'20','Latitude':'35.01','Longitude':'-80.95','Custom':'analyst'};row=P.merge_row(old,self.candidate());self.assertEqual(row['ID'],'keep');self.assertEqual(row['Dashboard Include'],'No');self.assertEqual(row['Custom'],'analyst')
    def test_changed_geometry_revokes_old_evidence_status(self):
        old={'Acres':'30','Terrain Status':'verified-flat','Terrain Evidence':'https://example.org/survey','Verified Drive Minutes':'35'};row=P.merge_row(old,self.candidate());self.assertEqual(row['Terrain Status'],'unverified');self.assertEqual(row['Verified Drive Minutes'],'');self.assertEqual(row['Terrain Evidence'],old['Terrain Evidence'])
    def test_atomic_write_retains_custom_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x.csv';P.write_ledger(path,['ID'],[{'ID':'x','Acres':'20','Custom':'keep'}]);fields,rows=P.load_ledger(path);self.assertEqual(rows[0]['Custom'],'keep')
    def test_invalid_ledger_does_not_overwrite_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x.csv';path.write_text('ID,Acres\nx,20\n');before=path.read_bytes()
            with self.assertRaises(ValueError):P.write_ledger(path,['ID','Acres'],[{'ID':'x','Acres':'-1'}])
            self.assertEqual(before,path.read_bytes())
    def test_snapshot_excludes_audit_rows_and_keeps_old_review_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x.csv';path.write_text('ID\nx\n');rows=[{'ID':'x','Last Researched':'2026-05-13'},{'ID':'SEARCH-50AC-AUDIT'}]
            snapshot=P.build_snapshot(rows,BRIEF,{'status':'blocked'},path);self.assertEqual(len(snapshot['properties']),1);self.assertEqual(snapshot['latestListingReviewAt'],'2026-05-13');self.assertEqual(len(snapshot['ledgerSha256']),64)
    def test_config_rejects_unapproved_hosts(self):
        with self.assertRaises(ValueError):P.validate_brief({**BRIEF,'brokerSources':[{'url':'https://example.org'}]})
    def test_snapshot_json_rejects_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):P.atomic_json(Path(directory)/'x.json',{'value':float('nan')})
if __name__=='__main__':unittest.main()
