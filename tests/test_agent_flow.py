import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
from loglens.agent import run_gemini_agent, call_mcp
from loglens.queries import LogQueries
from loglens.models import Filters

class Message:
    def __init__(self, calls=None, content=None):
        self.tool_calls, self.content = calls, content
    def model_dump(self, **kwargs):
        return {"role":"assistant", "content":self.content or ""}

class AgentFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_last_round_can_answer(self):
        call = NS(id='c1', function=NS(name='search_logs',arguments='{}'))
        replies = [NS(choices=[NS(message=Message([call]))]),
                   NS(choices=[NS(message=Message(content='Answer'))])]
        create = __import__('unittest.mock',fromlist=['Mock']).Mock(side_effect=replies)
        client = NS(chat=NS(completions=NS(create=create)))
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test','LOGLENS_MAX_ROUNDS':'1'}), patch('loglens.agent.OpenAI',return_value=client), patch('loglens.agent.call_batch',new=AsyncMock(return_value=[{'rows':[]}])):
            answer = await run_gemini_agent(None, [], 'engineer','question')
        self.assertEqual(answer,'Answer')
        self.assertEqual(create.call_args.kwargs['tool_choice'],'none')

    async def test_bad_arguments_return_error(self):
        for args in ('{bad', '[]', 'null'):
            self.assertIn('error', await call_mcp(None, {'search_logs'}, 'search_logs',args))

class TrendTests(unittest.TestCase):
    def test_limit_and_bucket_validation(self):
        db=NS(fetch_all=lambda q,p: [{'period_start':i} for i in range(4)])
        q=LogQueries(db, max_rows=3)
        result=q.trend(Filters('bgl'))
        self.assertTrue(result.truncated)
        self.assertEqual(result.result_count,3)
        self.assertEqual(result.parameters[-1],4)
        with self.assertRaises(ValueError):
            q.trend(Filters('bgl'), "invalid")
