"""Agent loop tests with a scripted LLM: no network, no API key."""
import json
import os
import unittest
import uuid
from unittest import mock

from fastapi.testclient import TestClient

import agent
from server import app

RESUME = '''JANE DOE
EXPERIENCE
• Used Python and SQL to analyze sales data for a campus retail store.
• Created Tableau reports for weekly metrics.
• Collaborated with a small team to communicate findings.
EDUCATION
• BA Economics, UCLA'''
JD = 'Data Analyst\n• Experience with Python and SQL.\n• Build Tableau dashboards.\n• Knowledge of AWS cloud computing.'

PLAN = {'requirements': [{'text': 'Python and SQL', 'priority': 'must'}, {'text': 'Tableau dashboards', 'priority': 'must'},
                         {'text': 'AWS cloud computing', 'priority': 'nice'}]}


def fid(text):
    return next(f['id'] for f in agent.extract_facts(RESUME) if text in f['text'])


class Fake:
    """Scripted LLM. `drafts` is a list of per-round draft lists; verify echoes the rewrite as supported
    unless `verify` says otherwise."""
    def __init__(self, drafts, verify=None, map_override=None):
        self.drafts, self.verify, self.map_override, self.log = list(drafts), verify, map_override, []

    def __call__(self, step, system, user):
        payload = json.loads(user)
        self.log.append(step)
        if step == 'plan':
            return PLAN
        if step == 'map':
            if self.map_override:
                return self.map_override
            out = []
            for r in payload['requirements']:
                ids = [c['id'] for c in r['candidates']]
                py = fid('Python')
                tb = fid('Tableau')
                if 'Python' in r['requirement']:
                    out.append({'index': r['index'], 'status': 'matched', 'fact_ids': [py]})
                elif 'Tableau' in r['requirement']:
                    out.append({'index': r['index'], 'status': 'matched', 'fact_ids': [tb]})
                else:
                    out.append({'index': r['index'], 'status': 'not_evidenced', 'fact_ids': []})
            return {'mappings': out}
        if step == 'draft':
            return {'drafts': self.drafts.pop(0) if self.drafts else []}
        if step == 'verify':
            if self.verify:
                return self.verify(payload)
            return {'checks': [{'fact_id': i['fact_id'], 'claims': [{'claim': 'core claim', 'supported': True,
                    'quote': i['source_text'][:20]}]} for i in payload['items']]}
        if step == 'coach':
            return {'summary': 'Focus on dashboards.', 'gap_actions': [{'requirement': 'AWS cloud computing', 'action': 'If you have used AWS, add it.'}]}
        raise AssertionError(step)


def good(text, after):
    return {'fact_id': fid(text), 'after': after, 'why': 'serves requirement'}


class AgentLoop(unittest.TestCase):
    def test_happy_path_is_verified_and_traced(self):
        llm = Fake([[good('Python', 'Analyzed sales data for a campus retail store using Python and SQL.'),
                     good('Tableau', 'Created Tableau reports tracking weekly metrics.')]])
        r = agent.run_agent(RESUME, JD, llm)
        self.assertEqual(len(r['suggestions']), 2)
        self.assertTrue(all(s['verified'] and s['evidence'] in RESUME for s in r['suggestions']))
        self.assertEqual(r['agent']['repair_rounds'], 0)
        self.assertEqual([s['step'] for s in r['agent']['steps']][:3], ['index', 'plan', 'retrieve'])

    def test_fabrication_is_repaired(self):
        bad = good('Python', 'Built AWS pipelines with Python and SQL for sales data.')
        fixed = good('Python', 'Analyzed sales data for a campus retail store with Python and SQL.')
        tab = good('Tableau', 'Created Tableau reports tracking weekly metrics.')
        llm = Fake([[bad, tab], [fixed]])
        r = agent.run_agent(RESUME, JD, llm)
        self.assertEqual(r['agent']['repair_rounds'], 1)
        self.assertEqual(r['suggestions'][0]['attempts'], 2)
        self.assertNotIn('AWS', r['suggestions'][0]['after'])

    def test_persistent_fabrication_is_dropped_not_shipped(self):
        bad = good('Python', 'Led a team of 12 analysts using Python and SQL, improving revenue 40%.')
        tab = good('Tableau', 'Created Tableau reports tracking weekly metrics.')
        r = agent.run_agent(RESUME, JD, Fake([[bad, tab], [bad], [bad]]))
        self.assertEqual([x['fact_id'] for x in r['suggestions']], [fid('Tableau')])
        self.assertEqual(r['agent']['repair_rounds'], 2)
        self.assertEqual(len(r['agent']['dropped']), 1)

    def test_verifier_must_quote_the_source(self):
        def verify(payload):
            return {'checks': [{'fact_id': i['fact_id'], 'claims': [{'claim': 'x', 'supported': True,
                    'quote': 'text that is not in the resume at all'}]} for i in payload['items']]}
        d = good('Python', 'Analyzed sales data with Python and SQL.')
        r = agent.run_agent(RESUME, JD, Fake([[d], [d], [d]], verify=verify))
        self.assertEqual(r['suggestions'], [])

    def test_mapper_cannot_cite_unretrieved_or_invented_facts(self):
        llm = Fake([[]], map_override={'mappings': [{'index': i, 'status': 'matched', 'fact_ids': ['F999']} for i in range(3)]})
        r = agent.run_agent(RESUME, JD, llm)
        self.assertTrue(all(q['status'] == 'not_evidenced' and q['evidence'] == '' for q in r['requirements']))
        self.assertEqual(r['suggestions'], [])

    def test_no_resume_facts_fails_loud(self):
        with self.assertRaises(agent.AgentError):
            agent.run_agent('hi', JD, Fake([]))

    def test_provider_error_propagates(self):
        def boom(step, s, u):
            raise agent.AgentError(502, 'provider down')
        with self.assertRaises(agent.AgentError) as ctx:
            agent.run_agent(RESUME, JD, boom)
        self.assertEqual(ctx.exception.status, 502)


class Retrieval(unittest.TestCase):
    def test_bm25_ranks_relevant_fact_first(self):
        facts = agent.extract_facts(RESUME)
        top = agent.BM25(facts).search('Tableau dashboards for weekly metrics', 2)[0][0]
        self.assertIn('Tableau', top['text'])

    def test_bank_fact_is_used_as_evidence_but_never_rewritten(self):
        bank = ['Deployed a churn model on AWS SageMaker for a class capstone project.']
        llm = Fake([[]], map_override=None)
        # make the mapper pick bank fact B1 for the AWS requirement
        orig = llm.__call__

        def patched(step, system, user):
            out = orig(step, system, user)
            if step == 'map':
                for m, r in zip(out['mappings'], json.loads(user)['requirements']):
                    if 'AWS' in r['requirement']:
                        m.update(status='matched', fact_ids=['B1'])
            return out
        res = agent.run_agent(RESUME, JD, patched, bank)
        aws = next(q for q in res['requirements'] if 'AWS' in q['text'])
        self.assertEqual((aws['status'], aws['source']), ('matched', 'bank'))
        self.assertTrue(all(s['source'] == 'resume' for s in res['suggestions']))
        self.assertTrue(any('fact bank' in a['action'] for a in res['gap_actions']))

    def test_hard_flags(self):
        src = 'Used Python to analyze sales data.'
        self.assertTrue(agent.hard_flags('Used Python to grow sales 40%.', src, src))
        self.assertTrue(agent.hard_flags('Used Python and AWS.', src, src))
        self.assertFalse(agent.hard_flags('Analyzed sales data with Python.', src, src))


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def user(self):
        c = TestClient(app)
        r = c.post('/api/auth/register', json={'email': f'{uuid.uuid4().hex[:8]}@example.com', 'password': 'password123'})
        self.assertEqual(r.status_code, 200)
        return c

    def tailor(self, c, result=None, exc=None):
        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test'}):
            target = mock.patch('server.run_ai_tailor', side_effect=exc, return_value=result)
            with target:
                return c.post('/api/tailor', json={'resume': RESUME, 'job_description': JD})

    def result(self, suggestions, status='matched'):
        return {'requirements': [{'text': 'x', 'status': status, 'evidence': 'e', 'priority': 'must', 'source': 'resume'}],
                'suggestions': suggestions, 'missing': [], 'summary': 's', 'mode': 'ai', 'agent': {'steps': []}}

    def test_credit_charged_for_grounded_result(self):
        c = self.user()
        r = self.tailor(c, self.result([{'before': 'a', 'after': 'b', 'why': 'w', 'evidence': 'a'}]))
        self.assertEqual((r.status_code, r.json()['credits_remaining'], r.json()['charged']), (200, 2, True))

    def test_no_charge_when_nothing_grounded(self):
        c = self.user()
        r = self.tailor(c, self.result([], status='not_evidenced'))
        self.assertEqual((r.json()['credits_remaining'], r.json()['charged']), (3, False))

    def test_no_charge_on_provider_failure(self):
        c = self.user()
        r = self.tailor(c, exc=__import__('fastapi').HTTPException(502, 'down'))
        self.assertEqual(r.status_code, 502)
        self.assertEqual(c.get('/api/me').json()['user']['credits'], 3)

    def test_fact_bank_is_private_and_deletable(self):
        a, b = self.user(), self.user()
        fact = a.post('/api/facts', json={'text': 'Built a dashboard for 4 teammates in a class project.'})
        self.assertEqual(fact.status_code, 200)
        self.assertEqual(a.post('/api/facts', json={'text': 'built a dashboard for 4 teammates in a class project.'}).status_code, 409)
        self.assertEqual(b.get('/api/facts').json()['items'], [])
        self.assertEqual(b.delete(f'/api/facts/{fact.json()["id"]}').status_code, 404)
        self.assertEqual(a.delete(f'/api/facts/{fact.json()["id"]}').status_code, 200)
        self.assertEqual(TestClient(app).get('/api/facts').status_code, 401)


if __name__ == '__main__':
    unittest.main()
