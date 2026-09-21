"""Regression cases based on the observed broker DOM; no network needed."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import property_pipeline as P
BRIEF=json.loads((ROOT/'data/property-search-brief.json').read_text())
HTML=(ROOT/'tests/fixtures/realstack-optional-mls.html').read_text()
URL='https://www.mossyoakproperties.com/property/test-york-south-carolina/74443/'
SOURCE={'name':'Mossy Oak Properties — York','url':'https://www.mossyoakproperties.com/land-for-sale/south-carolina/york-county/'}
NOW='2026-09-21T20:00:00Z'
class Client:
    hosts=set(P.BROKERS)
    def __init__(self,pages):self.pages=pages;self.requests=[]
    def get(self,url):
        self.requests.append(url)
        value=self.pages.get(url)
        return {'ok':True,'http':200,'body':value} if value is not None else {'ok':False,'http':403,'reason':'Access denied'}
class SourceTests(unittest.TestCase):
    def parse(self,html=HTML,url=URL):return P.parse_broker_listing(html,url,SOURCE,NOW)
    def refresh(self,rows=None,html=HTML,**kw):
        client=Client({SOURCE['url']:f'<h1>County</h1>1 - 1 of 1 Listings<a href="{URL}">view</a>',URL:html})
        return P.refresh(rows or [],{**BRIEF,'brokerSources':[SOURCE]},client,NOW,**kw)
    def test_optional_mls_label_does_not_corrupt_id(self):self.assertEqual(self.parse()['ID'],'MOP-74443')
    def test_publisher_is_not_hardcoded_to_advance(self):self.assertEqual(self.parse()['Source'],'Mossy Oak Properties')
    def test_optional_external_mls_preserved_separately(self):self.assertEqual(self.parse()['MLS / External Reference'],'--/TEST-MLS')
    def test_primary_h1_not_metadata_or_related_listing(self):
        row=self.parse();self.assertEqual(row['List Price'],'545000.0');self.assertEqual(row['Acres'],'35.9');self.assertEqual(row['County'],'York County')
    def test_no_price_per_acre_substitution(self):
        html=HTML.replace('<span class="label">Price: </span><span class="value">$545,000</span>','')
        self.assertNotIn('List Price',self.parse(html))
    def test_page_id_must_match_url_id(self):self.assertIsNone(self.parse(url=URL.replace('74443','74444')))
    def test_description_numbers_never_fill_missing_primary_acres(self):
        self.assertIsNone(self.parse(HTML.replace('<span class="label">Acres: </span><span class="value">35.9</span>','')))
    def test_publisher_namespace_separates_identical_numeric_ids(self):
        alt=URL.replace('www.mossyoakproperties.com','www.advancelandandtimber.com')
        self.assertNotEqual(P.identity({'Property URL':URL}),P.identity({'Property URL':alt}))
    def test_new_slug_on_same_publisher_keeps_identity(self):
        self.assertEqual(P.identity({'Property URL':URL}),P.identity({'Property URL':URL.replace('test-york-south-carolina','new-title')}))
    def test_tracking_links_canonicalized_and_deduped(self):
        page=P.Page();page.feed(f'<a href="{URL}?utm_source=x">1</a><a href="{URL.rstrip("/")}">2</a>')
        self.assertEqual(P.listing_links(page,SOURCE),[URL])
    def test_unknown_source_cannot_become_mossy_oak(self):self.assertIsNone(self.parse(url=URL.replace('www.mossyoakproperties.com','example.org')))
    def test_terrain_and_drive_claims_remain_unverified(self):
        row=self.parse();self.assertIn('rolling terrain',row['Listing Notes']);self.assertNotIn('Verified Drive Minutes',row);self.assertIn('Source Drive Conflict',row)
    def test_constraints_at_end_of_long_description_not_lost(self):
        signals,flag=P.source_constraints('Other details. '*200+'Charlotte are both just over an hour away. Gently rolling topography.')
        self.assertTrue(flag);self.assertTrue(any('rolling terrain' in s for s in signals))
    def test_negated_rolling_does_not_create_conflict(self):
        signals,_=P.source_constraints('No rolling hills. Flat land.')
        self.assertFalse(any('describes rolling' in s for s in signals))
    def test_flat_creek_is_not_verified_flat_land(self):
        signals,_=P.source_constraints('Flat Creek frontage.')
        self.assertFalse(any('flat or level land' in s for s in signals))
    def test_new_flat_claim_never_auto_qualifies(self):
        rows,h=self.refresh(html=HTML.replace('Rolling topography with a creek. About an hour from Charlotte.','Flat land.'))
        self.assertEqual(rows[0]['Terrain Status'],'unverified');self.assertEqual(rows[0]['Arena Fit'],'unverified')
    def test_index_only_is_failed_listing_refresh(self):
        rows,h=P.refresh([],{**BRIEF,'brokerSources':[SOURCE]},Client({SOURCE['url']:'0 - 0 of 0 Listings'}),NOW)
        self.assertEqual(h['status'],'error');self.assertFalse(h['listingRefreshSucceeded'])
    def test_links_present_but_all_parsing_fails_is_error(self):
        rows,h=self.refresh(html='<h1>Nothing usable</h1>')
        self.assertEqual(h['status'],'error');self.assertEqual(h['listingPagesAttempted'],1);self.assertEqual(h['listingsChecked'],0)
    def test_legitimate_unchanged_check_is_success(self):
        rows,h=self.refresh();same,h2=self.refresh(rows)
        self.assertEqual(h['rowsAdded'],1);self.assertEqual(h2['rowsAdded'],0);self.assertEqual(h2['rowsChanged'],0);self.assertTrue(h2['listingRefreshSucceeded'])
    def test_recheck_records_real_price_change(self):
        rows,_=self.refresh();updated,h=self.refresh(rows,html=HTML.replace('$545,000','$500,000'))
        self.assertEqual(h['rowsChanged'],1);self.assertEqual(updated[0]['List Price'],'500000.0');self.assertIn('List Price',h['changes'][0]['fields'])
    def test_existing_listing_can_become_sold(self):
        rows,_=self.refresh();updated,h=self.refresh(rows,html=HTML.replace('>Available<','>Sold<'))
        self.assertEqual(updated[0]['Status'],'Sold');self.assertEqual(h['rowsChanged'],1)
    def test_dont_import_new_sold_or_undercontract_opportunity(self):
        for status in ['Sold','Under Contract','Pending']:
            rows,h=self.refresh(html=HTML.replace('>Available<','>'+status+'<'))
            self.assertEqual(rows,[]);self.assertEqual(h['unavailableNewListingsExcluded'],1);self.assertTrue(h['listingRefreshSucceeded'])
    def test_failed_detail_never_advances_its_review_date(self):
        rows,_=self.refresh();updated,h=self.refresh(rows,html='<h1>Unavailable</h1>')
        self.assertEqual(rows,updated);self.assertEqual(h['status'],'error')
    def test_stale_drive_claim_cleared_after_source_recheck(self):
        rows,_=self.refresh();updated,h=self.refresh(rows,html=HTML.replace('About an hour from Charlotte.',''))
        self.assertEqual(updated[0]['Source Drive Conflict'],'')
    def test_manual_id_exclusion_and_evidence_preserved(self):
        rows,_=self.refresh();rows[0].update({'ID':'manual','Dashboard Include':'No','Terrain Evidence':'https://example.org/topo','Custom':'keep'})
        updated,h=self.refresh(rows);self.assertEqual(updated[0]['ID'],'manual');self.assertEqual(updated[0]['Dashboard Include'],'No');self.assertEqual(updated[0]['Custom'],'keep')
    def test_capped_checks_rotate_instead_of_starving_records(self):
        url2=URL.replace('74443','74444');brief={**BRIEF,'brokerSources':[SOURCE]}
        pages={SOURCE['url']:f'<a href="{URL}">a</a><a href="{url2}">b</a>',URL:HTML,url2:HTML.replace('74443','74444')}
        rows,h=P.refresh([],brief,Client(pages),NOW,limit=1)
        more,h2=P.refresh(rows,brief,Client(pages),NOW,limit=1,offset=h['nextListingOffset'])
        self.assertEqual(len(more),2);self.assertTrue(h['listingLimitReached'])
    def test_pagination_truncation_is_reported_not_full_coverage(self):
        pages={SOURCE['url']:f'1 - 1 of 99 Listings<a href="{URL}">a</a>',URL:HTML}
        rows,h=P.refresh([],{**BRIEF,'brokerSources':[SOURCE]},Client(pages),NOW)
        self.assertTrue(h['sources'][0]['inventoryTruncated']);self.assertEqual(h['status'],'partial')
    def test_actual_captured_pages_parse_when_local_evidence_is_available(self):
        path=ROOT/'source-diagnostic/observations.json'
        if not path.exists():self.skipTest('Live evidence is tested separately in the live workflow')
        for i,ob in enumerate(json.loads(path.read_text())):
            for j,sample in enumerate(ob.get('samples',[])):
                f=ROOT/f'source-diagnostic/detail-{i}-{j}.html'
                if f.exists():self.assertIsNotNone(P.parse_broker_listing(f.read_text(),sample['url'],ob['source'],NOW))
if __name__=='__main__':unittest.main()
