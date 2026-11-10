# UI/UX redesign — what changed and what was verified

> **Superseded in part.** A later presentation-only pass removed the academic
> submission details from the public pages, replaced the machine-readable
> decision labels with sentences, and moved rule ids, retrieval scores, record
> ids and classifier output into a collapsed technical block plus a separate
> `/evaluation` page. Where this document and
> [`UI_REFINEMENT_PRESENTATION.md`](UI_REFINEMENT_PRESENTATION.md) disagree on
> labels, the safety page or test counts, the refinement document is current.
> The layout, palette, typography and navigation described below are unchanged.

Scope: a visual and usability pass over the existing working application. The backend,
the rule engine, the retrieval pipeline and the decision contract are untouched. No
dosage, PHI, REI, PPE value or regulatory approval was invented, and the frontend still
cannot choose a decision class — it renders `POST /rag/answer` verbatim.

Screenshots in `screenshots/redesign/` were captured from the running app (backend on
:8000, Vite on :5173) with Playwright on Edge. The earlier `screenshots/01-*.png` set
documents the pre-redesign interface and is kept only for comparison.

## 1. Information architecture

Four primary destinations — Home, Ask assistant, Knowledge library, Safety guide — with
About moved to the footer and to `/project-info`.

| Route | Page | Note |
|---|---|---|
| `/` | `Home` | new landing page; the old dashboard was retired |
| `/advisory` | `AdvisoryAssistant` | same endpoint and request shape as before |
| `/knowledge-base` | `KnowledgeBase` | search + crop filter over the real 9 records |
| `/safety-guidelines` | `SafetyGuidelines` | plain-language PHI/REI/PPE/label/CIB&RC + live rule registry |
| `/project-info` | `ProjectInfo` | secondary; linked from the footer |
| `/dashboard` | `Home` | kept as an alias so old links resolve |

Navigation: a horizontal bar from 1024px, a fixed four-item bottom bar below that. The
bottom bar keeps all four labels visible — a hamburger would hide four destinations
behind a tap, which is the opposite of what a first-time farmer user needs.

## 2. Design system

Tokens live in `tailwind.config.js`; the palette is the one specified (Forest #214E3D /
#173B2E, Sage #A8B9A1 / #E8EEE5, Ivory #F7F6EF / #F0F0E7, Gold #D9B866, Charcoal #252B27,
Grey #737A73) expressed as single-hue ramps so hover, border and surface variants stay in
the same family.

- Type: Manrope for headings (`font-display`), Inter for body, Noto Sans Devanagari as the
  Hindi fallback. Body copy is 15–16px; `:lang(hi)` raises line-height to 1.75 because
  Devanagari sits lower on its body than Latin at the same metric.
- One panel component (`Card`), one button factory (`buttonClass`), one icon set (inline
  24px outlines, `aria-hidden`). No second visual language for the same job.
- Tap targets: 44px minimum on interactive controls; the language pill and crop chips are
  at least 34px high with 44px-equivalent padding at the edges.
- Colour is never the only signal: every decision class carries a label, an icon, a
  sentence and a `data-decision` attribute; safety fields carry an icon plus the words
  "Not published in source".
- Focus: one `:focus-visible` ring for every interactive element; `prefers-reduced-motion`
  removes transitions.

## 3. Pages

**Home.** Hero ("Better crop decisions start with better information."), the advisory
composer as the centrepiece, a four-item "What you get" panel, a trust strip, live pilot
counts (crops / records / sources / indexed passages) read from the API, a four-step
explanation, and a dark band explaining why nothing here is a dose. Counts are the real
ones; nothing is a marketing statistic.

**Ask assistant.** Question box, language control, examples drawn from real records only.
Result blocks, in order: answer (question, confidence, the backend's own text and
sections) → decision status → missing information → sources → safety data → next steps →
why this decision → retrieved passages → technical detail. Missing safety data and the
decision status are never inside a `<details>`.

**Knowledge library.** Search across crop, pest and ingredient plus crop chips, all over
the nine real records. PHI/REI/PPE are always visible on the card with the source's own
note; interventions and the long verification note are collapsible. Nothing is invented,
and the dataset note states the pilot's size.

**Safety guide.** Five plain-language cards (PHI, REI, PPE, label, CIB&RC), the
"why missing data stops a recommendation" band, then the live rule registry, blocking
precedence and thresholds exactly as `GET /rules/status` returns them.

**About.** Project details, what the system does, and the scope note.

**Bilingual.** Every label, button, error, empty state and safety explanation exists in
English and Hindi. Record identifiers, source titles, dosages and rule text are quoted,
not translated. The interface states that retrieval is lexical, so a Hindi question is
matched against English source text.

## 4. Screenshots (actual, from the running app)

Desktop 1440: `home-desktop-1440.png`, `result-educational-desktop-1440.png`,
`result-refusal-desktop-1440.png`, `result-clarification-desktop-1440.png`,
`result-escalation-desktop-1440.png`, `library-desktop-1440.png`,
`safety-desktop-1440.png`, `about-desktop-1440.png`, `advisory-empty-desktop-1440.png`,
`home-desktop-hindi.png`, `result-hindi-desktop.png`, `safety-desktop-hindi.png`.

Tablet 768: `home-tablet-768.png`, `library-tablet-768.png`, `safety-tablet-768.png`,
`result-educational-tablet-768.png`, `about-tablet-768.png`,
`advisory-empty-tablet-768.png`.

Mobile 390: `home-mobile-390.png`, `result-educational-mobile-390.png`,
`library-mobile-390.png`, `safety-mobile-390.png`, `about-mobile-390.png`, plus
viewport close-ups `view-mobile-home-top.png`, `view-mobile-result-status.png`,
`view-mobile-result-bottom.png`, `view-mobile-library-top.png`.

## 5. Test results

| Check | Result |
|---|---|
| Frontend unit tests (`vitest run`) | 28 passed, 4 files |
| Production build (`tsc -b && vite build`) | pass — JS 252.41 kB (78.08 kB gzip), CSS 31.14 kB (6.45 kB gzip) |
| Backend regression (`pytest -q`) | 443 passed, 71 warnings |
| Phase 9 browser integration (`scripts/phase9_integration_check.py`) | 31/31 passed |
| New responsive sweep (`scripts/redesign_screenshots.py`) | 50 checks, 0 overflow failures |

The responsive sweep measures `document.documentElement.scrollWidth` against the viewport
width for all five routes at 360 / 390 / 430 / 768 / 1024 / 1440 / 1920 px (35
measurements, all equal), and records the functional checks: home composer hands the
question to `/advisory` and the answer arrives, the three nav links route correctly, the
Hindi switch changes the rendered heading and `document.documentElement.lang`.

Decision classes exercised against the live API: `EDUCATIONAL_INFORMATION`,
`SAFETY_REFUSAL`, `CLARIFICATION_REQUIRED`, `ESCALATION_REQUIRED`. `ACTIONABLE_RECOMMENDATION`
and `REGULATORY_VERIFICATION_REQUIRED` cannot be produced by the current knowledge base
(0 of 9 records have a published PHI/REI/PPE profile and the CIB&RC registry is never
queried), so no screenshot or claim is made for them.

## 6. Changed files

New: `src/pages/Home.tsx`, `src/components/AdvisoryComposer.tsx`, `src/components/Nav.tsx`,
`src/components/Button.tsx`, `backend/scripts/redesign_screenshots.py`, this document.

Rewritten: `src/i18n/strings.ts`, `src/layouts/AppLayout.tsx`, `src/pages/AdvisoryAssistant.tsx`,
`src/pages/KnowledgeBase.tsx`, `src/pages/SafetyGuidelines.tsx`, `src/pages/ProjectInfo.tsx`,
`src/components/AdvisoryResult.tsx`, `src/components/DecisionBadge.tsx`,
`src/components/ConfidenceMeter.tsx`, `src/components/Card.tsx`, `src/components/Icon.tsx`,
`src/components/LanguageSwitch.tsx`, `src/App.tsx`, `src/index.css`, `index.html`,
`tailwind.config.js`.

Tests updated for the new copy (labels only, no assertions weakened):
`src/components/DecisionBadge.test.tsx`, `src/i18n/LanguageProvider.test.tsx`.

Removed: `src/pages/Dashboard.tsx`, `src/components/Sidebar.tsx`,
`src/components/StatusBadge.tsx` — superseded by `Home`, `Nav` and the decision badge. The
old dashboard's only unique content (live system status, coverage, workflow) is on the new
Home and Safety pages, served by the same endpoints.

## 7. Decisions worth knowing

- **Decision status sits above the answer text**, before the answer card. The brief's A–E
  order is a reading order for content blocks; a refusal that a farmer only meets after
  700px of scrolling would be a safety problem, so the class is the first thing rendered.
  Everything else follows A→E.
- **Missing information is a first-class card**, not a footnote, and it appears even when
  the answer is otherwise complete.
- **An empty source card is not rendered on a refusal.** "0 sources" adds nothing that the
  decision strip and the reason card have not already said.
- **Confidence is shown with its two inputs** (retrieval and classifier) so a number is
  never presented as a probability of correctness.
- **Home is honest about scope**: five crops, nine records, and every answer currently
  educational.

## 8. Remaining limitations

1. `ACTIONABLE_RECOMMENDATION` and `REGULATORY_VERIFICATION_REQUIRED` remain unreachable
   in the browser because no record has a complete published safety profile and the CIB&RC
   registry is never queried. Their styling is unit-tested, not browser-tested.
2. Retrieval is lexical: a Hindi question is matched against English source text by the
   hash embedder, so recall for Hindi-only phrasing is weaker than for English. The UI says
   so; it does not claim cross-lingual retrieval.
3. The library's crop filter and search run client-side over nine records. That is correct
   at this size and will not be at 900; the endpoint would need paging and a server filter.
4. Screenshots are Chromium/Edge at 1× and 2× DPR. Safari and Firefox are unverified, and
   `env(safe-area-inset-bottom)` padding on the bottom bar is untested on a real notched
   device.
5. Contrast was chosen against WCAG AA for body text, but no automated axe run is included
   in the suite; the accessibility evidence is the focus-ring, label, icon and
   `aria-pressed`/`aria-current` wiring plus manual review.
6. The image is a single licensed stock photograph; there is no art direction per crop.
