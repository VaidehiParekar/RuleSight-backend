# Real RBI document: what to use and what to skip

**Source:** RBI Master Direction – Know Your Customer (KYC) Direction, 2016 (Updated as on August 14, 2025)
**Ref:** RBI/DBR/2015-16/18 · Master Direction DBR.AML.BC.No.81/14.01.001/2015-16 · issued 25 Feb 2016
**URL:** https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566

**Already downloaded:** [RBI_KYC_MD_2016_updated_2025-08-14.txt](RBI_KYC_MD_2016_updated_2025-08-14.txt) is the full page text (about 229k characters), taken from rbi.org.in on 11 Oct 2026. Paragraph numbers 3(a)(iv), 6(d), 18, 37, 38, 46, 68 and 70 were checked against this text.
In the app, upload it with `title = "RBI KYC Master Direction 2016 (updated 14-08-2025)"`, `regulator = RBI`, `version_label = 2025-08-14`, `is_synthetic = false` (this is the real RBI text).

> **Ingestion note:** RBI footnote numbers are glued to the text (e.g. `38. 112Updation`, `7“Controlling`). Strip them when chunking, and have the critic **normalise whitespace** before the verbatim-quote check.

## Other real files in this folder

| File | What it is | Use |
|---|---|---|
| `NSM_v1_RBI_circular_2024-10-30_WITHDRAWN.pdf` | RBI circular on Note Sorting Machines (BIS standards), 30 Oct 2024. Has a "Withdrawn from October 02, 2026" watermark | **Real change-intelligence demo**, old version |
| `NSM_v2_RBI_Master_Direction_2026-10-02.pdf` | RBI Master Direction on Note Sorting Machines, 2 Oct 2026. Consolidates and withdraws 5 circulars | New version; tested against synthetic POL-04 |

Answer key: [../3_answer_key/ANSWER_KEY_NSM_REAL.md](../3_answer_key/ANSWER_KEY_NSM_REAL.md).

## USE: paragraphs that match our demo bank's controls

Run the pipeline **only on these paragraphs** (Chapters II, IV, VI, VII and para 70). Do not run the whole document on the free tier.

| Para | Topic | Short quote | Nova Trust control | Expected result |
|---|---|---|---|---|
| 3(a)(iv) | Beneficial owner, companies | "more than 10 percent of the shares or capital or profits" | CTL-04 (uses 25%) | **Gap, design** |
| 6, 7 | Designated Director, Principal Officer | "In no case, the Principal Officer shall be nominated as the 'Designated Director'." | CTL-10 | Covered (the "must be different people" detail is not stated in the policy, so this may come out as partial; that is an acceptable answer) |
| 18(a)(iv) | V-CIP geo-tagging | "live GPS co-ordinates (geo-tagging) of the customer" | CTL-17 | **Gap, design** |
| 18(a)(v) | V-CIP liveness | "face liveness / spoof detection as well as face matching technology" | CTL-17 (face match only) | **Gap, design** |
| 18(c)(i) | V-CIP storage | "stored in a system / systems located in India" | CTL-18 (location not stated) | **Insufficient info** |
| 37(a) | Risk categorisation review | "at least once in six months" | CTL-02 (annual) | **Gap, design** |
| 38 | Periodic updation | "once in every two years for high-risk… eight years… ten years" | CTL-05 (3 years for High) + EVD-02 | **Gap, design + operating** |
| 46(a), 46(b) | Record preservation | "at least five years…" | CTL-09 (8 years) | Covered |
| 70 | Employee training | "On-going employee training programme shall be put in place" | none | **Gap, missing** |

This gives you a **second, real accuracy check**: 9 rows with known expected results. Show it as "Real RBI subset: X of 9 correct".

## USE (optional): an applicability demo on real text

| Para | Topic | Why it is a good demo |
|---|---|---|
| 68 | At-par cheque facility availed by **co-operative banks** | Nova Trust is a Scheduled Commercial Bank, so the agent should mark this **Not applicable** with a reason |

## SKIP: do not ingest or analyse these

| Part | Reason |
|---|---|
| Introduction and preamble, para 1 (title), definitions in para 3 (except 3(a)(iv)) | Not obligations. Definitions make the extractor produce false positives |
| Chapter IX (paras 51–54A: UAPA, WMD Act, UNSC sanctions lists, FATF jurisdictions) | Needs sanctions-screening controls our demo bank does not have; too large for one night |
| Chapter X paras 57 (FATCA/CRS), 63 (correspondent banking), 64 (wire transfers), 66 (PAN), 67 (third-party products) | Out of scope for the demo bank |
| Chapter XI (repeal provisions) and the Annexes/Appendix | Lists of repealed circulars, no obligations |
| Paras 47–50 (reporting to FIU-IND) | They refer to "the time limit as specified in the Rule". The **actual CTR/STR deadlines are in the PML Rules (Rule 8), not in this Master Direction.** Do not claim RBI MD says "15th of the month" or "7 working days". Our synthetic REG-KYC covers these instead |

## What is fictional (and why)

| Part | Why |
|---|---|
| Nova Trust Bank (policies, RCM, evidence) | Real bank documents are confidential. The bank is fictional, but every regulatory reference points to a real RBI paragraph here. |
| Change demo | Uses the real NSM v1 to v2 pair. The KYC text here is the latest version only. |
| Cross-regulation and contradiction (#13, #14) | **Dropped.** The real corpus has no clear overlap or conflict, so we do not claim these features. |

**Pitch line:** "Every regulation in our demo is real RBI text. The bank is a fictional test subject, and we measured accuracy against a labelled answer key."
