import unittest
from loglens.queries import LogQueries
from loglens.models import Filters
from loglens.validation import validate_answer

class DB:
    def __init__(self): self.calls=[]
    def fetch_all(self,q,p): self.calls.append((q,p)); return []

class Changes(unittest.TestCase):
    def test_fallback_bounded_preserves_filters(self):
        db=DB(); e=LogQueries(db).search(Filters("bgl",component="KERNEL"),"error")
        self.assertEqual(len(db.calls),2)
        self.assertEqual(db.calls[0][1],db.calls[1][1])
        self.assertEqual(e.scope["search_method"],"literal_all_terms")
    def test_correlation_priority(self):
        e=LogQueries(DB()).nearby("bgl","x")
        self.assertLess(e.query.index("TRIM(a.request_id)"),e.query.index("TRIM(a.node_id)"))
        self.assertIn("ELSE l.event_id = %s",e.query)
        self.assertEqual(e.query.count("%s"),len(e.parameters))
    def test_validation(self):
        e={"evidence_id":"E-abc", "rows":[{"log_count":4}]}
        self.assertTrue(validate_answer("5 log rows [E-abc]",e)["warnings"])
        self.assertTrue(validate_answer("[E-unknown]",e)["warnings"])
        self.assertFalse(validate_answer("4 log rows [E-abc]",e)["warnings"])
