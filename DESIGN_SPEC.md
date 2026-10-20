# ResumeFit — UI Specification (selected mockup)

**Chosen visual direction:** White/light-blue professional SaaS interface with blue CTAs. The original generated image reference selected by the project owner is provided as `selected-ui-reference.png` (concept art, not a screenshot of the working implementation).

## Design tokens
- Primary text: `#101e40`
- Accent blue: `#2872f6`
- Page background: `#f7faff`
- Soft blue: `#f0f6ff`
- Positive/grounded rephrase: soft green `#e9f9f0`
- Neutral card border: `#e5ebf5`
- Card radius: 12–16px
- Typeface: system UI sans-serif (Inter-like)

## Screen structure
1. **Persistent header** — ResumeFit logo, Home / History / Pricing, credit count and profile.
2. **Hero / process strip** — value proposition, three steps (input → analyze → results).
3. **Left input column** — resume textarea and JD textarea, with try-example buttons and primary Tailor Resume CTA.
4. **Right analysis column** — requirement chips, before/after/why grid, missing qualifications, summary and next steps; save/download action.
5. **History** — saved jobs and restore prior analysis.
6. **Pricing** — free / one-time credit packages.
7. **Authentication modal** — register and sign in.

## UX notes
- Input fields have character counters and min length validation.
- Result tags distinguish `Example Preview`, `Rule-based Demo` and `Real AI Analysis`.
- Result cards only present evidence-backed modifications; user reviews and copies bullets individually.
- Responsive design stacks columns below tablet width.
- The visual reference may contain text invented for mock presentation only; factuality constraints apply to actual generated output.
