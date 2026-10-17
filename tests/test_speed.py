import asyncio
import unittest
from unittest.mock import patch
from loglens.agent import call_batch

class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrency_bounded_and_order_preserved(self):
        active = peak = 0
        async def fake(session, available, name, arguments):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return name
        with patch('loglens.agent.call_mcp', fake):
            result = await call_batch(None, set(), [(str(i), '{}') for i in range(7)])
        self.assertEqual(result, list(map(str, range(7))))
        self.assertEqual(peak, 3)
