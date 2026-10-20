"""ResumeFit tailoring agent.

A multi-step, tool-using pipeline instead of one prompt:

  1. plan      LLM   JD -> prioritized requirements (+ deterministic keyword tool)
  2. retrieve  tool  BM25 over the resume's facts AND the user's saved fact bank (RAG)
  3. map       LLM   requirement -> fact ids. Evidence is looked up by id, never free-typed.
  4. draft     LLM   rewrite only the facts that serve must-have requirements
  5. verify    LLM + code   claim-by-claim check; every "supported" claim needs a quote
                     that is a real substring of the source fact. Failures go back to
                     step 4 with feedback (bounded repair loop), then are dropped.
  6. coach     LLM   summary + honest next steps for gaps

Every step is recorded in a trace that is returned to the UI. The LLM is injected
(`llm(step, system, user) -> dict`) so the whole loop is testable without a network.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from typing import Callable

MAX_REPAIR_ROUNDS = 2
MAX_DRAFTS = 5
TIME_BUDGET_SEC = 150
MAX_FACTS = 60

LLM = Callable[[str, str, str], dict]


class AgentError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------- text helpers
def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()


STOP = set('''and the with for of in to on a an or as at by is are be we our you your this that from have has
will do it they their across using use experience ability knowledge strong relevant excellent who skills skill
work working plus including good understanding familiar such etc can able into more also not but may must should
years year role team company candidate position job responsibilities requirements preferred required'''.split())


def stem(w: str) -> str:
    for suf in ('ing', 'ed', 'es', 's', 'ly'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def tokens(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r'[a-z][a-z0-9+#.]*[a-z0-9+#]|[a-z]', (text or '').lower())
            if w not in STOP and len(w) > 1]


KNOWN_TOOLS = ['Python', 'SQL', 'Tableau', 'Excel', 'Power BI', 'AWS', 'GCP', 'Azure', 'React', 'Node.js',
               'MongoDB', 'Docker', 'Kubernetes', 'PyTorch', 'TensorFlow', 'Spark', 'BigQuery', 'Databricks',
               'Snowflake', 'SAS', 'MATLAB', 'JavaScript', 'GitHub', 'Java', 'R', 'Looker', 'Hadoop',
               'Airflow', 'dbt', 'Git', 'Pandas', 'NumPy', 'scikit-learn', 'Figma', 'Jira', 'Salesforce']


def mentions(text: str, term: str) -> bool:
    return bool(re.search(r'(?<![\w.])' + re.escape(term) + r'(?![\w])', text, re.I if len(term) > 1 else 0))


NUM_RE = re.compile(r'(?<!\w)\d+(?:[.,]\d+)?%?')


# ---------------------------------------------------------------- facts + retrieval (RAG)
SECTION_RE = re.compile(r'^(?:[A-Z][A-Z &/]{2,40}|(?:experience|education|skills|projects|summary|work experience|'
                        r'professional experience|leadership|activities|certifications|awards)[:\s]*)$', re.I)


def extract_facts(resume: str) -> list[dict]:
    """Split a resume into atomic, citable facts (bullets and substantial lines)."""
    facts: list[dict] = []
    section = 'Header'
    for line in resume.splitlines():
        raw = line.strip()
        if not raw:
            continue
        m = re.match(r'^(?:[-•*▪●]|\d+[.)])\s*(.+)$', raw)
        text = (m.group(1) if m else raw).strip()
        if not m and len(text) < 60 and SECTION_RE.match(text.rstrip(':')):
            section = text.rstrip(':').title()
            continue
        if len(text) < 14:
            continue
        facts.append({'id': f'F{len(facts) + 1}', 'text': text, 'source': 'resume', 'section': section})
        if len(facts) >= MAX_FACTS:
            break
    return facts


class BM25:
    """Small dependency-free BM25 index. Resumes are tiny, so this is instant."""

    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = [Counter(tokens(d['text'] + ' ' + d.get('section', ''))) for d in docs]
        self.len = [sum(t.values()) or 1 for t in self.tf]
        self.avg = sum(self.len) / max(len(docs), 1)
        df: Counter = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + .5) / (c + .5)) for w, c in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[dict, float]]:
        q = tokens(query)
        scored = []
        for doc, tf, ln in zip(self.docs, self.tf, self.len):
            s = 0.0
            for w in q:
                if w in tf:
                    s += self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * ln / self.avg))
            scored.append((doc, s))
        scored.sort(key=lambda x: -x[1])
        return [x for x in scored[:k] if x[1] > 0]


def retrieve(index: BM25, facts: list[dict], query: str, k: int = 5, min_hits: int = 3) -> list[dict]:
    """Top-k facts for a query. If lexical retrieval is thin (synonyms, e.g. 'visualization' vs
    'dashboards'), pad with the remaining facts so the mapper can still judge semantic matches."""
    hits = [d for d, _ in index.search(query, k)]
    if len(hits) < min_hits:
        seen = {h['id'] for h in hits}
        hits += [f for f in facts if f['id'] not in seen][: min_hits - len(hits)]
    return hits


def jd_keywords(jd: str) -> list[str]:
    """Deterministic tool: tools/technologies explicitly named in the job description."""
    return [t for t in KNOWN_TOOLS if mentions(jd, t)]


# ---------------------------------------------------------------- deterministic claim checks
def hard_flags(after: str, source: str, resume: str) -> list[str]:
    """Rules that never need an LLM: new numbers, new named tools, mostly-new wording."""
    flags = []
    src_nums = set(NUM_RE.findall(source))
    new_nums = [n for n in NUM_RE.findall(after) if n not in src_nums]
    if new_nums:
        flags.append(f'introduces numbers not in the source bullet: {", ".join(new_nums)}')
    new_tools = [t for t in KNOWN_TOOLS if mentions(after, t) and not mentions(source, t)]
    if new_tools:
        flags.append(f'introduces tools not in the source bullet: {", ".join(new_tools)}')
    src_stems = set(tokens(source))
    after_toks = tokens(after)
    novel = [w for w in after_toks if w not in src_stems]
    if after_toks and len(novel) / len(after_toks) > 0.5:
        flags.append('more than half of the wording is new; keep to the source facts')
    return flags


# ---------------------------------------------------------------- prompts
P_PLAN = '''You analyse job descriptions. Return ONLY JSON: {"requirements":[{"text":str,"priority":"must"|"nice"}]}.
Extract 3-8 distinct, concrete requirements (skills, responsibilities, qualifications). "must" = stated as required
or core duty; "nice" = preferred/bonus. Short phrases, no duplicates, no information that is not in the posting.'''

P_MAP = '''You map job requirements to resume facts. You get a list of requirements, each with candidate facts
({"id","text"}). Return ONLY JSON: {"mappings":[{"index":int,"status":"matched"|"partial"|"not_evidenced","fact_ids":[str],"note":str}]}.
Rules: a job description is NEVER evidence. "matched" only if a listed fact explicitly shows the skill or duty.
"partial" if a fact is related but does not show it directly. Otherwise "not_evidenced" with empty fact_ids.
Only use ids that were provided. Absence from the resume means "not documented", not "cannot do".'''

P_DRAFT = '''You rewrite resume bullets for a target job WITHOUT INVENTING ANYTHING. You get items
{"fact_id","fact_text","requirement"}; optionally "previous_attempt" and "problems" to fix.
Return ONLY JSON: {"drafts":[{"fact_id":str,"after":str,"why":str}]}.
Rules: "after" may reorder, tighten and use stronger verbs, and may echo the requirement's wording ONLY where the fact already
shows it. Never add a tool, skill, number, percentage, outcome, scope, team size, title or employer that is not in fact_text.
Keep one concise bullet (<= 35 words). "why" is one sentence naming which requirement it serves. If "problems" is given,
fix exactly those problems by removing the unsupported content.'''

P_VERIFY = '''You are a strict fact-checker for resume rewrites. You get items {"fact_id","source_text","rewrite"}.
Return ONLY JSON: {"checks":[{"fact_id":str,"claims":[{"claim":str,"supported":bool,"quote":str}]}]}.
Split each rewrite into its atomic factual claims (skills, tools, actions, scope, numbers, outcomes). For each claim mark
supported=true ONLY if source_text states it, and give "quote": an exact contiguous substring of source_text proving it.
If no such quote exists, supported=false and quote="". Be strict about implied scope or impact ("led", "improved", "enterprise").'''

P_COACH = '''You are a candid career coach. You get requirements with status and the evidence found. Return ONLY JSON:
{"summary":str,"gap_actions":[{"requirement":str,"action":str}]}.
"summary": 2-3 sentences of concrete advice based strictly on the supplied statuses. For each not_evidenced requirement
(max 4) give one "action": a truthful next step such as "If you have done X, add a bullet about Y; otherwise a small project
could show it". Never claim the person has the skill. No scores, no hiring predictions.'''


# ---------------------------------------------------------------- the agent
class Run:
    def __init__(self, llm: LLM):
        self.llm, self.trace, self.calls, self.t0 = llm, [], 0, time.time()

    def step(self, name: str, detail: str, **extra):
        self.trace.append({'step': name, 'detail': detail, 'at': round(time.time() - self.t0, 2), **extra})

    def ask(self, step: str, system: str, payload) -> dict:
        if time.time() - self.t0 > TIME_BUDGET_SEC:
            raise AgentError(504, 'The analysis took too long. Please try again.')
        self.calls += 1
        out = self.llm(step, system, json.dumps(payload, ensure_ascii=False))
        if not isinstance(out, dict):
            raise AgentError(502, 'AI did not return a valid structured response.')
        return out


def run_agent(resume: str, jd: str, llm: LLM, bank: list[str] | None = None) -> dict:
    run = Run(llm)
    resume_facts = extract_facts(resume)
    if not resume_facts:
        raise AgentError(422, 'Could not find any experience statements in the resume. Use one bullet or sentence per line.')
    bank_facts = [{'id': f'B{i + 1}', 'text': clean(t), 'source': 'bank', 'section': 'Fact bank'}
                  for i, t in enumerate(bank or [])][:MAX_FACTS]
    pool = resume_facts + bank_facts
    by_id = {f['id']: f for f in pool}
    index = BM25(pool)
    run.step('index', f'Indexed {len(resume_facts)} resume facts and {len(bank_facts)} fact-bank entries for retrieval.')

    # 1. plan ----------------------------------------------------------------
    kws = jd_keywords(jd)
    plan = run.ask('plan', P_PLAN, {'job_description': jd, 'tools_named_in_posting': kws})
    reqs = []
    for item in (plan.get('requirements') or [])[:8]:
        if isinstance(item, dict) and clean(str(item.get('text', ''))):
            reqs.append({'text': clean(str(item['text']))[:170],
                         'priority': 'nice' if item.get('priority') == 'nice' else 'must'})
    if not reqs:
        raise AgentError(502, 'AI did not extract any requirements from the job description.')
    run.step('plan', f'Extracted {len(reqs)} requirements ({sum(r["priority"] == "must" for r in reqs)} must-have).',
             requirements=[r['text'] for r in reqs])

    # 2-3. retrieve + map ------------------------------------------------------
    cands = [retrieve(index, pool, r['text']) for r in reqs]
    run.step('retrieve', 'BM25 retrieval per requirement: ' + '; '.join(
        f'#{i + 1}→{",".join(c["id"] for c in cs)}' for i, cs in enumerate(cands)))
    mp = run.ask('map', P_MAP, {'requirements': [
        {'index': i, 'requirement': r['text'], 'candidates': [{'id': c['id'], 'text': c['text']} for c in cands[i]]}
        for i, r in enumerate(reqs)]})
    maps = {m.get('index'): m for m in (mp.get('mappings') or []) if isinstance(m, dict)}
    for i, r in enumerate(reqs):
        m = maps.get(i, {})
        allowed = {c['id'] for c in cands[i]}
        ids = [x for x in (m.get('fact_ids') or []) if isinstance(x, str) and x in allowed]
        ids.sort(key=lambda x: by_id[x]['source'] != 'resume')  # prefer evidence from this resume
        status = m.get('status') if m.get('status') in ('matched', 'partial', 'not_evidenced') else 'not_evidenced'
        if not ids:
            status = 'not_evidenced'
        r.update(status=status, fact_ids=ids,
                 evidence=by_id[ids[0]]['text'] if ids else '', source=by_id[ids[0]]['source'] if ids else '')
    run.step('map', 'Mapped requirements to facts: ' + ', '.join(f'#{i + 1}={r["status"]}' for i, r in enumerate(reqs)))

    # 4. draft targets -----------------------------------------------------------
    targets, seen = [], set()
    for r in sorted(reqs, key=lambda r: (r['priority'] != 'must', r['status'] != 'matched')):
        if r['status'] == 'not_evidenced':
            continue
        fid = next((x for x in r['fact_ids'] if by_id[x]['source'] == 'resume' and x not in seen), None)
        if fid:
            seen.add(fid)
            targets.append({'fact_id': fid, 'fact_text': by_id[fid]['text'], 'requirement': r['text']})
    targets = targets[:MAX_DRAFTS]
    run.step('select', f'Selected {len(targets)} resume facts to rewrite (must-have requirements first).')

    accepted: dict[str, dict] = {}
    dropped: list[dict] = []
    pending = {t['fact_id']: t for t in targets}
    feedback: dict[str, dict] = {}
    rounds = 0
    while pending and rounds <= MAX_REPAIR_ROUNDS:
        rounds += 1
        items = [{**t, **feedback.get(fid, {})} for fid, t in pending.items()]
        drafts = run.ask('draft', P_DRAFT, {'items': items}).get('drafts') or []
        drafts = {d['fact_id']: d for d in drafts if isinstance(d, dict) and d.get('fact_id') in pending
                  and clean(str(d.get('after', '')))}
        # 5. verify ----------------------------------------------------------------
        checks_in = [{'fact_id': fid, 'source_text': pending[fid]['fact_text'], 'rewrite': clean(str(d['after']))}
                     for fid, d in drafts.items()]
        checks = {}
        if checks_in:
            for c in run.ask('verify', P_VERIFY, {'items': checks_in}).get('checks') or []:
                if isinstance(c, dict):
                    checks[c.get('fact_id')] = c
        next_pending, passed, failed = {}, [], []
        for fid, t in pending.items():
            d = drafts.get(fid)
            problems = []
            if not d:
                problems.append('no rewrite was produced')
            else:
                after = clean(str(d['after']))[:650]
                src = t['fact_text']
                problems += hard_flags(after, src, resume)
                claims = [c for c in (checks.get(fid, {}).get('claims') or []) if isinstance(c, dict)]
                if not claims:
                    problems.append('the verifier returned no claim breakdown')
                good = []
                for c in claims:
                    q = clean(str(c.get('quote', '')))
                    ok = bool(c.get('supported')) and len(q) >= 3 and q.casefold() in clean(src).casefold()
                    good.append({'claim': clean(str(c.get('claim', '')))[:200], 'supported': ok, 'quote': q if ok else ''})
                    if not ok:
                        problems.append(f'unsupported claim: "{clean(str(c.get("claim", "")))[:120]}"')
            if problems:
                failed.append(fid)
                next_pending[fid] = t
                feedback[fid] = {'previous_attempt': clean(str(d['after'])) if d else '', 'problems': problems}
            else:
                passed.append(fid)
                accepted[fid] = {'before': t['fact_text'], 'after': after,
                                 'why': clean(str(d.get('why', '')))[:400] or f'Emphasizes: {t["requirement"]}.',
                                 'evidence': t['fact_text'], 'source': 'resume', 'fact_id': fid,
                                 'requirement': t['requirement'], 'verified': True, 'claims': good,
                                 'attempts': rounds}
        run.step('verify', f'Round {rounds}: {len(passed)} rewrite(s) passed claim-checking, {len(failed)} failed'
                 + (f' → sent back with feedback.' if failed and rounds <= MAX_REPAIR_ROUNDS else '.'),
                 passed=passed, failed=failed)
        pending = next_pending
        if rounds > MAX_REPAIR_ROUNDS:
            break
    for fid, t in pending.items():
        dropped.append({'fact': t['fact_text'], 'reason': '; '.join(feedback.get(fid, {}).get('problems', []))[:300]})
    if dropped:
        run.step('drop', f'Dropped {len(dropped)} rewrite(s) that could not be verified after {MAX_REPAIR_ROUNDS} repair rounds '
                 '(better no suggestion than an unsupported one).')
    suggestions = [accepted[t['fact_id']] for t in targets if t['fact_id'] in accepted]

    # 6. coach -------------------------------------------------------------------
    coach = run.ask('coach', P_COACH, {'requirements': [
        {'requirement': r['text'], 'priority': r['priority'], 'status': r['status'], 'evidence': r['evidence']} for r in reqs]})
    missing = [r['text'] for r in reqs if r['status'] == 'not_evidenced'][:6]
    actions = [{'requirement': clean(str(a.get('requirement', '')))[:170], 'action': clean(str(a.get('action', '')))[:400]}
               for a in (coach.get('gap_actions') or [])[:4] if isinstance(a, dict) and a.get('action')]
    for r in reqs:
        if r['source'] == 'bank':
            actions.append({'requirement': r['text'], 'action':
                            f'Your fact bank already documents this but this resume does not: “{r["evidence"][:160]}”. Consider adding it.'})
    run.step('coach', 'Wrote summary and next steps for gaps.')
    return {
        'requirements': [{k: r[k] for k in ('text', 'priority', 'status', 'evidence', 'source')} for r in reqs],
        'suggestions': suggestions, 'missing': missing, 'gap_actions': actions,
        'summary': clean(str(coach.get('summary', '')))[:1000], 'mode': 'ai',
        'agent': {'steps': run.trace, 'llm_calls': run.calls, 'repair_rounds': max(rounds - 1, 0),
                  'dropped': dropped, 'seconds': round(time.time() - run.t0, 1)},
    }


# ---------------------------------------------------------------- OpenAI client
def openai_llm(usage: dict | None = None) -> LLM:
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
    key = os.getenv('OPENAI_API_KEY', '')
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    def call(step: str, system: str, user: str) -> dict:
        body = {'model': model, 'temperature': 0.1, 'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        req = Request('https://api.openai.com/v1/chat/completions', data=json.dumps(body).encode(), method='POST',
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=50) as r:
                data = json.loads(r.read().decode())
            if usage is not None:
                u = data.get('usage') or {}
                usage['in'] = usage.get('in', 0) + u.get('prompt_tokens', 0)
                usage['out'] = usage.get('out', 0) + u.get('completion_tokens', 0)
            return json.loads(data['choices'][0]['message']['content'])
        except HTTPError as e:
            raise AgentError(502, f'AI provider error ({e.code}) during "{step}". Check your API key and model access.')
        except TimeoutError:
            raise AgentError(504, 'AI provider timed out. Please try again.')
        except URLError as e:
            raise AgentError(502, f'Could not reach the AI provider: {e.reason}')
        except (ValueError, KeyError, IndexError, TypeError):
            raise AgentError(502, f'AI did not return valid JSON during "{step}".')
    return call
