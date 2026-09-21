import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import property_pipeline as P
class SourceEdgeTests(unittest.TestCase):
    def test_under_hour_language_is_not_an_over_limit_claim(self):
        for phrase in ['Less than an hour from Charlotte.', 'Within an hour from Charlotte.',
                       'Half an hour from Charlotte.', 'Under one hour from Charlotte.',
                       'Within approximately an hour from Charlotte.']:
            with self.subTest(phrase=phrase):self.assertFalse(P.source_constraints(phrase)[1])
    def test_about_or_over_an_hour_is_a_source_claim(self):
        for phrase in ['About an hour from Charlotte.', 'Just over an hour from Charlotte.',
                       'Columbia and Charlotte are both just over an hour away.']:
            with self.subTest(phrase=phrase):self.assertTrue(P.source_constraints(phrase)[1])
    def test_tracked_record_not_misattributed_to_last_county_index(self):
        url='https://www.mossyoakproperties.com/property/test/74443/'
        fixture=(Path(__file__).parent/'fixtures/realstack-optional-mls.html').read_text()
        class Client:
            hosts={'www.mossyoakproperties.com'}
            def get(self,target):
                return {'ok':True,'http':200,'body':fixture if target==url else '0 - 0 of 0 Listings'}
        brief={'brokerSources':[{'name':'Mecklenburg index','url':'https://www.mossyoakproperties.com/land-for-sale/north-carolina/mecklenburg-county/'}]}
        rows,health=P.refresh([{'ID':'manual','Acres':'35.9','Property URL':url}],brief,Client(),'2026-09-21')
        self.assertEqual(rows[0]['Scrape Source URL'],url)
        self.assertEqual(rows[0]['Scrape Source Name'],'Tracked broker listing')
if __name__=='__main__':unittest.main()
