# Answer key: real RBI Note Sorting Machine documents vs Nova Trust POL-04

**Regulations (real, from rbi.org.in):**
- **NSM v1:** RBI/2024-2025/86, DCM (NPD) No.S2193/09.45.000/2024-25, 30 Oct 2024. The PDF carries a red **"Withdrawn from October 02, 2026"** watermark. File: `1_regulations_rbi/NSM_v1_RBI_circular_2024-10-30_WITHDRAWN.pdf`
- **NSM v2:** RBI/DCM/2026-27/473, DCM(NPD) No.S2154/18.00.014/2026-27, 2 Oct 2026, Master Direction on Note Sorting Machines. File: `1_regulations_rbi/NSM_v2_RBI_Master_Direction_2026-10-02.pdf`

**Bank side (fictional Nova Trust, cites real RBI paragraphs):** POL-04, controls CTL-19 to CTL-22, evidence EVD-06 (inventory) and EVD-07 (test log).

**Do not feed this file to the agents.**

---

## 1. Obligations in NSM v2 (8)

| ID | Para | Obligation (short) |
|---|---|---|
| N-01 | 2.2, 4 | Machines must authenticate notes against the features RBI discloses; a note without all genuine features is suspect/reject |
| N-02 | 2.3 | Machines must sort phased-out series as unfit, whatever their condition |
| N-03 | 5 (Tables 1–3) | Machines must sort notes as unfit using the fitness criteria (soiling, limpness, dog-ears > 100 mm², tears, holes > 8 mm², stains, graffiti, folds > 5 mm, decolouration, repair) |
| N-04 | 6.1, 6.2 | Mutilated, imperfect, mismatched and built-up notes are suspect/reject and must be inspected manually |
| N-05 | 7 | Test machines for accuracy and consistency **quarterly**, recalibrate if needed, keep a certificate signed by bank officials |
| N-06 | Testing Procedure (p. 9) | Test deck of **at least 2,000** notes every quarter; tolerance 5% for fitness, **zero** for counterfeits (FICN) |
| N-07 | 8.2 | Phase out NSM models that are **discontinued from production** on or before **30 June 2027**; penalties for non-adherence |
| N-08 | 8.2 | Going forward, procure **only BIS-certified** NSMs |

**Applicability (para 3):** this covers machines operated by banks "either directly by their staff or **indirectly by their agents**". That includes the 6 machines at the CIT agency hubs.

Not obligations: para 1 (history), 8.1 (where to find the BIS standard and lists), the Annex (list of withdrawn circulars).

## 2. Expected mappings and gaps

| Obligation | Control | Coverage | Gap | Type | Why | Priority |
|---|---|---|---|---|---|---|
| N-01 | CTL-21 | Covered | — | — | Insufficient evidence (no configuration certificate supplied) | — |
| N-02 | CTL-21 | Covered | — | — | Insufficient evidence | — |
| N-03 | CTL-21 | Covered | — | — | Insufficient evidence | — |
| N-04 | CTL-22 | Covered | — | — | Insufficient evidence | — |
| N-05 | CTL-19 | Partial | **NG-01** | Design + Operating | Half-yearly vs quarterly; EVD-07 shows **no test in Jul–Sep 2026** | P1 |
| N-06 | CTL-19 | Partial | **NG-02** | Design | 1,000-note deck vs 2,000; CTL-19 uses one 5% threshold, with no zero tolerance for counterfeits | P2 |
| N-07 | none | Missing | **NG-03** | Missing | No phase-out plan (POL-04 §3.1); EVD-06 shows **7 discontinued machines** (CashMate 7 × 5, CashMate 9 × 2); deadline 30 Jun 2027 | P1 |
| N-08 | CTL-20 | Covered | — | — | — | — |
| Para 3 (agents) | none | Scope gap | **NG-04** | Design | POL-04 §1.2 excludes CIT-agent machines; EVD-06 shows 6 NoteGuard N3 at agent hubs, with **test date not recorded** | P2 |

Risk formula (TEAM_PLAN §6, currency handling = criticality 2):
- NG-01: 2 × 3 = 6 → P1
- NG-02: 2 × 2 = 4 → P2
- NG-03: 2 × 3 × 1.5 (deadline introduced by v2) = 9 → P1
- NG-04: 2 × 2 = 4 → P2

## 3. Change intelligence v1 → v2 (the real-world demo)

This is **not** a line-by-line diff. v1 is a 1-page circular and v2 is a 10-page consolidated Master Direction. Compare at **obligation level**.

| ID | What the system should report | Type |
|---|---|---|
| CHN-01 | v1 para 3 ("effective May 01, 2025, banks should deploy only such NSM models that conform… and are duly certified by BIS") is **replaced** by v2 para 8.2: procure only BIS-certified NSMs going forward, and phase out **discontinued** models by **30 June 2027**, with penalties | Modified |
| CHN-02 | v1 is **withdrawn** from 2 Oct 2026 (v2 Annex row 4 + the watermark on v1). The system should mark v1 as `superseded` automatically | Withdrawn |
| CHN-03 | v2's Annex withdraws 5 circulars. Only one (row 4) is in our corpus. Rows 1, 2, 3 (2009, 2010, 2022) and **row 5 (24.04.2025, "Revised Timeline for Implementation")** are **not ingested** | Corpus-gap warning |
| CHN-04 | Requirements N-01 to N-06 come from the July 2022 circular (v2 para 1 says so). They are **consolidated, not new**. The system must **not** call them "new requirements"; it should say "carried over from DCM(NPD)No.S488 dated 01.07.2022 (not in corpus)" | Consolidated |

**What earns marks here:** the system abstains and says "I'm missing the 24 April 2025 circular, so the timeline history may be incomplete". It does not invent what that circular says. That is D2 reliability in action.

## 4. Things the system must not do
- Do not claim penalties or amounts beyond "penalties would be levied … in terms of" the referenced Master Direction.
- Do not treat v1 as still in force after 2 Oct 2026.
- Do not invent the content of the 24.04.2025 circular.
