import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock, Mock
from loglens.agent import run_gemini_agent, call_mcp, max_rounds, run_agent
from loglens.queries import LogQueries
from loglens.models import Filters

class Message:
    def __init__(self, calls=None, content=None):
        self.tool_calls, self.content = calls, content
    def model_dump(self, **kwargs):
        return {"role":"assistant", "content":self.content or ""}

class AgentFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_gemini_budget_allows_one_followup_batch(self):
        call = NS(id='c1', function=NS(name='search_logs', arguments='{}'))
        create = Mock(side_effect=[
            NS(choices=[NS(message=Message([call]))]),
            NS(choices=[NS(message=Message([call]))]),
            NS(choices=[NS(message=Message(content='Insufficient evidence'))]),
        ])
        client = NS(chat=NS(completions=NS(create=create)))
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}, clear=True), patch('loglens.agent.OpenAI', return_value=client), patch('loglens.agent.call_batch', new=AsyncMock(return_value=[{'rows': []}])) as batch:
            self.assertEqual(max_rounds(), 2)
            answer = await run_gemini_agent(None, [], 'engineer', 'question')
        self.assertEqual(answer, 'Insufficient evidence')
        self.assertEqual(create.call_count, 3)
        self.assertEqual(batch.await_count, 2)
        self.assertEqual([c.kwargs['tool_choice'] for c in create.call_args_list], ['required', 'auto', 'none'])

    async def test_openai_answers_in_two_calls_or_uses_one_extra_round(self):
        for needs_followup in (False, True):
            with self.subTest(needs_followup=needs_followup):
                call = NS(type='function_call', name='search_logs', arguments='{}', call_id='c1')
                evidence_reply = NS(id='r1', output=[call])
                final_reply = NS(id='r3', output=[], output_text='Answer')
                replies = [evidence_reply] * (2 if needs_followup else 1) + [final_reply]
                create = Mock(side_effect=replies)
                client = NS(responses=NS(create=create))
                connection = AsyncMock()
                connection.__aenter__.return_value = (None, None)
                session = AsyncMock()
                session.list_tools.return_value = NS(tools=[])
                session_context = AsyncMock()
                session_context.__aenter__.return_value = session
                with patch.dict(os.environ, {'AI_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test'}, clear=True), patch('loglens.agent.load_dotenv'), patch('loglens.agent.OpenAI', return_value=client), patch('loglens.agent.stdio_client', return_value=connection), patch('loglens.agent.ClientSession', return_value=session_context), patch('loglens.agent.call_batch', new=AsyncMock(return_value=[{'rows': []}])) as batch:
                    answer = await run_agent('engineer', 'question')
                self.assertEqual(answer, 'Answer')
                self.assertEqual(create.call_count, 3 if needs_followup else 2)
                self.assertEqual(batch.await_count, 2 if needs_followup else 1)
                self.assertEqual(create.call_args.kwargs['tool_choice'], 'none' if needs_followup else 'auto')

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

    async def test_provider_requests_tools_on_final_round(self):
        call = NS(id='c1', function=NS(name='search_logs', arguments='{}'))
        create = Mock(return_value=NS(choices=[NS(message=Message([call]))]))
        client = NS(chat=NS(completions=NS(create=create)))
        evidence = {'evidence_id': 'E-abc', 'tool': 'search_logs', 'result_count': 1, 'scope': {'dataset': 'bgl'}}
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test', 'LOGLENS_MAX_ROUNDS': '2'}), patch('loglens.agent.OpenAI', return_value=client), patch('loglens.agent.call_batch', new=AsyncMock(return_value=[evidence])) as batch:
            answer = await run_gemini_agent(None, [], 'engineer', 'question')
        self.assertIn('E-abc', answer)
        self.assertIn('not a diagnosis', answer)
        self.assertEqual(create.call_count, 3)
        self.assertEqual(batch.await_count, 2)
        self.assertEqual(create.call_args.kwargs['tools'], [])

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
