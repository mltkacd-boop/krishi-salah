# UI Refinement — Removing Academic and Internal Technical Detail

Presentation-layer change only. No backend file, rule, threshold, prompt or API
schema was touched; the palette, typography, navigation and page layout are the
ones delivered in the redesign pass.

---

## 1. The Gates Foundation attribution

**Claim under review.** The About page carried
`Project Type: Group Project | Source: Bill & Melinda Gates Foundation-linked
agricultural decision support`, taken from the project blueprint.

**How it was checked.** A repository-wide search for `Gates` (case-insensitive)
over every tracked file, excluding `node_modules`, `dist`, `.venv` and the
database data directory:

```
rg -i "gates" -g '!node_modules' -g '!dist' -g '!.venv' -g '!.pgdata'
```

**Result.** One non-generated hit:

| File | Line | Text |
| --- | --- | --- |
| `01_Blueprint/PROJECT_ARCHITECTURE_BLUEPRINT.md` | 5 | `**Project Type:** Group Project \| **Source:** Bill & Melinda Gates Foundation-linked agricultural decision support` |

There is no assignment brief, course handout or institutional document in this
repository, and nothing in the fetched knowledge-base sources, the fixtures or
the test data refers to the foundation. The only support for the claim is the
project's own blueprint — i.e. it is a description the project wrote about
itself, not a documented fact from the assignment.

**Decision.** Removed from every rendered surface, as instructed for the case
where the assignment documentation does not explicitly support it. The
blueprint file itself is left untouched (it is a design artefact, not a UI
surface) and this note records that the attribution is unverified rather than
confirmed.

---

## 2. Public About page (`/project-info`)

Before: a submission-style page — registration number, section, course, project
type, and a paragraph describing the assignment.

After: a page that answers a farmer's four questions, in the order they are
asked.

| Block | Content | Source |
| --- | --- | --- |
| What Krishi Salah does | Answers questions about a pest, a crop or a safety rule; assembled from published Indian agricultural sources; checked against fixed safety rules; says what is missing instead of guessing | static copy |
| What it covers today | The pilot's scope, the crop chips and `N records · M sources` | live `/knowledge-base/crops`, `/approved-uses`, `/sources` |
| Languages | English and Hindi, with the honest caveat that retrieval compares words, not meaning | static copy |
| What every answer shows | Source, the status of PHI/REI/PPE, a clear next step — including when no answer can be given | static copy |
| How an answer is built | 4 steps: write the question → we find the record → the rules decide → the answer, with sources | static copy |
| Limits of this pilot | No record publishes PHI + REI + PPE together, so chemical answers stay educational; CIB&RC is never queried; the knowledge base is small; this is not a substitute for the label | static copy, matching the backend's own `reason` |

Removed: the student's registration number, the section code, the course code
(`CSE 276`), the project type (`Group Project`), and the Gates line. The project
title survives in one place, as a footer line (`Academic pilot · <title>`) that
also links to the evaluation view.

No regulatory approval, registration or production readiness is claimed
anywhere on the page; the limits block says the opposite in four sentences.

The site-wide footer no longer prints `CSE 276 · …`; it now prints the project
title only. The course code is on `/evaluation`, where an evaluator looks for it.

---

## 3. Farmer-facing decision labels

The backend's six classes, rendered as sentences. The raw value never reaches
the screen — it survives as a `data-decision` attribute for tests and
evaluators.

| Backend value | English | Hindi |
| --- | --- | --- |
| `ACTIONABLE_RECOMMENDATION` | Verified recommendation | सत्यापित सिफ़ारिश |
| `EDUCATIONAL_INFORMATION` | Educational information only | केवल शैक्षिक जानकारी |
| `SAFETY_REFUSAL` | Cannot provide a safe recommendation | सुरक्षित सिफ़ारिश संभव नहीं |
| `REGULATORY_VERIFICATION_REQUIRED` | Product approval needs verification | उत्पाद अनुमोदन की पुष्टि आवश्यक |
| `ESCALATION_REQUIRED` | Consult an agricultural expert | कृषि विशेषज्ञ से सलाह लें |
| `CLARIFICATION_REQUIRED` | More information needed | अधिक जानकारी चाहिए |

Each class also carries a one-sentence description and its own icon, so meaning
never depends on colour alone.

Other labels removed from the ordinary surface:

- the raw `outcome` and `answer_scope` values beside the badge — the badge no
  longer prints `answered`, `needs_clarification`, `crop-level`, etc.;
- `confidence_label` **plus** the number: the meter now reads `Low / Medium /
  High` and its bar width is chosen by label (34 / 67 / 100 %), so a percentage
  cannot be recovered from it;
- `retrieval 0.46 · classifier 0.85` under the meter;
- rule identifiers and machine codes in "Why this decision": the list renders
  the backend's message with a plain severity word (`Blocks the answer`,
  `Educational information only`, `Important caution`);
- per-citation `sha256`, `verification_status`, `record_ids` and passage counts.

---

## 4. What stays visible on purpose

The brief's list of things a farmer keeps is unchanged:

- source name, authority and an outbound link on every citation (`target="_blank"`,
  `rel` set), plus publication date where the source publishes one and the
  reliability tier;
- the missing-information panel (`Pre-harvest interval (PHI)`, `Re-entry
  interval (REI)`, `Protective equipment (PPE)`, `Regulatory approval`) in a
  gold card that is never collapsed and is rendered above the sources;
- the safety panel with `Not published in source` for each unpublished value,
  and the backend's own explanation of why;
- the usage policy line (educational only, not a pesticide recommendation, not a
  regulatory approval, not a substitute for the label);
- "What to do next", driven by the backend's `outcome`.

Nothing was softened, reordered into a disclosure, or made smaller.

---

## 5. Where the technical detail went

Two layers, both reading the same public GET endpoints, neither containing a
credential (the backend returns none; `CORS_ORIGINS`, `DB_SSLMODE` and
`VECTOR_STORAGE_MODE` are never sent to the client).

**a. Per result — "Technical details (for evaluation)"**
Collapsed by default, inside the result page. It is a controlled disclosure:
`aria-expanded` / `aria-controls` on the button, and the body is not mounted at
all until it is opened, so the text cannot be found by a screen reader, a text
search or a test until someone asks for it. Contents: `decision`, `outcome`,
`advisory_status`, `answer_scope`, `generation_mode`, `gate_detail`, raw
`confidence` + `confidence_components`, the rule table (`rule_id`, `code`,
`severity`, `action`), the evidence table (`chunk_ref`, `chunk_type`,
`approved_use_id`, score), citation metadata (`source_id`, `verification_status`,
`sha256`, `record_ids`, `chunk_refs`), the raw `classification` object, and
model versions with the usage policy.

**b. Cross-cutting — `/evaluation`**
Linked from the footer ("Evaluation details") and from the safety page. Six
cards: retrieval index and its thresholds, the rule engine (all five rules with
trigger/action/severity, block precedence, thresholds, KB counts and the
backend's `reason`), the question classifier (type, targets, thresholds,
training metadata, note), knowledge-base storage (`repository_class`, fallback
reason, env-var name, `vector_store`, record counts), and the project record —
**the technical project title only**, with a link back to About.

The Project record card previously carried the student's name, section, course
and project type. All four were removed in the final refinement: they identify
the coursework, not the system under evaluation, and they are now asserted
absent from every route, this one included.

The safety page kept its substance and lost its identifiers: it now explains
PHI, REI, PPE, the label and CIB&RC in plain words, states why missing data stops
a recommendation, and shows the live `0 / 9 records are actionable` count with
the backend's reason verbatim. The rule registry, precedence and thresholds that
used to sit on that page moved to `/evaluation`.

---

## 6. Safety constraints — what was and was not touched

| Constraint | Status |
| --- | --- |
| Rule engine unmodified | No file under `backend/app/rules/` or `backend/app/services/` changed |
| Backend decision logic unmodified | No backend file changed in this pass; `pytest` 443 passed |
| Safety warnings not suppressed | Missing-information card, safety panel and policy line all still render, above the fold of the answer body |
| No invented PHI/REI/PPE/regulatory data | Every value displayed comes from the response; unpublished values still read `Not published in source` |
| Frontend cannot override a decision | No control sets `decision`/`outcome`; the only client state is the collapse state of the technical block; `AdvisoryRequest` keeps `extra="forbid"` |
| Citations and evidence preserved | Citations unchanged in content; evidence and per-citation hashes moved into the technical block, not deleted |

---

## 7. Files changed in this pass

Rewritten
- `frontend/src/components/DecisionBadge.tsx` — friendly labels only; raw class,
  outcome and scope as `data-*` attributes.
- `frontend/src/components/ConfidenceMeter.tsx` — `{ label }` only; no number, no
  inputs feeding a hidden percentage.
- `frontend/src/components/AdvisoryResult.tsx` — plain-language rule findings,
  citation card without hashes, click-gated `TechnicalDetails`; severity chip is
  now a nowrap label that stacks above its message on mobile.
- `frontend/src/pages/ProjectInfo.tsx` — public About.
- `frontend/src/pages/SafetyGuidelines.tsx` — plain words, gate band, live
  actionable count, link to `/evaluation`.
- `frontend/src/pages/Home.tsx` — dropped the indexed-passages stat (an internal
  retrieval diagnostic) and the `status()` fetch that fed it.

Added
- `frontend/src/pages/Evaluation.tsx` — `/evaluation`.
- `frontend/src/pages/Evaluation.test.tsx` — 2 tests.
- `frontend/src/components/AdvisoryResult.test.tsx` — 7 tests.
- `frontend/src/pages/ProjectInfo.test.tsx` — 3 tests.
- `backend/scripts/presentation_check.py` — 59-check acceptance sweep.
- `frontend/src/presentationBoundary.test.tsx` — 13 tests: every route, in both
  languages, rendered through the real layout, asserting no submission metadata.
- `screenshots/refinement/` — 19 screenshots + `presentation-report.json`.

Edited
- `frontend/src/pages/App.tsx` — `/evaluation` route (`/dashboard` alias kept).
- `frontend/src/layouts/AppLayout.tsx` — footer link to `/evaluation`.
- `frontend/src/i18n/strings.ts` — decision labels, About copy, `eval.*` family,
  technical-detail labels, footer title line; both languages.
- `frontend/src/types/api.ts` — `ModelInfoResponse`, `KnowledgeBaseStatusResponse`.
- `frontend/src/services/classificationService.ts` — `modelInfo()`.
- `frontend/src/services/knowledgeBaseService.ts` — `status()`.
- `frontend/src/components/DecisionBadge.test.tsx` — new labels; `data-outcome`
  asserted; `it.each` over all six classes proving the raw name never prints.

---

## 8. Verification actually run

| Check | Result |
| --- | --- |
| `npx tsc --noEmit` | 0 errors |
| `npx vitest run` | **65 passed**, 9 files |
| `npx vite build` | ok — `index-BmIZegQD.css` 32.19 kB (6.57 gzip), `index-DQ0vjMd2.js` 263.14 kB (80.48 gzip) |
| `pytest -q` (backend) | **443 passed** |
| `scripts/phase9_integration_check.py` | **31 / 31** — real HTTP, real browser, 5 routes × 7 widths, nav, handoff, language switch |
| `scripts/presentation_check.py` | **59 / 59** |

`presentation_check.py` is the acceptance test for this brief. It drives the
real app through the real API and reads `document.body.innerText`, so hidden or
collapsed content does not count as visible. It asserts:

- no registration number, section code, student name, `CSE 276`, `Group Project`
  or `Gates`;
- no decision enum, no `R1_…`–`R5_…`, no `gate_detail` / `advisory_status` /
  `confidence_components`, no `SHA256`, no `chunk-`, on home, library, safety,
  about and every result page, at 1440 and at 390;
- the four reachable decision classes come back from the live API as
  `EDUCATIONAL_INFORMATION`, `SAFETY_REFUSAL`, `CLARIFICATION_REQUIRED`,
  `ESCALATION_REQUIRED`, on desktop and mobile, and the Hindi question
  `धान का तना छेदक` still returns an educational answer;
- `R2_REQUIRE_SAFETY_FIELDS` is absent before the technical block is opened and
  present after — i.e. the diagnostics are preserved *and* separated;
- `/evaluation` shows rule ids and `clf-1.0.0`, contains no registration number
  and no credential-shaped string, and does not overflow at 390 or 1440.

Decision classes exercised: **four of six.** `ACTIONABLE_RECOMMENDATION` and
`REGULATORY_VERIFICATION_REQUIRED` remain unreachable in this build because no
record has a complete published PHI/REI/PPE profile (0/9) and the CIB&RC
registry is never queried. No screenshot or claim is made for them.

Screenshots, `screenshots/refinement/`: `home`, `library`, `safety`,
`about-desktop-1440`, `about-mobile-390`, `about-desktop-hindi`,
`result-{educational,refusal,clarification,escalation}-desktop-1440`,
`result-{…}-mobile-390`, `result-hindi-desktop-1440`,
`result-technical-open-desktop-1440`, `evaluation-desktop-1440`,
`evaluation-desktop-hindi`, `evaluation-mobile-390`.

---

## 9. Known limitations

1. `ACTIONABLE_RECOMMENDATION` and `REGULATORY_VERIFICATION_REQUIRED` cannot be
   produced by this knowledge base, so their new labels are verified by unit test
   only.
2. The app has no React error boundary. A render exception blanks the page. This
   was hit for real during this pass: `/evaluation` crashed on the nested
   classifier-threshold object, because an object is not a valid React child, and
   the page rendered empty. Fixed by flattening values in `formatValue()`; a
   boundary would turn any future occurrence into a visible error instead of a
   blank page, and is worth adding outside this presentation-only scope.
3. Some text inside a Hindi answer is English: the backend's source-check
   messages and quoted source titles are data, not interface copy, and were not
   translated because translating them would misquote the source.
4. `/evaluation` is linked, not access-controlled — it shows engineering detail,
   not secrets. If the pilot is ever exposed publicly beyond a demo, it should
   move behind a flag.

---

## 10. Follow-up refinement — submission metadata out, engineering detail kept

Five changes, again presentation-only.

**1. Project record (`/evaluation`).** The card now contains `project_title` and
nothing else. The student's name, section, course and project type were removed,
along with the `CSE 276` eyebrow that used to sit above the page title. What
remains is the technical project title plus every engineering diagnostic the page
already carried: retrieval index and thresholds, the five-rule table with ids,
severities, actions and triggers, block precedence, rule thresholds, knowledge-base
counts and the engine's own reason, classifier type/targets/thresholds/training
metadata, storage backend and vector-store detail.

**2. Decision explanation labels.** The two labels a farmer reads beside a rule's
message are now:

| Severity | English | Hindi |
| --- | --- | --- |
| `block` | Refuses the answer | उत्तर रोकता है |
| `restrict_actionability` | Educational information only | केवल शैक्षिक जानकारी |
| `warn` | Important caution | महत्वपूर्ण सावधानी |

`Allows educational only` and `Attaches a warning` are gone; the sweep asserts the
old wording is absent and the new wording present, in both languages. The chip
sits in a 10.5 rem grid column with `whitespace-nowrap`, so the longer phrase stays
on one line instead of breaking after "Educational information".

**3. Rule identifiers are preserved, deliberately.** They are absent from the
farmer's view and present, unrenamed and unsummarised, in two technical places:
the per-result technical block (`rule_id`, `code`, `severity`, `action`) and the
rule table on `/evaluation`. Both are asserted positively, so a future tidy-up
that deletes them fails a test rather than passing silently.

**4. New boundary tests.** `frontend/src/presentationBoundary.test.tsx` renders the
whole app — layout, navigation and footer included — for all six routes in both
languages (13 tests) and fails if the student's name, registration number, section
code, `CSE 276`, `Group Project`, `Gates Foundation`, `Registration number` or
`Project type` appears anywhere in the rendered text. It mocks the services, because
the question is what the interface prints; the live contract is the Playwright
sweep. `AdvisoryResult.test.tsx` gained a test for the two severity labels, and the
`Evaluation` test now asserts the project title is present while the four
submission fields are not.

**5. Both languages, both form factors.** The Playwright sweep was extended to
59 checks: the four reachable decision classes at 1440 and 390, a Hindi question on
desktop and on mobile, the Hindi About and evaluation pages, and the academic-token
scan on ordinary routes at both sizes.

Regression results for this pass:

| Check | Result |
| --- | --- |
| `npx tsc --noEmit` | 0 errors |
| `npx vitest run` | **65 passed**, 9 files (was 46 / 7) |
| `npx vite build` | ok — `index-BmIZegQD.css` 32.19 kB (6.57 gzip), `index-DQ0vjMd2.js` 263.14 kB (80.48 gzip) |
| `pytest -q` (backend) | **443 passed** |
| `scripts/phase9_integration_check.py` | **31 / 31** |
| `scripts/presentation_check.py` | **59 / 59** |

No backend file, rule, threshold, retrieval path, colour, type scale, navigation
or layout was touched. `ACTIONABLE_RECOMMENDATION` and
`REGULATORY_VERIFICATION_REQUIRED` remain unreachable in this build (0/9 records
have a complete published PHI/REI/PPE profile), so their labels are covered by unit
tests only.

---

## 11. Phase 1 verification — React error boundary

**Was one present?** No. `getDerivedStateFromError`, `componentDidCatch` and the
string `ErrorBoundary` appeared nowhere under `frontend/src`. The consequence was
observed for real during the evaluation-page work: an object passed as a React
child threw during render and the whole page went blank, with nothing in the
interface to say what had happened.

**What was added**

`frontend/src/components/ErrorBoundary.tsx` — a class component
(`getDerivedStateFromError` + `componentDidCatch`) plus a hook-free
`ErrorFallback`. The fallback carries the Krishi Salah mark, a plain sentence, and
a `Reload the page` button calling `window.location.reload()`. It renders no
stack trace, file path, thrown message or identifier; it reads the language from
the persisted choice and then `<html lang>`, so it works even if the i18n
provider is what failed. Logging is development-only: the full error and React's
component stack in `import.meta.env.DEV`, the error's name and message in a
production build.

`frontend/src/layouts/AppLayout.tsx` — two lines changed: one import, and the
`<Outlet />` wrapped so the page renders inside the boundary. The header,
navigation, language switch and footer stay mounted, so a broken page is still a
navigable site.

**Scope, stated in the component and honest about it:** render, lifecycle and
constructor errors in the subtree below the boundary. Not API failures (services
return typed errors and the pages render them), not event-handler errors, not
rejected promises.

**Tests**

- `frontend/src/components/ErrorBoundary.test.tsx` — 8 tests: a child that throws
  during render produces the fallback and not a blank page; the thrown message,
  `at ThrowingChild`, `.tsx`, `node_modules` and the registration number never
  appear in the rendered text; the button calls `window.location.reload` exactly
  once; healthy children render through with no fallback in the tree; the error is
  logged while staying out of the interface; English by default, Hindi from the
  saved choice and from `<html lang>`.
- `frontend/src/layouts/AppLayout.test.tsx` — 2 tests: with a throwing route, the
  fallback appears while the header, both navigation bars and the footer links
  remain; a healthy route renders untouched.

The whole-app suite in `presentationBoundary.test.tsx` already renders all six
routes through `App` → `AppLayout`, so it now also proves the new boundary does
not interfere with normal rendering.

**Verification**

| Check | Result |
| --- | --- |
| `npx tsc --noEmit` | 0 errors |
| `npx vitest run` | **75 passed**, 11 files (was 65 / 9) |
| `npx vite build` | ok — `index-CZdyLs0o.css` 32.26 kB (6.58 gzip), `index-CYKC2RTw.js` 265.84 kB (81.29 gzip) |
| `scripts/phase9_integration_check.py` | **31 / 31** |
| `scripts/presentation_check.py` | **59 / 59** |

Screenshots: `screenshots/refinement/error-boundary-desktop-1440.png`,
`error-boundary-mobile-390.png`, `error-boundary-mobile-390-hindi.png`. They were
captured with a temporary harness that mounted the real `AppLayout` with a
throwing route; the harness was deleted afterwards and the suites above were
re-run on the clean tree.

No backend file, route, label, colour, type scale or navigation was changed, and
the boundary's copy is new text only — no existing string was edited.
