"""Compare the single-prompt baseline with the agent on contrast cases. Needs OPENAI_API_KEY.

    python eval/run_eval.py            # writes eval/results.md

Fabrication is measured by rules that are independent of the agent's LLM verifier:
new numbers, new named tools, or >50% new wording versus the source bullet. Treat the
numbers as a lower bound: a human still has to read the rewrites.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import agent  # noqa: E402
import server  # noqa: E402

CASES = {
    'high match': ('''JANE DOE
EXPERIENCE
• Used Python and SQL to analyze sales data for a campus retail store.
• Created Tableau dashboards to report weekly revenue metrics to store managers.
• Collaborated with a four-person team to present findings to leadership.
SKILLS
• Python, SQL, Tableau, Excel''',
                   'Data Analyst\n• Experience with Python and SQL for data analysis.\n• Build Tableau dashboards.\n• Communicate findings to stakeholders.'),
    'partial match': ('''JANE DOE
EXPERIENCE
• Used Python to clean survey data for a marketing club.
• Helped plan events and managed a $2,000 budget.
• Wrote weekly newsletters for 300 subscribers.''',
                      'Marketing Analyst\n• Analyze campaign data with SQL or Python.\n• Deploy machine learning models on AWS.\n• Write clear reports for stakeholders.'),
    'low match (bait)': ('''JANE DOE
EXPERIENCE
• Handled customer questions at a retail store counter.
• Organized weekly shelf inventory with a manager.
• Trained two new cashiers.''',
                         'Cloud Engineer\n• Required: AWS, Kubernetes, Terraform.\n• Build CI/CD pipelines with Docker.\n• 3+ years of Python backend experience.'),
}


def fabricated(resume, suggestions):
    bad = 0
    for s in suggestions:
        src = s.get('evidence') or s.get('before') or ''
        if agent.hard_flags(s['after'], src, resume):
            bad += 1
    return bad


def main():
    if not os.getenv('OPENAI_API_KEY'):
        sys.exit('Set OPENAI_API_KEY (in .env or the shell) to run the evaluation.')
    rows = []
    for name, (resume, jd) in CASES.items():
        base = server.call_openai(resume, jd)  # single prompt + the old post-hoc validator
        raw = agent.openai_llm()
        ag = agent.run_agent(resume, jd, raw)
        rows.append((name, len(base['suggestions']), fabricated(resume, base['suggestions']),
                     len(ag['suggestions']), fabricated(resume, ag['suggestions']),
                     ag['agent']['repair_rounds'], len(ag['agent']['dropped']), ag['agent']['llm_calls'],
                     sum(r['status'] != 'not_evidenced' for r in ag['requirements']), len(ag['requirements'])))
    lines = ['| Case | Baseline rewrites | Baseline flagged | Agent rewrites | Agent flagged | Repair rounds | Rejected | LLM calls | Reqs evidenced |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]}/{r[9]} |')
    out = '\n'.join(lines)
    (ROOT / 'eval' / 'results.md').write_text(out + '\n')
    print(out)


if __name__ == '__main__':
    main()
