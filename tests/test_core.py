"""Run with: python -m unittest discover -s tests -v"""
import unittest
import time
import hmac
import hashlib
from server import safe_demo, validate_ai, hash_password, verify_stripe_signature

R = 'Jane Doe\n• Used Python and SQL to analyze sales data.\n• Created Tableau reports for weekly metrics.\n• Collaborated with a small team to communicate findings.'
J = 'Data Analyst\n• Experience with Python and SQL.\n• Build Tableau dashboards.\n• Knowledge of AWS cloud computing.'

class CoreTests(unittest.TestCase):
    def test_demo_no_new_tools(self):
        response = safe_demo(R, J)
        self.assertEqual(response['mode'], 'demo')
        self.assertGreater(len(response['suggestions']), 0)
        self.assertTrue(all(x['evidence'] in R for x in response['suggestions']))
        self.assertTrue(any(x['status'] == 'not_evidenced' for x in response['requirements']))

    def test_ai_rejects_unsubstantiated_numbers(self):
        candidate = {'requirements': [], 'suggestions': [{'before': 'Used Python and SQL to analyze sales data.', 'after': 'Improved revenue by 80% using Python and SQL.', 'evidence': 'Used Python and SQL to analyze sales data.', 'why': 'Quantified'}], 'missing': [], 'summary': ''}
        self.assertEqual(len(validate_ai(candidate, R)['suggestions']), 0)

    def test_ai_rejects_new_tools(self):
        candidate = {'requirements': [], 'suggestions': [{'before': 'Used Python and SQL to analyze sales data.', 'after': 'Built AWS and Spark pipelines using Python.', 'evidence': 'Used Python and SQL to analyze sales data.', 'why': 'Tools'}], 'missing': [], 'summary': ''}
        self.assertEqual(len(validate_ai(candidate, R)['suggestions']), 0)

    def test_ai_accepts_grounded_rewrite(self):
        candidate = {'requirements': [], 'suggestions': [{'before': 'Used Python and SQL to analyze sales data.', 'after': 'Analyzed sales data with Python and SQL.', 'evidence': 'Used Python and SQL to analyze sales data.', 'why': 'Clearer action verb'}], 'missing': [], 'summary': ''}
        self.assertEqual(len(validate_ai(candidate, R)['suggestions']), 1)

    def test_password_hash_deterministic_for_salt(self):
        s='10ab'*8
        self.assertEqual(hash_password('my-password-123',s),hash_password('my-password-123',s))
        self.assertNotEqual(hash_password('my-password-123',s),hash_password('another-password',s))

    def test_stripe_webhook_hmac(self):
        payload=b'{"type":"checkout.session.completed"}'
        secret='whsec_test_abc'
        ts=int(time.time())
        digest=hmac.new(secret.encode(),str(ts).encode()+b'.'+payload,hashlib.sha256).hexdigest()
        self.assertTrue(verify_stripe_signature(payload,f't={ts},v1={digest}',secret))
        self.assertFalse(verify_stripe_signature(b'altered',f't={ts},v1={digest}',secret))

if __name__ == '__main__':
    unittest.main()
