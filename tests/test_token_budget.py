import json
import tempfile
import unittest
from pathlib import Path
from loglens.token_budget import compact_evidence, prepare_evidence

class TokenTests(unittest.TestCase):
    def test_round_trip_and_audit(self):
        original = {'evidence_id':'E-1','query':'SELECT * FROM logs','parameters':[1],
                    'scope':{'dataset':'bgl'},'truncated':True,
                    'rows':[{'event_id':'1','message':'hello'}, {'event_id':'2','message':None}]}
        with tempfile.TemporaryDirectory() as folder:
            result = prepare_evidence(original, folder)
            self.assertEqual(json.loads(Path(result['local_audit_file']).read_text()), original)
            data = result['evidence']
            rows = data['rows']
            self.assertEqual([dict(zip(rows['columns'],r)) for r in rows['values']], original['rows'])
            self.assertTrue(data['truncated'])
            self.assertEqual(data['scope'], original['scope'])
            self.assertNotIn('query', data)
            self.assertIn('query', original)

    def test_sparse_rows_not_changed(self):
        original = {'rows':[{'a':1},{'b':2}]}
        self.assertEqual(compact_evidence(original), original)
