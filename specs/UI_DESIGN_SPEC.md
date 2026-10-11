# RuleSight UI design spec

**Owner:** Vaidehi (frontend) · **Status:** ready to build · **Applies to:** `frontend/` (React 19, Vite, TypeScript, Tailwind 4, shadcn/ui new-york, TanStack Query, Recharts, Zod)

**Sources this spec is built from:**
- `backend/TEAM_PLAN_ONE_NIGHT.md`. Sections 2, 3, 5, 6, 7, 8 and 11 are the contract.
- `backend/demo_data/` (README, both answer keys, `expected_mappings_RBI.csv`, the RCM, EVD-02/06/07)
- The current frontend scaffold (`src/styles/index.css`, `src/lib/navigation.ts`, `components/layout/*`)

---

## 0. How to use this file with Claude Code

Paste this into Claude Code from the `RuleSight/` workspace root:

> Read `backend/specs/UI_DESIGN_SPEC.md` in full, then `backend/TEAM_PLAN_ONE_NIGHT.md` §5, then the demo data it points to. Build the frontend in `frontend/` exactly to this spec, in the order of §14. Use mock mode (`VITE_USE_MOCKS=true`) with fixtures built from `backend/demo_data/` as described in §12. Copy regulation quotes **verbatim** from the files in `backend/demo_data/1_regulations_rbi/`; never paraphrase into a quote field. Do not add colours, fonts or chart types that this spec does not define. After each screen, run `npm run lint`, `npm run typecheck` and `npm test`, then check the screen in both light and dark themes.

Build one screen at a time. Section 15 is the acceptance checklist.

---

## 1. What we are designing

RuleSight reads **real RBI regulations**, extracts obligations, maps them to a bank's controls, finds gaps, scores risk and drafts remediation. A human approves each step. The bank, **Nova Trust Bank Ltd., is fictional**.

**Who uses it** (there is no auth; the header has an "Acting as" dropdown that sets `X-Actor`):
- **Priya Sharma, Compliance Officer.** Approves gaps and remediation. Cares about P1 items, deadlines and the audit trail.
- **Rahul Mehta, Analyst.** Reviews extracted obligations and mappings. Accepts, edits or rejects them. Works in tables all day.

**What the demo must make obvious** (from plan §11):
1. Every finding traces back to a **verbatim RBI clause**. The Gap Trace page is the "money screen".
2. The system **abstains**: it says "Insufficient evidence" and "Not in corpus", and never guesses "compliant".
3. **Change intelligence:** NSM v2 (2 Oct 2026) supersedes v1. v1 is marked withdrawn, the 30 June 2027 phase-out appears, 7 discontinued machines become P1 gap NG-03, and the system warns that the 24 Apr 2025 circular is missing from the corpus.
4. **Measured accuracy** on an Accuracy panel, scored against the answer key.

**The feel:** a well-made internal tool at a serious bank, or a regulatory publisher's reader. Think of the quiet confidence of a law report, a central-bank publication or a well-typeset annual report. It should not look like a startup landing page or an AI demo.

---

## 2. Design principles and the "not made by AI" rules

### Principles
1. **The document is the hero.** Regulation text is set like print: serif, generous measure, clause numbers in the margin. Everything else supports it.
2. **Density with calm.** Compliance people scan tables. Use compact rows, hairline rules, aligned numbers and few boxes.
3. **Show the reasoning.** Each conclusion shows its chain (clause → obligation → control → evidence → gap) and the factors behind the score. Never show a bare verdict.
4. **Honest states are first-class.** "Insufficient evidence", "Not applicable", "Needs review" and "Not in corpus" get the same design care as "Covered".
5. **One accent, used sparingly.** Plum is the brand. Rose ash is for highlight and selection only. Most of the screen is ink on parchment.

### Do
- Left-aligned layouts with a clear reading line. Use a 12-column grid, but let the content set the widths.
- Hairline rules (1px) to separate. Prefer **rules over cards**: a page is a sheet with sections, not a pile of floating tiles.
- Small radius: **4px** on controls and **6px** on panels. Badges get 3px. Pills (fully round) only for the actor avatar.
- Real, specific microcopy: "18.4% of High-risk re-KYC overdue (EVD-02)", not "Issue detected".
- Tabular figures for every number. Right-align numeric columns.
- Small-caps-style eyebrow labels for sections (uppercase, 11px, letter-spacing 0.06em, muted ink).
- Section numbering in the trace (§1 Clause, §2 Obligation, …), echoing how regulations are numbered.
- Restrained icons: `lucide-react`, 16px, stroke 1.5, only where they add meaning (status, actions). Never decorate headings with them.

### Don't (each of these reads as "AI-generated")
- No gradients, glassmorphism, glows, blurred blobs, mesh backgrounds or gradient text.
- No sparkles ✨, robot or brain icons, "AI-powered" badges or "magic" wording. The agent is a colleague, not a wizard. Say "Extracted by agent", not "AI magic".
- No emoji anywhere in the UI.
- No large rounded cards with heavy shadows on every element, and no "bento grid" dashboards.
- No blue or indigo-violet primary (the default Tailwind and shadcn look). Never use `blue-*`, `indigo-*`, `violet-*`, `slate-*` or `gray-*` utilities. Use only the tokens in §3.
- No centred hero headings, no "Welcome back, Priya!", no oversized greeting text.
- No percentage confidence scores ("92% confident"). The plan forbids fake probabilities. Show the **graph path** and **critic pass/fail** instead.
- No donut or pie charts, gauges, 3D or radial progress rings. No dual-axis charts.
- No skeleton shimmer animations sweeping across the whole page (see §6 Motion).
- No Inter, Geist or Poppins (the default "AI app" fonts).

---

## 3. Colour system

### 3.1 Where the palette comes from
Two Color Hunt palettes are blended into one system:

| Source | Hex | Role in RuleSight |
|---|---|---|
| Palette A ([5749649f8383c8aaaaffdab3](https://colorhunt.co/palette/5749649f8383c8aaaaffdab3)) | `#574964` aubergine | **Primary brand**: nav active state, primary buttons, links, focus |
| | `#9F8383` dusty mauve | Tertiary ink, P3 tone, secondary chart rules |
| | `#C8AAAA` rose ash | **Highlight** (light theme): selection, highlighted quote span, graph focus halo. Also borders on tags and the dark-theme P3 tone. |
| Palette B ([ffeac5ffdbb56c4e31603f26](https://colorhunt.co/palette/ffeac5ffdbb56c4e31603f26)) | `#FFEAC5` cream | Parchment base (lightened), dark-theme ink on highlight, graph and wordmark rule |
| | `#603F26` dark coffee | **Accent**: document and source metadata, secondary buttons, quote rule (light theme) |

The result, **"Aubergine & Parchment"**, looks like plum ink on warm paper. It reads as finance and print, not as SaaS blue.

All the contrast ratios below were computed (WCAG 2.x), not estimated.

### 3.2 Theme tokens (replace `frontend/src/styles/index.css` tokens with these)

| Token | Light | Dark | Use | Contrast check |
|---|---|---|---|---|
| `--background` | `#FAF5EE` | `#17121C` | Page (parchment / aubergine-black) | |
| `--card` | `#FFFDF9` | `#201927` | Sheets, tables, panels | |
| `--sunken` | `#F3EADF` | `#140F18` | Table header, code/quote wells, sidebar | |
| `--raised` | `#FFFFFF` | `#2A2232` | Popovers, dropdowns, drawer | |
| `--foreground` | `#2B2130` | `#F3E9DF` | Body ink | 15.2 : 1 / 14.3 : 1 on card |
| `--muted-foreground` | `#6B5A66` | `#B3A3AD` | Secondary text, labels | 5.9 : 1 / 7.1 : 1 |
| `--border` | `#E8DCCF` | `#352B3D` | Hairline rules (decorative) | |
| `--input` | `#94806F` | `#7A6A85` | Form-control borders | ≥ 3.4 : 1 (WCAG 1.4.11) |
| `--primary` | `#574964` | `#C9B6D9` | Brand plum | 7.6 : 1 / 9.1 : 1 |
| `--primary-hover` | `#463A51` | `#DACBE6` | | |
| `--primary-foreground` | `#FFFDF9` | `#17121C` | Text on primary | 8.1 : 1 / 9.8 : 1 |
| `--primary-tint` | `#EDE6F0` | `#2E2538` | Active nav row, selected chip | |
| `--accent` | `#603F26` | `#C8AAAA` | Source/document accent, secondary button text | 9.2 : 1 / 8.0 : 1 |
| `--accent-strong` | `#9F8383` | `#9F8383` | Quote rule, hover | |
| `--highlight` | `#C8AAAA` | `#574964` | Selection bg, highlighted quote span | ink on rose ash 7.2 : 1 / cream on plum 7.0 : 1 |
| `--highlight-foreground` | `#2B2130` | `#FFEAC5` | Text on highlight | |
| `--ring` | `#574964` | `#FFEAC5` | Focus ring (2px + 2px offset) | |

**Status tokens.** These are reserved for state and always ship with an icon and a text label.

| Token | Light fg / tint bg | Dark fg / tint bg | Meaning |
|---|---|---|---|
| `--critical` | `#A33A2C` / `#F8E4DF` | `#EE8A78` / `#3A1F1D` | P1, failed, rejected, ineffective, deleted |
| `--warning` | `#8F5A0A` / `#F8EBD3` | `#E3B05A` / `#38291A` | P2, partial, partially effective, modified, needs review |
| `--success` | `#3F6E46` / `#E3EEE0` | `#93C48F` / `#1C2B1F` | Covered, adequate, effective, verified, added, critic passed |
| `--neutral-status` | `#7E6464` / `#F1E8E6` | `#C8AAAA` / `#2C2329` | P3, insufficient info, insufficient evidence, not applicable, draft |

Light-theme status text on its tint is ≥ 4.9 : 1. Dark-theme status text on the card is ≥ 6.9 : 1.

**Theme switching.** This keeps the scaffold's mechanism. Light is the default when the OS has no preference. The `prefers-color-scheme: dark` block is guarded by `:root:not([data-theme="light"])`, and `:root[data-theme="dark"]` repeats the dark values. Add a three-state **theme control** in the header: *System / Light / Dark* (icons `Monitor`, `Sun`, `Moon`). It sets or removes `data-theme` on `<html>` and saves the choice in `localStorage` (inside `try/catch`, since storage can throw). Run an inline script in `index.html` before first paint to avoid a flash. Dark theme is **designed, not inverted**: surfaces step up in lightness as they rise (background → card → raised).

### 3.3 Domain colour mapping (use exactly these)

| Concept | Value → token |
|---|---|
| Priority | P1 → critical · P2 → warning · P3 → neutral-status |
| Gap status | potential → warning outline · confirmed → critical solid tint · dismissed → neutral, struck label · needs_info → neutral-status |
| Coverage | covered → success · partial → warning · none (missing) → critical · insufficient_info → neutral-status |
| Design assessment | adequate → success · inadequate → critical · unknown → neutral-status |
| Operating assessment | effective → success · partially_effective → warning · ineffective → critical · insufficient_evidence → neutral-status, with the label **"Insufficient evidence"** and an `EyeOff` icon |
| Applicability | applicable → primary tint · not_applicable → neutral-status, with the reason shown inline · unknown → warning outline |
| Review status | suggested → primary outline ("Suggested by agent") · accepted → success · edited → accent (dark coffee) · rejected → critical · needs_review → warning |
| Remediation | draft → neutral · approved → primary · in_progress → warning · completed → success outline · verified → success solid · rejected → critical |
| Change type | added → success (`+`) · deleted → critical (`−`) · modified → warning (`~`) · withdrawn → critical outline · carried-over/consolidated → neutral · corpus-gap warning → warning with `FileQuestion` icon |
| Document status | uploaded → neutral · processing → primary with a spinner · ready → success · failed → critical · superseded → neutral, struck version label |
| Synthetic marker | Bank documents (`is_synthetic = true`) carry a small accent-outlined tag **"Fictional bank"**. RBI documents carry **"RBI · Real text"** in plum outline. |

### 3.4 Chart colours (validated with the dataviz palette validator, both themes)

**Categorical: 5 slots in fixed order, never cycled.** Use these only for entity *identity* (knowledge-graph node types, legend series), never for status.

| Slot | Entity (graph) | Light | Dark |
|---|---|---|---|
| 1 | Clause / regulation | `#6B4E8C` plum | `#9A7BD3` |
| 2 | Obligation | `#C9692F` terracotta | `#D5733A` |
| 3 | Control | `#0083A0` deep teal | `#0096A8` |
| 4 | Evidence | `#B8862A` ochre | `#B8892A` |
| 5 | Gap | `#B4527A` rose | `#CF6C96` |

Validator results: lightness band, chroma floor, adjacent CVD separation (worst ΔE 14.4 light / 12.3 dark), normal-vision floor and ≥ 3:1 contrast against the card all **pass**. Remediation and change nodes use the neutral ink with a distinct shape (see §8.8) rather than a 6th hue.

**Sequential: one hue (plum), low → high.** Use it for magnitude, coverage composition, the risk heatmap and remediation progress.

| Step | Light | Dark |
|---|---|---|
| 1 (low) | `#BFA8D2` | `#5E4B78` |
| 2 | `#9F84BC` | `#7A639B` |
| 3 | `#7E62A0` | `#9880BC` |
| 4 | `#604783` | `#B7A2D8` |
| 5 (high) | `#432F5E` | `#D8CAEC` |

The ordinal check passes: monotone lightness, ΔL ≥ 0.06 between steps, and the light end clears the surface.

**Chart text** always uses `--foreground` or `--muted-foreground`, never the series colour. Gridlines use `--border`. Axis lines are hidden except for the baseline.

**Status vs categorical:** ochre (slot 4) and the warning tone are related hues, and terracotta (slot 2) and critical are too. Never put them in the same chart. Status marks always carry an icon and a label.

---

## 4. Typography

The pairing is a serif for regulatory text and headings, a humanist grotesque for the UI, and a mono for references. It reads as "bank document", not "AI app".

| Role | Font | Package (self-host; no Google CDN in a bank tool) |
|---|---|---|
| Display and regulation text | **Source Serif 4** (variable, opsz) | `@fontsource-variable/source-serif-4` |
| UI, tables, body | **IBM Plex Sans** 400/500/600 | `@fontsource/ibm-plex-sans` |
| Clause refs, IDs, hashes, numbers in code wells | **IBM Plex Mono** 400/500 | `@fontsource/ibm-plex-mono` |

Tailwind theme: `--font-serif: "Source Serif 4 Variable", Georgia, serif; --font-sans: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; --font-mono: "IBM Plex Mono", ui-monospace, monospace;`. Set `font-variant-numeric: tabular-nums` on `body`, and `lining-nums` on the serif.

**Scale** (rem at a 16px root; UI base is 14px):

| Token | Size / line-height | Font | Use |
|---|---|---|---|
| `display` | 30 / 36, weight 600, tracking −0.01em | Serif | Page title (one per page) |
| `h2` | 20 / 28, weight 600 | Serif | Section titles |
| `h3` | 15 / 22, weight 600 | Sans | Panel and table titles |
| `body` | 14 / 22 | Sans | Default UI |
| `reading` | 16 / 27, max 68ch | Serif | Regulation and policy quotes, trace clause text |
| `small` | 13 / 20 | Sans | Table cells, meta |
| `eyebrow` | 11 / 16, weight 600, uppercase, tracking 0.06em | Sans | Section labels |
| `kpi` | 32 / 36, weight 500, tabular | Sans | KPI numbers (sans, not serif, for crisp digits) |
| `mono` | 12.5 / 20 | Mono | `OB-07`, `para 38`, `CTL-05`, `EVD-02`, run IDs |

IDs such as `G-07`, `CTL-19` and `para 8.2` are always mono, in `--muted-foreground`, and can be copied (a click copies with a 1.2s "Copied" tooltip).

---

## 5. Layout, spacing, surfaces

- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48. Page gutter is 32px desktop, 16px mobile. Content max width is 1440px; reading columns are max 68ch.
- **Shell:** a left **sidebar of 232px** (collapsible to 64px icon rail, on `--sunken`) with a **top bar of 56px** (on `--card`, bottom hairline).
- **Surfaces:** pages sit on `--background`. Primary content goes in "sheets" (`--card`, 1px `--border`, 6px radius, **no shadow**). Only popovers, drawer and dialogs get a shadow: light `0 8px 24px -8px rgb(43 33 48 / 0.18)`, dark `0 8px 24px -8px rgb(0 0 0 / 0.5)`.
- **Tables** are the default container for lists. Header on `--sunken`, eyebrow-style labels, 40px rows (32px "compact" toggle), hairline row dividers, hover row in `--primary-tint`, selected row with a 2px plum left bar plus `--highlight` at 40% opacity.
- **Breakpoints:** ≥ 1280 full layout · 1024–1279 sidebar collapses to rail · < 1024 sidebar becomes a drawer, and tables switch to stacked rows with the key fields. Never scroll the page horizontally; wide tables scroll inside their own container with a sticky first column.

---

## 6. Motion

- 120ms ease-out for hover and focus. 180ms for drawers and popovers (slide 8px + fade). No bounces.
- Loading: a static `--sunken` block with a soft opacity pulse (1.6s), per component, never a sweeping shimmer.
- Pipeline progress is the only animated "live" element: the active node's dot pulses, and the timeline bar grows.
- Respect `prefers-reduced-motion`: disable the pulse and slide, and keep the fades.

---

## 7. App shell and shared components

### 7.1 Shell

```
┌──────────────┬──────────────────────────────────────────────────────────────────────┐
│ ▣ RuleSight  │  Gaps / G-07                                [Mock data]  ◐ Theme  ⌄ │
│              │                                      Acting as: (PS) Priya Sharma ▾ │
│ OVERVIEW     ├──────────────────────────────────────────────────────────────────────┤
│  Dashboard   │                                                                      │
│ LIBRARY      │   page content                                                       │
│  Documents   │                                                                      │
│  Changes     │                                                                      │
│ ANALYSIS     │                                                                      │
│  Obligations │                                                                      │
│  Controls    │                                                                      │
│  Gaps     12 │                                                                      │
│  Remediation │                                                                      │
│ SYSTEM       │                                                                      │
│  Graph       │                                                                      │
│  Agent runs  │                                                                      │
│  Audit log   │                                                                      │
│ ──────────── │                                                                      │
│ Nova Trust   │                                                                      │
│ Bank (fict.) │                                                                      │
│ RBI corpus·3 │                                                                      │
└──────────────┴──────────────────────────────────────────────────────────────────────┘
```

- **Wordmark:** "RuleSight" in Source Serif 4, 18px, weight 600, `--foreground`. Before it, a 16px mark: a plum square with a cream horizontal rule through it (like a highlighted line in a document). Draw it as inline SVG; no icon library.
- **Nav** replaces `NAV_ITEMS` in `src/lib/navigation.ts`, grouped under eyebrow labels as drawn above. Routes: `/`, `/documents`, `/changes`, `/obligations`, `/controls`, `/gaps`, `/gaps/:id`, `/remediation`, `/graph`, `/runs`, `/runs/:id`, `/audit`. Drop the scaffold's Regulations, Evidence, Assessments and Findings routes: those are shown inside Documents, Controls and the Gap Trace. Active item: `--primary-tint` background, plum text, 2px plum left bar. The Gaps item shows the open-P1 count as a small critical-tint badge.
- **Sidebar footer:** the tenant ("Nova Trust Bank · Fictional") and the corpus ("RBI corpus · 3 documents"). This is the honesty reminder.
- **Top bar:** breadcrumb (sans 13px, muted, last item in ink), then on the right: a **Mock data** tag (warning outline, only when `VITE_USE_MOCKS=true`), the theme control, and the **Acting as** select.
- **Acting as:** a select with the initials avatar (plum-tint circle, mono initials) and the name and role: *Priya Sharma, Compliance Officer* / *Rahul Mehta, Analyst*. It sets the `X-Actor` header on every request through the API client, and persists in `localStorage`. Changing it shows a toast ("Now acting as Rahul Mehta. New actions are recorded under this name.").

### 7.2 Components (build on shadcn new-york, restyled to the tokens)

| Component | Spec |
|---|---|
| **Button** | Heights 32/36. *Primary:* plum fill. *Secondary:* card fill, `--input` border, ink text. *Accent:* accent text, accent border (document actions). *Ghost:* text only. *Danger:* critical text and border, filled only in the confirm dialog. 4px radius, weight 500. Label is a verb ("Approve remediation", not "Submit"). |
| **Badge / Tag** | 20px tall, 3px radius, 12px weight 500, tint background with status text, a 12px icon on the left. Variants follow §3.3. Never colour-only. |
| **Priority chip** | Mono text "P1" in a 24×20 box: critical tint + critical text + a 2px left bar of critical. P2 warning, P3 neutral. |
| **Quote block** | The signature element. `--sunken` well, 3px left rule in `--accent-strong`, serif `reading` text, an opening "“" hanging in the margin in the accent colour at 28px. Footer line in mono small: `RBI KYC Master Direction 2016 · para 38 · p. 23` plus a **Verbatim ✓** tag (success) when the critic verified it is an exact substring, or **Quote not verified** (warning) otherwise. Highlighted spans (the words that matter, e.g. "once in every two years") use `--highlight` with 2px padding and no rounded pill. |
| **ID link** | Mono, muted, dotted underline. Hover shows a popover with the entity summary. |
| **KPI tile** | No box: a cell in a ruled row of 4. Eyebrow label, `kpi` number, one context line in `small` muted ("18 applicable · 1 not applicable"). An optional inline breakdown (P1 · P2 · P3 chips). Clicking goes to the filtered list. |
| **Filter bar** | One row above each table: search (with `/` shortcut), then segmented filters (Priority, Type, Status), "Clear all", and a result count on the right ("12 gaps"). Filters live in the URL query. |
| **Drawer** | Right side, 520px, `--raised`. Used for obligation and mapping detail, document detail and run detail. Esc closes it and focus returns to the row. |
| **Graph path** | Replaces any "confidence". A horizontal chain of small nodes: `OB-07 → topic: Periodic KYC ← CTL-05`, with categorical dots for the node types, plus a **Critic: passed / retried / failed** tag. |
| **Confirm dialog** | Used for approve, reject and dismiss. Shows the actor ("This will be recorded as Priya Sharma, Compliance Officer") and a required reason field for reject or dismiss. |
| **Toasts** | Bottom-right, `--raised`, 4s, with an Undo link where the API allows. |
| **States** | Every data view has all four: *Loading* (pulse blocks shaped like the content), *Empty* (one serif sentence and one action, e.g. "No gaps yet. Run the pipeline after uploading a regulation and the RCM." [Go to Documents]), *Error* (critical outline sheet: what failed, the error envelope message, Retry), and *Partial* (inline warning when some items need review). The scaffold's `components/feedback/*` should be restyled, not replaced. |

---

## 8. Screens

The endpoints are those in plan §5. Each page has a `display` title (serif) and a one-line `small` muted subtitle stating the scope. Example: "Nova Trust Bank against 3 RBI documents · last pipeline run 11 Oct 2026, 14:02".

### 8.1 Dashboard (`/`)

Purpose: answer "how exposed are we, and how far can we trust the numbers?" in about 10 seconds.

Data: `/dashboard/summary` (if available) or composed from `/obligations`, `/mappings`, `/gaps`, `/remediations` (via gaps), `/eval/latest`, and the latest `/pipeline/runs`.

```
Compliance overview                                    [Run pipeline]  [Upload document]
Nova Trust Bank (fictional) · RBI KYC MD 2016, NSM Master Direction 2026 · run 14:02

OBLIGATIONS        COVERAGE              OPEN GAPS                 REMEDIATION
19                 7 / 18 covered        12                        2 approved
18 applicable ·    39% of applicable     [P1 3] [P2 7] [P3 2]      of 12 drafted
1 not applicable
─────────────────────────────────────────────────────────────────────────────────────
Coverage of applicable obligations (100% bar, sequential plum + labels)
████████████████▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░    covered 7 · partial 7 · insufficient 2 · missing 3

┌ Top risks ──────────────────────────────┐  ┌ Gaps by type × priority ─────────────┐
│ P1 G-07 Re-KYC High risk every 2 yrs  6 │  │ Design            ███▒▒▒▒ 6          │
│ P1 NG-03 Phase out 7 NSMs by 30 Jun 27 9│  │ Design + operating ██ 2              │
│ P1 NG-01 Quarterly NSM testing        6 │  │ Missing            █▒ 2              │
│ P2 G-01  Beneficial owner >10%        4 │  │ Insufficient info  ░░ 2              │
│ … view all 12 gaps →                    │  └──────────────────────────────────────┘
└─────────────────────────────────────────┘
┌ Risk matrix (criticality × severity) ───┐  ┌ Accuracy against answer key ─────────┐
│ heatmap, count per cell                 │  │ Obligation recall      ████████▏ 0.89│
└─────────────────────────────────────────┘  │ Obligation precision   …             │
┌ Recent agent runs ──────────────────────┐  │ Mapping accuracy       …             │
│ run 7f3a · 11 nodes · 84 LLM calls ·    │  │ Gap recall · Gap type accuracy       │
│ 0 errors · 2m 41s           [view →]    │  │ Change detection · Citation validity │
└─────────────────────────────────────────┘  │ Scored by scripts/evaluate.py · time │
                                             └──────────────────────────────────────┘
```

- **Top risks** is a compact table: priority chip, gap ID, one-line description, **risk score** (right-aligned, tabular), and a "from change" tag when `origin = change` (NG-03).
- **Accuracy panel:** one bar per metric on a shared 0–1 axis (sequential step 4), with the value as a direct label. No targets are invented. The footer names the method ("Measured against `3_answer_key/` · 19 obligations, 12 gaps") and the timestamp. If `/eval/latest` is empty, show "Not scored yet. Run `scripts/evaluate.py`." **Never hardcode these numbers.** In mock mode the panel shows the Mock tag.
- Numbers in the wireframes are illustrative. **Compute every figure from the data; never hardcode.** For reference, `expected_mappings_RBI.csv` gives: covered 7 (OB-08, OB-09, N-01–N-04, N-08), partial 7 (OB-01, OB-04, OB-06, OB-07, N-05, N-06, NSM-SCOPE), insufficient info 2 (OB-02, OB-05), missing 3 (OB-03, OB-10, N-07), not applicable 1 (OB-11). The answer key counts 19 obligations and treats the NSM para 3 scope row separately, so decide with Anand whether NSM-SCOPE counts in the coverage denominator, and label the tile accordingly.

### 8.2 Documents (`/documents`)

Purpose: upload, see each document's state, and watch the pipeline.

- **Header actions:** `[Upload document]` (primary) and `[Run pipeline]` (secondary).
- **Table columns:** Title (serif 15px) with a **RBI · Real text** or **Fictional bank** tag · Type (Regulation / Policy / RCM / Evidence) · Version (mono, e.g. `v2 · 2 Oct 2026`) · Supersedes (link) · Status badge · Added. Group rows by type, with group headers as eyebrow rows.
- **Version chain:** NSM v1 and v2 show as a linked pair. v1's version label is struck through, with a critical-outline **Withdrawn 2 Oct 2026** tag. Hover explains: "Withdrawn by RBI Master Direction DCM(NPD) No.S2154/18.00.014/2026-27, Annex row 4".
- **Upload dialog** (react-hook-form + Zod): a dropzone (dashed `--input` border, serif prompt "Drop a PDF, Markdown, text or CSV file"), then *Document type* (segmented), *Title*, *Regulator* (default RBI for regulations), *Version label*, *Supersedes* (select listing documents of the same type) and the 10 MB limit. Client-side validation for type and size, plus server errors inline. After upload, the row appears with **Processing**.
- **Live pipeline panel:** opens below the header when a run is active (poll `/pipeline/runs/{run_id}` every 1.5s, stop when done). It is a **vertical step list** of the LangGraph nodes in order: extract_obligations → check_applicability → extract_controls → map → critic → assess_evidence → detect_gaps → score_risk → draft_remediation → (diff_versions → impact when the document supersedes another). Each row shows a status icon (queued ○ / running ● pulsing plum / done ✓ success / retried ↻ warning / failed ✕ critical), node name (mono), duration, and LLM calls. The conditional change branch is indented with a "Triggered because NSM v2 supersedes v1" note. That note tells the agentic story without saying "AI".
- **Document drawer:** metadata, sha256 (mono, truncated, copyable), chunk count, extracted obligation count, and the first chunks shown with their `clause_ref` in the margin.

### 8.3 Obligations (`/obligations`)

Purpose: Rahul reviews what the agent extracted, **side by side with the source**.

- **Filters:** Document, Applicability, Review status, Topic, and search.
- **Layout:** a split view. On the left, a 55% table: `code` (mono) · clause ref (mono) · obligation (actor + action, 2 lines) · topic · frequency/deadline · criticality (1–3 shown as ▮▮▯) · applicability badge · review status. On the right, a 45% sticky **source panel** for the selected row: a quote block with the verbatim `source_quote`, then structured fields as a definition list (Actor, Action, Condition, Frequency, Deadline, Threshold). Each field reads "Not specified" in muted italic when empty; never leave a field blank.
- **Not applicable:** OB-11 (para 68, co-operative bank at-par cheques) shows a **Not applicable** badge, and the reason ("Nova Trust is a commercial bank") appears inline under the row, not hidden in a tooltip. This is a demo beat.
- **Actions** in the source panel: `[Accept]` (primary), `[Edit]` (secondary; inline form that turns the fields into inputs; saving sets status **Edited**, in the accent colour), `[Reject]` (danger ghost; requires a reason). Keyboard: `j`/`k` move between rows, `a` accept, `e` edit, `r` reject. A small hint bar at the bottom shows the shortcuts.
- **Bulk:** checkbox column, then "Accept 6 selected".

### 8.4 Controls and mappings (`/controls`)

- Table of controls from the RCM and policies: `CTL-xx` · name · owner · frequency · type (Preventive/Detective) · automation · source (`POL-01 §2`) · RBI reference (mono) · mapped obligations count.
- Selecting a control opens a drawer with its description (serif), source quote, mapped obligations, and for each mapping: coverage badge, **graph path**, critic tag, rationale (serif small), and `[Accept] [Reject]` (PATCH `/mappings/{id}`).
- A **Mappings** tab gives an obligation × control matrix: rows are obligations, columns are controls, and each cell carries a coverage glyph (● covered, ◐ partial, ○ none, ? insufficient) in the status colour. Glyph and colour are always shown together.

### 8.5 Gaps (`/gaps`)

- **Filters:** Priority (P1/P2/P3), Type, Status, Origin (Initial / From change), Regulation.
- **Table**, sorted by `risk_score` descending: Priority chip · Gap ID (mono) · obligation summary · regulation + para (mono) · gap type tag · controls involved (ID links) · risk score (bold, tabular) · status · remediation status. Example rows: NG-03 (9, P1, Missing, *From change*), G-07 (6, P1, Design + operating), NG-01 (6, P1, Design + operating).
- **Risk score cell:** hovering shows the factors: `criticality 2 × severity 3 × urgency 1.5 = 9 → P1 (rule v1)`.
- Clicking a row opens the Gap Trace.

### 8.6 Gap Trace (`/gaps/:id`), the money screen

Data: `GET /gaps/{id}/trace` → `{regulation, clause, source_quote, obligation, controls[], assessment, evidence[], gap, risk_factors, remediations[], audit[]}`.

**Layout:** a two-column page. The main column (max 760px) holds the **numbered vertical trace**. A right rail (320px, sticky) holds the **verdict and actions**.

```
Gaps / G-07
G-07 · Re-KYC for High-risk customers runs on a 3-year cycle; RBI requires 2
[P1] [Design + operating] [Potential]                 RBI KYC Master Direction 2016 · para 38

 ┃ §1  REGULATION CLAUSE                                         ┌ VERDICT ─────────────────┐
 ┃     RBI KYC Master Direction 2016 (updated 14 Aug 2025)       │ Risk score            6  │
 ┃     “ …periodic updation … at least once in every two years   │ criticality 2 (CDD)      │
 ┃       for high risk customers… ”     [Verbatim ✓]  para 38    │ × severity 3 (des+op)    │
 ●     ─────────────────────────────                             │ × urgency 1.0 (initial)  │
 ┃ §2  OBLIGATION  OB-07                                         │ = 6 → P1     rule v1     │
 ┃     Bank must · update KYC · High risk every 2 yrs, Medium 8, │──────────────────────────│
 ┃     Low 10.   Applicable · Accepted by Rahul Mehta            │ Status: Potential        │
 ●     ─────────────────────────────                             │ [Confirm gap]            │
 ┃ §3  CONTROL  CTL-05 Periodic KYC updation                     │ [Needs info] [Dismiss]   │
 ┃     Compliance – KYC Unit · Monthly · Semi-automated          │──────────────────────────│
 ┃     “Re-KYC every 3 years (High)…”  POL-01 §2                  │ Acting as Priya Sharma   │
 ┃     Path: OB-07 → topic Periodic KYC ← CTL-05 · Critic passed  └──────────────────────────┘
 ●     ─────────────────────────────
 ┃ §4  EVIDENCE  EVD-02 Periodic KYC Update Status, Q2 FY2025-26
 ┃     mini-table: High · cycle 3 vs RBI 2 · due 1,240 · overdue 228 (18.4%) · 2,105 not on due list
 ●     ─────────────────────────────
 ┃ §5  ASSESSMENT    Design: Inadequate ✕   Operating: Partially effective ~
 ┃     rationale (serif), cited quotes as small quote blocks
 ●     ─────────────────────────────
 ┃ §6  GAP  Design + operating — why, in one paragraph
 ●     ─────────────────────────────
 ┃ §7  REMEDIATION  draft by agent
 ┃     Action · Owner team · Target 30 days · Closure evidence
 ┃     [Approve remediation] [Edit] [Reject]
 ●     ─────────────────────────────
 ┃ §8  AUDIT HISTORY
 ┃     11 Oct 14:02  agent       created gap (origin initial)
 ┃     11 Oct 14:20  Rahul Mehta accepted OB-07
 ┃     11 Oct 14:31  Priya Sharma approved remediation  (before → after diff)
```

- **The spine:** a 2px vertical line in `--border`, with a 10px node per section coloured by **entity categorical slot** (clause = plum, obligation = terracotta, control = teal, evidence = ochre, gap = rose). The spine therefore uses the same colours as the Graph view, which visually ties the two together. Section numbers `§1`–`§8` are mono and muted; section titles are eyebrows.
- **§1 Clause** uses the full quote block in `reading` size with the key phrase highlighted in the highlight colour. This is the most beautiful element on the page.
- **§4 Evidence** shows the relevant CSV rows as a small table, with the offending cells highlighted (critical tint) and the source file name in mono. With no evidence, show a neutral sheet: "No evidence supplied for this control. Operating effectiveness: **Insufficient evidence**. RuleSight does not assume compliance."
- **Multiple controls** (or none, for Missing gaps like NG-03): §3 lists each one. With none, show "No control in the RCM or policies covers this obligation" and the graph path search that found nothing (`kg_orphans`).
- **Right rail:** the risk formula reads as a ledger with right-aligned factors and the total. The actions write audit entries. The confirm dialog names the actor. After approval, an optimistic update applies, a toast confirms it, and the new audit row slides into §8.
- `[View in graph]` link → `/graph?focus=gap:G-07`.
- **Change-origin gaps** (NG-03) get an accent-outlined banner above §1: "Introduced by a regulatory change: NSM Master Direction 2 Oct 2026 supersedes the circular of 30 Oct 2024. Urgency ×1.5." It links to Changes.
- **Print:** a print stylesheet renders the trace as a clean A4 document (no sidebar, serif, black ink). This is useful for audit packs, and it shows care.

### 8.7 Changes (`/changes`)

Purpose: the highlight demo, NSM v1 → v2.

- **Header:** two selects, *Earlier version* and *Later version* (prefilled to the supersedes pair), then `[Compare]` (POST `/changes/compare`).
- **Summary strip** (ruled KPI row): Modified 1 · Withdrawn 1 · Consolidated (carried over) 6 · Corpus-gap warnings 1 · New gaps 1 (NG-03, P1).
- **Corpus-gap warning**, shown prominently and in honest tone: a warning-outlined sheet with a `FileQuestion` icon. "The v2 Annex withdraws 5 circulars. Only 1 is in the corpus. Not ingested: 2009, 2010 and 2022 circulars, and **24 Apr 2025 'Revised Timeline for Implementation'**. Timeline history may be incomplete. RuleSight has not inferred their content." Below it, a `[Upload missing circular]` accent button.
- **Change list (obligation level, mode b):** each change is a row-card with a type tag (Modified / Withdrawn / Consolidated) and a two-column **before | after** comparison. The before column carries v1's clause in a quote block (struck-through phrases in a critical underline). The after column carries v2's para 8.2 (added phrases highlighted in success tint with a `+` marker in the margin). Significance tag (High / Medium / Low / Administrative). **Impact** footer: affected obligations, controls and new gaps as ID links.
- **Consolidated items** (N-01 to N-06) are collapsed into a single row: "6 requirements carried over from DCM(NPD) No.S488 dated 01.07.2022 (not in corpus). Not new." Expand it to see the list. The UI must never label these "New".
- **Clause diff mode (mode a,** for same-structure pairs): a classic side-by-side diff with clause refs in the gutter. Added lines on a success tint with `+`, deleted on a critical tint with `−`, modified on a warning tint with `~`, and word-level highlights inside. Whitespace-only changes are hidden behind a toggle. Do not rely on colour alone: the gutter symbols are always shown.

### 8.8 Knowledge graph (`/graph`), optional (build last)

- Data: `GET /graph?focus=gap:ID`.
- **Layout: deterministic layered columns, not a force simulation.** Columns are Clause → Obligation → Control → Evidence → Gap → Remediation. Nodes sit in their type's column, ordered to minimise crossings (sort by connected IDs). Use `@xyflow/react` for rendering and pan/zoom, with positions computed by a simple column layout. This reads like a ledger, not a hairball, and it renders the same way every time.
- **Nodes:** 160×36 rounded 4px, card fill, 1px border in the categorical colour, a 3px left bar in that colour, and the mono ID plus a short label. Remediation nodes use neutral ink with a dashed border. Change nodes are diamonds in the accent colour.
- **Edges:** 1.5px `--muted-foreground` at 50%, with the edge label (`COVERED_BY`, `DERIVED_FROM`) shown on hover.
- **Focus:** the focused gap and its path get a highlight halo (`--highlight` 4px ring) and full-opacity edges; everything else fades to 35%. A side panel lists the path as text, which is also the accessible alternative.
- **Legend:** top-left, the five categorical swatches with labels.

### 8.9 Remediation (`/remediation`)

- A board grouped by status: Draft · Approved · In progress · Completed · Verified (columns as ruled lists, not floating cards). Each item shows the gap ID and priority chip, the action (2 lines), the owner team, and the target in days with a due date. A progress bar uses the sequential ramp.
- Clicking opens the Gap Trace scrolled to §7.

### 8.10 Agent runs (`/runs`, `/runs/:id`)

- List: run ID (mono), started, duration, nodes, LLM calls, input/output tokens, errors, and a **cache hits** note when present (determinism story).
- Detail: a **Gantt timeline**: one row per node, a bar from `started_at` to `ended_at` (sequential step 3, failed in critical, retried with a warning end-cap), a shared time axis in seconds, and a row hover showing tokens and the error. Below it, the node table.

### 8.11 Audit log (`/audit`)

- An insert-only ledger table: time (mono, 24h, IST) · actor (avatar + name; "agent" shown as a neutral square avatar labelled "Pipeline") · action · entity (ID link) · a `before → after` diff expander (JSON diff with word highlights). Filter by actor, entity type and date.
- Header note: "Audit entries cannot be edited or deleted."

---

## 9. Charts (Recharts) – rules

| Chart | Form | Encoding |
|---|---|---|
| Coverage composition | Single 100% stacked horizontal bar, 16px tall | Sequential plum steps 5 → 1 for covered → partial → insufficient → missing. 2px gaps between segments. Direct labels under the bar ("covered 7"). |
| Gaps by type × priority | Horizontal stacked bars, one row per gap type, sorted by total | Segments P1/P2/P3 in status tones, **each with a text label or legend + icon**. Total at the bar end. |
| Risk matrix | 3 × 4 heatmap (criticality 1–3 × severity 1, 1.5, 2, 3) | Sequential ramp by count, the count printed in each cell, empty cells as `--sunken`. Caption with the formula. |
| Accuracy | Bullet-style horizontal bars, shared 0–1 axis | Single hue (sequential step 4), value labels, no targets. |
| Remediation progress | Segmented bar | Sequential ramp. |
| Pipeline run | Gantt (custom bars on a time axis) | Sequential step 3; status via end-cap icon. |

**Mark specs:** bar thickness 16–20px with a 4px radius on the data end only, anchored to the baseline. 2px line strokes. Gridlines are horizontal only, in `--border`. Ticks in `small` muted. **Every chart has:**
- A hover tooltip on `--raised` with a 6px radius, the series name and value in ink, and a colour dot.
- A legend whenever there are ≥ 2 series.
- A "View as table" toggle that renders the same data as an accessible table.
- An `aria-label` summary sentence.

Wrap Recharts in `components/charts/*` so that the colours come from CSS variables (`getComputedStyle`) and re-read when the theme changes.

---

## 10. Content and voice

- Plain, precise and declarative. Sentence case everywhere. Avoid "Oops", "Awesome!" and exclamation marks.
- Always name the source: "RBI KYC MD 2016, para 38", "EVD-07 test log".
- Abstention copy: "Insufficient evidence", "Not specified", "Not in corpus", "Needs human review". Never "Unknown error" or "Something went wrong" without the envelope message.
- Agent attribution: "Suggested by agent", "Drafted by agent · awaiting approval". Avoid "AI" in labels except the one explanation line on the Documents pipeline panel.
- Dates: `11 Oct 2026`, times `14:02 IST`. Numbers use Indian digit grouping in evidence tables (`2,105`, `1,240`); use `Intl.NumberFormat('en-IN')`.

---

## 11. Accessibility

- WCAG 2.2 AA. All text tokens in §3 pass at ≥ 4.5 : 1, and control borders at ≥ 3 : 1.
- Status, coverage, priority and change type are never colour-only: always icon + text, or glyph + text.
- Focus ring: 2px `--ring` at 2px offset on every interactive element. In the dark theme it is cream, so it stands out against plum.
- Every table has a caption and proper headers. The trace uses an ordered list (`<ol>`) with section headings. The graph has a text alternative (the path panel).
- Keyboard: the full app is operable. Shortcuts as in §8.3, with `?` opening the shortcut sheet. The skip link is kept from the scaffold.
- Honour `prefers-reduced-motion`, and support `forced-colors` (borders survive, and the categorical swatches add a text label).

---

## 12. Mock mode and fixtures

- `VITE_USE_MOCKS=true` serves fixtures from `src/mocks/fixtures/*.json` through the same typed API client (`services/api-client.ts`), with 300–700ms artificial latency so the loading states are seen. A `?mockError=gaps` query param forces an error state for testing.
- **Zod schemas** mirror plan §5 and §4 exactly (enum values included). Fixtures must parse with them, which a test asserts.
- **Build the fixtures from `backend/demo_data/`, not from imagination:**
  - **Obligations:** the rows in `3_answer_key/expected_mappings_RBI.csv` (OB-01 to OB-11, N-01 to N-08, NSM-SCOPE). `source_quote` must be copied **verbatim** from `1_regulations_rbi/RBI_KYC_MD_2016_updated_2025-08-14.txt` (KYC) or transcribed exactly from the NSM PDFs. If an exact quote can't be found, set it to `"[QUOTE TO BE FILLED FROM SOURCE]"`. Don't paraphrase.
  - **Controls:** `2_bank_nova_trust/rcm/RCM_Nova_Trust_Risk_Control_Matrix.csv` (CTL-02 … CTL-22).
  - **Evidence:** EVD-02, EVD-06 and EVD-07 rows as given.
  - **Gaps:** the 12 in `ANSWER_KEY.md` with these risk scores from plan §6: NG-03 9 (P1, origin change) · G-07 6 (P1) · NG-01 6 (P1) · G-01, G-03, G-04, G-06, NG-02, NG-04 4 (P2) · G-08 3 (P2) · G-05 2 (P3) · G-02 1 (P3).
  - **Changes:** CHN-01 to CHN-04 from `ANSWER_KEY_NSM_REAL.md` §3.
  - **Eval:** fixture values are **placeholders**, clearly shown with the Mock tag. Real numbers come only from `/eval/latest`.
- Note: plan §11 still mentions "G-12 (privileged access)" for the trace demo. That scenario is in `_archive_not_used/`. Use **G-07** (KYC) and **NG-03** (NSM, from change) as the two showcase traces.

---

## 13. Implementation notes

- **Packages to add:** `lucide-react`, `@fontsource-variable/source-serif-4`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`, `@xyflow/react` (graph only), and shadcn components as needed (`dialog`, `select`, `dropdown-menu`, `tabs`, `tooltip`, `popover`, `sheet`, `table`, `toast`/`sonner`, `checkbox`, `form`). Do not add another chart library, CSS-in-JS or a component kit other than shadcn.
- **Tokens:** rewrite `src/styles/index.css`, keeping its structure: `@theme inline` maps every token in §3.2 (plus `--color-sunken`, `--color-raised`, `--color-accent`, `--color-highlight`, the status tints and the 5 `--chart-cat-*` and 5 `--chart-seq-*` variables), light `:root`, the dark media block guarded by `:not([data-theme="light"])`, and `:root[data-theme="dark"]`.
- **Folders** follow the scaffold's `src/features/<feature>/` convention: `dashboard`, `documents`, `changes`, `obligations`, `controls`, `gaps` (list + trace), `remediation`, `graph`, `runs`, `audit`. Shared pieces go in `components/data-display` (badges, quote block, ID link, graph path, priority chip), `components/charts`, and `components/layout` (shell, sidebar, top bar, theme control, actor select).
- **Query keys** go in `lib/query-keys.ts`. Mutations invalidate the gap, trace and audit queries.
- **Tests:** a render test per page for the loading, empty, error and data states; fixtures parse with the Zod schemas; the theme control toggles `data-theme`; the actor select sets `X-Actor` on requests.

---

## 14. Build order (matches plan §9)

1. Tokens, fonts, theme control, shell (sidebar, top bar, actor select, mock tag), shared badges and quote block.
2. Mock layer, Zod schemas and fixtures.
3. **Documents** and the live pipeline panel → **Obligations** (Checkpoint 1, H4).
4. **Gaps** list → **Gap Trace** → **Dashboard** (Checkpoint 2, H8).
5. **Changes**.
6. Controls/mappings, Remediation, Agent runs, Audit.
7. Graph (optional), print stylesheet, final dark-theme pass.

---

## 15. Acceptance checklist

- [ ] No colour outside §3 is used anywhere (grep for `blue-`, `indigo-`, `violet-`, `slate-`, `gray-`, and for hex literals outside `index.css`).
- [ ] Every screen looks intentional in **both** light and dark themes, and the theme choice persists and doesn't flash on load.
- [ ] Fonts are Source Serif 4 / IBM Plex Sans / IBM Plex Mono, self-hosted. Numbers are tabular.
- [ ] No gradients, glows, emoji, sparkle icons, confidence percentages, donuts or dual axes.
- [ ] Every quote has a source line and a Verbatim/Not-verified tag. No paraphrased quotes in fixtures.
- [ ] "Insufficient evidence", "Not applicable" (with reason) and "Not in corpus" are visible where the answer key expects them.
- [ ] The Gap Trace for G-07 and NG-03 reads top to bottom as a complete story, approve works, and the audit row appears.
- [ ] Changes shows CHN-01 to CHN-04, never labels the consolidated items "New", and shows the 24 Apr 2025 corpus-gap warning.
- [ ] Every data view has loading, empty and error states. Every chart has a tooltip, a legend (≥ 2 series) and a table view.
- [ ] Keyboard-only walkthrough of the demo script works. Axe reports no serious violations.
- [ ] Usable at 375px width (no horizontal page scroll).
