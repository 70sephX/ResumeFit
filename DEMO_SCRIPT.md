# ResumeFit — 3-Minute Capstone Live Demo

**Before starting:** launch `http://127.0.0.1:8001`, ensure the page loads, and keep a backup of the sample resume and job description. Do not disclose your API key on-screen. Test your chosen demonstration path beforehand.

### 0:00–0:25 | The real problem

“Job seekers apply to positions with different requirements but usually have one static resume. Manually tailoring bullet points is time-consuming, and unconstrained AI can invent skills or accomplishments. ResumeFit focuses on **truthful**, evidence-based tailoring.”

### 0:25–0:50 | Show the product

“The blue and white dashboard lets users upload a PDF, Word or TXT resume, paste a job description, and receive requirements, grounded bullet suggestions and documented gaps. We also offer accounts, history and a credit-based billing architecture.”

Upload the supplied fictional example Word file if created by you, or click **Try the interactive demo**.

### 0:50–1:35 | Demonstrate evidence

Open a **JD Key Requirement** chip and its supporting resume quote. Click **Show source proof** on a bullet. Point out the **Before**, **After** and **Why changed** columns.

“This is more auditable than a black-box rewrite: the model is instructed to quote the evidence, and the backend rejects suggestions with missing source text or novel metrics and selected technical tools.”

### 1:35–2:10 | Make a resume version

Click **Accept** for the machine-learning suggestion, optionally **Edit**, then **Apply accepted edits**. Click **Export Word .docx**. Open the generated file to demonstrate the entire flow is functional.

### 2:10–2:30 | Expose a skill gap

Click the AWS/GCP requirement: notice **Not evidenced**. Explain that the product will not insert a missing qualification or invent cloud experience.

### 2:10–2:30 (real-AI runs) | Show the agent, not just the answer

Open **How the agent worked**: point to the plan, the retrieval step, and a verify round that failed and was repaired (or a rewrite that was rejected). Open **Fact Bank** and explain that saved facts are retrieved as evidence but never inserted into a resume without review. “A chatbot can’t check its own claims against your resume or remember your verified experience across applications; this does.”

### 2:30–3:00 | Technology + next steps

“Our front end uses vanilla JavaScript, with a Python FastAPI backend, private SQLite history, and an optional OpenAI API for genuinely context-aware rewriting. A test-mode Stripe Checkout integration supports the credit model. For production, I would add a managed database, email verification, rate limits and verified Stripe testing.”

**If the app says Rule-based demo:** explicitly say “This run uses our deterministic demo analysis engine; real LLM mode requires a configured OpenAI API key.” Never imply the demo is live AI.

**If real AI is enabled:** log in beforehand and demonstrate one real tailored run; check the badge *Real AI · Live analysis*. Do not use unverified generated achievements.

## Professor evaluation checklist

- Clear problem statement — time-consuming JD tailoring and unsupported AI claims.
- Thoughtful design — front-end, API, parser, OpenAI, validators, persistence and payment boundaries.
- Working implementation — functioning uploads, demo, review and exports, with automated tests.
- Live demo — real clicks, source evidence, accept/edit/apply, export.
- Lessons learned — document parsing variability, grounding limits, API costs, scaling and privacy.

## Q&A to prepare

**Why no ATS score?** A percentage without access to the exact employer ATS is misleading. The app shows requirement evidence and gaps instead.

**How do you prevent hallucinations?** The agent maps requirements to fact IDs (evidence is looked up in code), splits each rewrite into claims, and requires every claim to be backed by a quote that exists in the source bullet. Failures are sent back for repair and then dropped. Rule checks reject new numbers/tools, and the user approves every edit. In our eval, the single-prompt baseline produced 3 flagged rewrites on a low-match case; the agent produced none. This reduces risk but is not a guarantee.

**Is it just a ChatGPT wrapper?** No: multi-step plan/retrieve/verify/repair loop, retrieval over a persistent per-user Fact Bank, deterministic verification, bounded cost, and honest refusal when nothing can be supported.

**How will you make money?** A free trial of three successful AI analyses, followed by pay-as-you-go credits (5 for $4.99, illustrative/test pricing). Actual payment requires separate activation.
