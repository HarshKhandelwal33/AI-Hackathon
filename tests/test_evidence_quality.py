import unittest
from loglens.models import Evidence
from scripts.enrich_logs import template

class QualityTests(unittest.TestCase):
    def test_reference_changes_when_evidence_changes(self):
        e = Evidence('search', {}, 'SELECT', [], [{'message':'a'}], 1)
        first = e.to_dict()['evidence_id']
        self.assertEqual(first, e.to_dict()['evidence_id'])
        e.rows[0]['message'] = 'b'
        self.assertNotEqual(first, e.to_dict()['evidence_id'])

    def test_templates_preserve_error_codes(self):
        self.assertEqual(template('HTTP 404 at 0xAB12'), 'HTTP 404 at <HEX>')
        self.assertEqual(template('id 12345678-abcd-abcd-abcd-123456789abc'), 'id <UUID>')
