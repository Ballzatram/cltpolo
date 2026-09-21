import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import refresh_property_research as refresh
BRIEF = json.loads((ROOT / 'data/property-search-brief.json').read_text())


def candidate(**kwargs):
    fields = dict(acres=20,price=200000,latitude=35.01,longitude=-80.95,county='York County',
                  city='Fort Mill',state='SC',title='Test property',address='Test road',
                  description='Pasture; flatness needs review.',url='https://example.org/listing/1234567',
                  source='Test source',external_id='1234567',verified=True)
    return SimpleNamespace(**(fields | kwargs))


class ResearchTests(unittest.TestCase):
    def test_twenty_inclusive(self):
        self.assertTrue(refresh.discovery_candidate(candidate(),BRIEF))
    def test_under_twenty_rejected(self):
        self.assertFalse(refresh.discovery_candidate(candidate(acres=19.9),BRIEF))
    def test_unknown_acres_rejected_at_discovery(self):
        self.assertFalse(refresh.discovery_candidate(candidate(acres=None),BRIEF))
    def test_north_excluded(self):
        self.assertFalse(refresh.discovery_candidate(candidate(latitude=35.9),BRIEF))
    def test_non_target_county_excluded(self):
        self.assertFalse(refresh.discovery_candidate(candidate(county='Iredell County'),BRIEF))
    def test_unknown_coordinates_stay_discovery_only(self):
        self.assertTrue(refresh.discovery_candidate(candidate(latitude=None,longitude=None),BRIEF))
    def test_no_minimum_drive_rule(self):
        self.assertTrue(refresh.discovery_candidate(candidate(latitude=35.22),BRIEF))
    def test_nan_does_not_pass(self):
        self.assertFalse(refresh.discovery_candidate(candidate(acres=float('nan')),BRIEF))
    def apply(self, existing=None, **kwargs):
        return refresh.apply_listing(existing or {},candidate(**kwargs),{'name':'Search','source':'Test','url':'https://example.org/search'},datetime(2026,9,21,tzinfo=timezone.utc))
    def test_new_listing_is_never_auto_shortlisted(self):
        row=self.apply(description='Very flat land, ideal for polo!')
        self.assertEqual(row['Terrain Status'],'unverified')
        self.assertNotIn('Weighted Polo Score',row)
        self.assertNotIn('Drive Time From Charlotte',row)
        self.assertEqual(row['Grass Fit'],'unverified')
        self.assertEqual(row['Status'],'Availability unverified')
    def test_custom_fields_and_manual_exclusion_survive(self):
        row=self.apply({'ID':'existing','Dashboard Include':'No','Analyst note':'keep me'})
        self.assertEqual(row['Analyst note'],'keep me')
        self.assertEqual(row['Dashboard Include'],'No')
    def test_same_geometry_preserves_reviewed_evidence(self):
        row=self.apply({'Acres':'20','Latitude':'35.01','Longitude':'-80.95','Terrain Status':'verified-flat','Terrain Evidence':'https://example.org/survey'})
        self.assertEqual(row['Terrain Status'],'verified-flat')
    def test_changed_geometry_revokes_pass_status_not_evidence_history(self):
        row=self.apply({'Acres':'30','Terrain Status':'verified-flat','Terrain Evidence':'https://example.org/survey','Verified Drive Minutes':'35','Usable Flat Acres':'15'})
        self.assertEqual(row['Terrain Status'],'unverified')
        self.assertEqual(row['Terrain Evidence'],'https://example.org/survey')
        self.assertEqual(row['Verified Drive Minutes'],'')
        self.assertEqual(row['Usable Flat Acres'],'')
    def test_audit_only_changes_do_not_count(self):
        a={'ID':'x','Last Researched':'2026-01-01'}
        b={'ID':'x','Last Researched':'2026-09-21','Terrain Evidence':''}
        self.assertEqual(refresh.meaningful(a),refresh.meaningful(b))
    def test_archived_subminimum_is_valid_not_deleted(self):
        self.assertEqual(refresh.validate([{'ID':'x','Acres':'10','Property URL':'https://example.org/x'}]),[])
    def test_duplicate_properties_rejected(self):
        row={'ID':'x','Acres':'20','Property URL':'https://example.org/x'}
        self.assertTrue(refresh.validate([row,row.copy()]))
    def test_unsafe_source_rejected(self):
        with self.assertRaises(ValueError): self.apply(url='javascript:alert(1)')
    def test_writer_preserves_unknown_columns_and_adds_evidence_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.csv'
            refresh.write_data(path,['ID'],[{'ID':'x','Custom':'keep'}])
            columns,rows=refresh.load_data(path)
            self.assertIn('Terrain Evidence',columns)
            self.assertEqual(rows[0]['Custom'],'keep')
    def test_malformed_csv_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.csv';path.write_text('ID,Acres\nx\n')
            with self.assertRaises(ValueError):refresh.load_data(path)
    def test_blocked_sources_preserve_rows_and_report_failures(self):
        class Parser:
            @staticmethod
            def is_listing_url(url):return True
            @staticmethod
            def fetch_url(url):return SimpleNamespace(ok=False,status=403,error='Blocked',text='',url=url)
        old=[{'ID':'x','Acres':'20','Property URL':'https://example.org/x'}]
        new,summary=refresh.run_refresh(old,BRIEF,Parser,pause=0)
        self.assertEqual(old,new)
        self.assertEqual(summary['sources_failed'],len(BRIEF['sources']))
        self.assertEqual(summary['rows_updated'],0)
        self.assertFalse(summary['csv_written'])
    def test_discovery_keeps_provenance_and_limits_work(self):
        class Parser:
            @staticmethod
            def is_listing_url(url):return True
            @staticmethod
            def fetch_url(url):return SimpleNamespace(ok=True,status=200,error='',text='fixture',url=url)
            @staticmethod
            def extract_listing_links(text,url):return ['https://example.org/listing/1234567']
            @staticmethod
            def parse_listing_page(page,source):return candidate(url=page.url,source=source)
        rows,summary=refresh.run_refresh([],BRIEF,Parser,limit=1,pause=0)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['Scrape Source URL'],BRIEF['sources'][0]['url'])
        self.assertEqual(summary['rows_added'],1)
        self.assertEqual(rows[0]['Terrain Status'],'unverified')


if __name__ == '__main__': unittest.main()
