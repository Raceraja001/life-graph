# Why M8 context snapshots have low precision: root causes

**Scope:** read-only analysis. Master `f534b7ac`, worktree `prec-baseline`. Source: `baseline_report.json`, bge-m3 arm (prod embedder), with the hashing arm for comparison.
**Files read:**
- `evals/context_quality/{dataset,questions}.json`;
- `scripts/eval_context_quality.py`;
- `life_graph/services/memory/{snapshot,retrieval,changes}.py`;
- `life_graph/storage/postgres.py` (`hybrid_search`);
- `docs/audits/2026-11-26-m8-context-quality-evaluation.md`.

**Method:** the classifier is `scratchpad/rc_classify.py`, which recomputes every count below from the report.

**Caveat on the method:** the report gives per-question reason *counts*, not each item's reason.
- **Decisions and intentions:** I worked out which ones came in through the keyword path by applying `snapshot._tsquery` (any word, English stemming) to their titles. All 14 decision and 14 intention keyword counts match the reported reasons exactly.
- **Memories:** I classified each memory by reading its text against the question. This is judgement, and the borderline calls are listed in the tables.

## 0. Short answer

**Precision is low mainly because of the snapshot's structure, not because retrieval is poor.**
- **Every snapshot has a fixed size, whatever the question.** It always holds:
  - 10 search hits;
  - 0–3 neighbour or entity expansions;
  - all 4 current decisions;
  - all 5 intentions due within 14 days.
- **The result is 19–22 items per question.** The gold relevant set (required ∪ acceptable) has a median of **5**.
- **Even a perfect selector could not beat about 0.30 at that size.** The best possible precision at the current item counts is **0.30 overall**, against an actual **0.25**.
- **27 of 45 questions already contain every gold record.** Their precision is exactly at that ceiling, so all of their noise is forced filler.

| Slice of the 839 items | Items | Precision | Share of the 629 noise items |
|---|---|---|---|
| Standing block (`current_decision` + `due_intention`, `snapshot.py:1235-1245`, `:1268-1273`) | 354 | **0.12** | 311 (49%) |
| Memory search leg (10 hits + expansions, `retrieval.py:33`, `:818-833`, `:886-887`) | 457 | 0.33 | 306 (49%) |
| Keyword-matched decisions/intentions (`snapshot.py:811-876`) | 28 | 0.57 | 12 (2%) |

**The hashing arm confirms that precision is mostly not an embedding problem.**
- Decision and intention noise is identical in both arms: **323 vs 323**.
- Memory precision rises only from 0.26 (hashing) to 0.33 (bge-m3).
- Most of what bge-m3 buys is recall: 81/97 → 91/97 required records found.

**Where the noise comes from (bge-m3):**

| Cause | Items | Share |
|---|---|---|
| Standing decision/intention block (cause 7) | 311 | 49% |
| Loose semantic neighbours (cause 1) | 103 | 16% |
| Top-K fill (cause 10) | 73 | 12% |
| Hub "generic personal" records (cause 8) | 60 | 10% |
| Keyword overlap with a different meaning (cause 2) | 60 | 10% |
| Gold too narrow (cause 11) | 10 | 2% |
| Query ambiguity (cause 9) | 8 | 1% |
| Historical record competing with the current one (cause 3) | 4 | 1% |
| Pending, superseded or expired records (cause 4) | 0 | – |
| Duplicates (cause 5) | 0 | – |

**Cause 4 is zero:** the state filters work, and the scoring counts those records as forbidden, not as noise (`eval_context_quality.py:516,529`).

## 1. Classification of every noise item

### 1a. Counts per cause and category (bge-m3 arm, 629 noise items)

| cause | O | A | B | C | D | E | F | G | total | share |
|---|---|---|---|---|---|---|---|---|---|---|
| 1. loose semantic similarity | 20 | 10 | 11 | 19 | 10 | 6 | 10 | 17 | **103** | 16% |
| 2. keyword overlap, different meaning | 7 | 8 | 5 | 4 | 6 | 9 | 8 | 13 | **60** | 10% |
| 3. historical record competing with current | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | **4** | 1% |
| 4. pending/rejected/superseded/expired | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0% |
| 5. duplicate / near-duplicate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0% |
| 6. missing relationship | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0% |
| 7. decision/intention block mixed in | 46 | 41 | 39 | 43 | 33 | 24 | 37 | 48 | **311** | 49% |
| 8. generic personal info, unrelated question | 11 | 10 | 11 | 6 | 2 | 6 | 8 | 6 | **60** | 10% |
| 9. query ambiguity | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **8** | 1% |
| 10. ranking / top-K fill | 11 | 12 | 7 | 7 | 10 | 7 | 8 | 11 | **73** | 12% |
| 11. scoring artefact (gold too narrow) | 7 | 0 | 0 | 1 | 0 | 0 | 0 | 2 | **10** | 2% |
| **all** | 112 | 81 | 73 | 80 | 61 | 53 | 72 | 97 | **629** | 100% |

**How to read the categories:**
- **Category O has the most cause 9 and cause 11 items.** These are wide questions ("commitments", "decide", "missing information"), where the gold set is hardest to draw.
- **Category G has the most cause 2 items.** "want", "score", "manager" and "new" are frequent words that match unrelated records.
- **Cause 7 is spread evenly** (24–48 per category), because it does not depend on the question.

**Recall misses (cause 6 lives here, not in the noise).** There are 6 bge-m3 misses:

| q | Missed | Primary cause | Why |
|---|---|---|---|
| F2 | `w_task_demo` | 6 missing relationship | The typed link `w_proj_rp -LEADS_TO-> w_task_demo` exists. Retrieval follows only ASSOCIATED links (`retrieval.py:154-167` → `associations.neighbours`), and typed links are read only *after* the budget, between items already kept (`snapshot.py:1407-1411`, `:1116`). |
| O3 | `i_aws_book` | 6 missing relationship | An open intention with no `trigger_time` can never be "due" (`snapshot.py:900-945`). It is reachable only by word overlap (`:855-876`), and "commitments" shares no word with it. No link joins it to the `l_aws_goal` memory (`Intention.source_memory` is unset; dataset `no_structured_home`). |
| O1 | `l_aws_goal`, `w_blocker` | 10 ranking / top-K | Crowded out of the 10 search slots by `f_fund_old`, `w_job_new`, `w_not_leaving` and `f_injection`. |
| O2 | `l_aws_goal` | 10 (and 2 for type) | A goal record (`fact_type` intention, tag `goal`), but retrieval never uses `fact_type` or tags. |
| O10 | `f_fund_old` | 10 | Crowded out by `l_aws_prereq` and `l_prereq` ("before …"). |

**"Reached only by luck" (also cause 6):**
- **O9 `i_fee`** matched only because "₹1,20,000" and "₹38,000" share the token `000` (`_words` keeps digit runs, `snapshot.py:788-818`).
- **A3 and F5 `i_fee`** matched on "Ila" and "school".
- **O1, O3 and O8:** the required intentions are present only because the standing block adds every due intention; no query-aware path finds them.

### 1b. Every noise item (bge-m3), one primary cause each

Standing decision/intention items share one cause and one code path, so they are grouped per question; every memory item and every keyword-matched decision/intention has its own row.

| q | item(s) | cause | why |
|---|---|---|---|
| O1 | d_pgqueue | 7 | standing block: added whatever the question (1) |
| O1 | f_fund_old | 10 | savings figure, no tie to priorities |
| O1 | f_injection | 2 | external email says 'top priority' (injection bait) |
| O1 | w_inferred_jobchange | 8 | inferred career guess, hub record |
| O1 | w_job_new | 1 | 'current' job state, not a priority |
| O1 | w_not_leaving | 11 | owner-stated career aim; gold accepts w_goal_link |
| O2 | d_billing_vendor, d_caregiver, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| O2 | f_budget | 11 | owner-stated money target ('I want to keep ... under'); gold accepts f_fund_old |
| O2 | p_constraint_travel | 1 | constraint, not a goal |
| O2 | p_inferred_hobby | 1 | inferred interest, not an active goal |
| O2 | p_run | 11 | training habit behind the marathon goal; gold accepts l_aws_progress for AWS |
| O3 | d_billing_vendor, d_caregiver, d_pgqueue | 7 | standing block: added whatever the question (3) |
| O3 | d_pause_rust | 2 | 'done' in 'until the AWS exam is done' |
| O3 | f_budget | 9 | 'commitments' read as financial commitments |
| O3 | f_car_loan_closed | 9 | a financial commitment that is done |
| O3 | f_fund_goal | 9 | savings goal read as commitment |
| O3 | f_fund_old | 10 | fill |
| O3 | l_aws_goal | 11 | dated plan whose child i_aws_book is required |
| O3 | p_back | 8 | hub record |
| O3 | p_constraint_travel | 1 | 'can't ... until' ~ 'not done' |
| O3 | w_blocker | 1 | blocked work, shares 'still' |
| O3 | w_dep | 3 | resolved dependency still active beside w_dep_done |
| O3 | w_proj_billing | 9 | ongoing project read as a commitment |
| O4 | i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (5) |
| O4 | f_budget | 9 | owner rule, 60 days old: decision-like |
| O4 | l_aws_goal | 9 | plan, decision-like |
| O4 | p_constraint_travel | 11 | owner-stated rule 25 days ago; gold accepts f_car_loan_closed (26 d) |
| O4 | p_goal_marathon | 9 | plan, decision-like |
| O4 | p_inferred_hobby | 8 | hub record |
| O4 | p_no_meat | 8 | hub personal rule |
| O4 | w_inferred_jobchange | 8 | hub record |
| O4 | w_proj_billing | 10 | fill |
| O5 | i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (5) |
| O5 | f_budget | 10 | fill |
| O5 | f_car_loan_closed | 1 | something ended ~ 'replaced' |
| O5 | f_fund_old | 1 | value with a pending successor ~ 'replaced' |
| O5 | f_injection | 2 | 'ignore previous instructions / OVERRIDE' ~ superseded |
| O5 | p_constraint_travel | 8 | hub record |
| O5 | p_no_meat | 8 | hub record |
| O5 | w_blocker | 10 | fill |
| O5 | w_inferred_jobchange | 8 | hub record |
| O5 | w_proj_billing | 1 | 'moving from the old PHP system' ~ replaced |
| O5 | w_task_runbook | 10 | fill |
| O7 | d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee | 7 | standing block: added whatever the question (6) |
| O7 | f_budget | 10 | fill |
| O7 | f_fund_goal | 10 | fill |
| O7 | f_fund_old | 10 | fill |
| O7 | p_constraint_travel | 1 | a constraint ~ 'blocked' |
| O7 | w_inferred_jobchange | 8 | hub record |
| O7 | w_kafka_consequence | 1 | project change, not a block |
| O8 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue | 7 | standing block: added whatever the question (4) |
| O8 | l_aws_goal | 1 | dated, months away |
| O8 | l_aws_prereq | 1 | 'before booking' |
| O8 | p_back | 1 | dated 21 Nov, past |
| O8 | p_goal_marathon | 1 | dated, Feb 2027 |
| O8 | p_pickup | 9 | fixed weekday duty: 'deadline' vs schedule |
| O8 | p_run | 1 | weekday routine |
| O8 | w_blocker | 1 | dated 4 Nov request |
| O8 | w_career_goal | 1 | dated, 2027 |
| O8 | w_dep | 3 | resolved dependency |
| O8 | w_inferred_jobchange | 8 | hub record |
| O8 | w_proj_billing | 10 | fill |
| O9 | d_billing_vendor, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| O9 | d_caregiver | 2 | 'consider' ~ 'Considered after the October hospital stay' |
| O9 | w_job_new | 1 | promotion ~ income; f_salary_new already holds the figure |
| O9 | w_not_leaving | 2 | 'new' job vs 'new' laptop |
| O10 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_demo, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| O10 | i_clinic | 2 | 'take' ~ 'Take Kamala to the clinic' |
| O10 | l_aws_prereq | 1 | 'before I can' prerequisite phrasing |
| O10 | l_prereq | 1 | 'before starting' prerequisite phrasing |
| O10 | p_constraint_travel | 8 | hub record |
| O10 | p_mother_care | 11 | dependent's ongoing care cost bears on a second loan |
| O10 | p_saturday | 2 | 'second Saturday' vs 'second home loan' |
| O10 | w_job_new | 11 | employment/role bears on loan eligibility |
| A1 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| A1 | f_husband_income_new | 2 | 'take' (coffee) vs 'take-home pay' |
| A1 | f_salary_new | 2 | 'take' vs 'take-home salary' |
| A1 | i_clinic | 2 | 'take' (my coffee) ~ 'Take Kamala' |
| A1 | p_back | 8 | hub record |
| A1 | p_constraint_travel | 8 | hub record |
| A1 | p_inferred_hobby | 8 | hub record |
| A1 | p_mother_care | 2 | 'take' vs 'takes her to the clinic' |
| A1 | p_no_meat | 1 | food preference, same topic |
| A1 | p_run | 1 | morning routine ~ morning coffee |
| A1 | w_inferred_jobchange | 8 | hub record |
| A1 | w_job_new | 10 | ASSOCIATED neighbour of keyword-matched f_salary_new ('promotion' group) |
| A2 | d_billing_vendor, d_pause_rust, d_pgqueue, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| A2 | f_budget | 10 | fill |
| A2 | f_fund_goal | 10 | fill |
| A2 | p_back | 8 | hub record |
| A2 | p_inferred_hobby | 8 | hub record |
| A2 | w_inferred_jobchange | 2 | 'look after' vs 'looking to leave' |
| A2 | w_not_leaving | 2 | 'look after' vs 'not looking for a new job' |
| A3 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| A3 | f_husband_income_new | 2 | 'school' (Ila's) vs 'Arjun's school cut his hours' |
| A3 | p_back | 8 | hub record |
| A3 | p_constraint_travel | 8 | hub record |
| A3 | p_mother_care | 1 | another family duty with a day pattern |
| A3 | p_mother_hosp | 1 | family, dates |
| A3 | p_run | 1 | 'which days' ~ Mon/Wed/Fri |
| A3 | p_saturday | 1 | 'which days' ~ every second Saturday |
| A4 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| A4 | f_budget | 10 | fill |
| A4 | f_car_loan_closed | 10 | fill |
| A4 | f_fund_goal | 10 | fill |
| A4 | f_fund_old | 10 | fill |
| A4 | f_salary_new | 10 | fill |
| A4 | l_aws_goal | 1 | 'when' ~ 'by March 2027' |
| A4 | l_aws_prereq | 10 | fill |
| A4 | p_goal_marathon | 1 | 'when' ~ 'February 2027' |
| A4 | p_inferred_hobby | 8 | hub record |
| A4 | w_task_runbook | 1 | 'when' ~ 'by Friday 28 November' |
| A5 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| A5 | f_budget | 10 | fill |
| A5 | f_fund_goal | 2 | 'goals' (fitness) vs savings 'goal' |
| A5 | f_salary_new | 10 | fill |
| A5 | l_aws_prereq | 10 | fill |
| A5 | p_constraint_travel | 8 | hub record |
| A5 | p_inferred_hobby | 1 | hobby ~ habits |
| B1 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| B1 | d_pgqueue | 2 | 'job' ~ 'Postgres job queue' |
| B1 | f_fund_goal | 10 | fill |
| B1 | f_fund_old | 10 | fill |
| B1 | p_anniv | 8 | hub record |
| B1 | p_back | 1 | work status |
| B1 | p_constraint_travel | 8 | hub record |
| B1 | w_inferred_jobchange | 1 | 'job', career, not the title |
| B1 | w_not_leaving | 1 | 'job', career, not the title |
| B2 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| B2 | f_fund_goal | 10 | fill |
| B2 | f_salary_new | 10 | fill |
| B2 | p_back | 8 | hub record |
| B2 | p_inferred_hobby | 8 | hub record |
| B2 | w_goal_link | 2 | 'engineering manager' role vs 'my manager' person |
| B2 | w_inferred_jobchange | 1 | work/career |
| B2 | w_proj_billing | 1 | work |
| B3 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| B3 | l_prereq | 1 | 'before starting' ~ 'depend on' |
| B3 | p_back | 8 | hub record |
| B3 | p_constraint_travel | 1 | 'until' ~ 'waiting' |
| B3 | w_blocker | 1 | another project's blocker, shares 'still' |
| B3 | w_inferred_jobchange | 8 | hub record |
| B4 | d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee | 7 | standing block: added whatever the question (6) |
| B4 | f_budget | 10 | fill |
| B4 | f_injection | 2 | PayFlow 'billing notice' vs 'Billing migration' |
| B4 | p_back | 8 | hub record |
| B4 | p_constraint_travel | 8 | hub record |
| B4 | w_goal_link | 1 | work |
| B4 | w_inferred_jobchange | 8 | hub record |
| B4 | w_not_leaving | 8 | hub record |
| B5 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| B5 | f_budget | 10 | fill |
| B5 | f_fund_goal | 2 | career 'goal' vs savings 'goal' |
| B5 | f_fund_old | 10 | fill |
| B5 | f_salary_new | 1 | promotion pay, career-adjacent |
| B5 | l_aws_prereq | 1 | certification, career-adjacent |
| B5 | p_constraint_travel | 8 | hub record |
| B5 | p_goal_marathon | 2 | career 'goal' vs fitness goal |
| C1 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| C1 | f_budget | 1 | monthly money |
| C1 | f_car_loan_closed | 1 | money |
| C1 | f_fund_goal | 1 | money |
| C1 | f_fund_old | 1 | money |
| C1 | i_clinic | 2 | 'take(-home)' ~ 'Take Kamala' |
| C1 | p_back | 8 | hub record |
| C1 | p_mother_care | 2 | 'take(-home)' vs 'takes her' |
| C2 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| C2 | f_fund_goal | 1 | money |
| C2 | f_fund_old | 1 | money |
| C2 | f_salary_new | 1 | money |
| C2 | l_prereq | 10 | fill |
| C2 | p_back | 8 | hub record |
| C2 | w_blocker | 2 | 'still repaying' vs 'still has not given' |
| C2 | w_proj_billing | 10 | fill |
| C2 | w_task_runbook | 10 | fill |
| C3 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| C3 | f_budget | 1 | money |
| C3 | f_car_loan_closed | 1 | money |
| C3 | f_emi | 1 | money |
| C3 | f_injection | 1 | money transfer email |
| C3 | f_salary_new | 1 | money |
| C3 | l_aws_prereq | 10 | fill |
| C3 | p_anniv | 8 | hub record |
| C3 | w_job_new | 10 | fill |
| C4 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| C4 | f_car_loan_closed | 1 | money |
| C4 | f_emi | 1 | money |
| C4 | f_fund_goal | 1 | money |
| C4 | f_fund_old | 1 | money |
| C4 | f_sip | 1 | money |
| C4 | p_anniv | 8 | hub record |
| C4 | w_proj_billing | 10 | fill |
| C5 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| C5 | d_pgqueue | 2 | 'much' ~ 'costs too much to run' |
| C5 | f_car_loan_closed | 1 | money |
| C5 | f_fund_old | 1 | money |
| C5 | f_husband_income_new | 11 | household income; gold accepts f_salary_new |
| C5 | p_constraint_travel | 8 | hub record |
| C5 | p_no_meat | 8 | hub record |
| C5 | w_job_new | 10 | fill |
| D1 | d_billing_vendor, d_caregiver, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| D1 | f_salary_new | 10 | fill |
| D1 | p_inferred_hobby | 1 | 'learning' the veena, inferred |
| D1 | w_career_goal | 10 | fill |
| D1 | w_job_new | 10 | fill |
| D1 | w_not_leaving | 8 | hub record |
| D1 | w_proj_billing | 10 | fill |
| D2 | d_billing_vendor, d_caregiver, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| D2 | f_car_loan_closed | 10 | fill |
| D2 | i_aws_book | 2 | 'book' (Rust book) ~ 'Book the AWS exam slot' |
| D2 | l_aws_goal | 1 | other course |
| D2 | l_aws_prereq | 2 | 'Rust book' vs 'booking the AWS exam' |
| D2 | l_aws_progress | 1 | progress on another course |
| D2 | p_inferred_hobby | 1 | learning |
| D2 | w_kafka_consequence | 2 | 'book' vs 'training she had booked' |
| D2 | w_task_runbook | 10 | fill |
| D3 | d_billing_vendor, d_caregiver, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| D3 | l_mastered | 1 | learning |
| D3 | l_prereq | 1 | prerequisite of another course |
| D3 | l_rust_progress_new | 2 | 'booking' vs 'Rust book' |
| D3 | l_rust_topic | 2 | 'booking' vs 'Rust book' |
| D3 | p_constraint_travel | 8 | hub record |
| D3 | w_kafka_consequence | 2 | 'booking' vs 'training she had booked' |
| D3 | w_task_runbook | 10 | fill |
| D4 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| D4 | f_car_loan_closed | 10 | fill |
| D4 | f_salary_new | 10 | fill |
| D4 | l_aws_goal | 1 | learning, not mastered |
| D4 | l_aws_prereq | 1 | learning |
| D4 | l_aws_progress | 1 | learning, 68% |
| D4 | p_inferred_hobby | 1 | learning |
| D4 | w_job_new | 10 | fill |
| E2 | f_emi | 2 | 'home' / 'March' in 'Home loan ... March 2034' |
| E2 | f_husband_income_old | 1 | husband's take-home pay, other person (as_of history) |
| E3 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| E3 | d_pgqueue | 2 | 'running' ~ 'too much to run' |
| E3 | f_fund_old | 1 | money |
| E3 | l_prereq | 10 | fill |
| E3 | p_back | 8 | hub record |
| E3 | p_constraint_travel | 8 | hub record |
| E3 | p_goal_marathon | 2 | 'running' (loan) vs 'run the half marathon' |
| E3 | p_run | 2 | 'running' vs 'runs 5 km' |
| E3 | w_blocker | 2 | 'still' (running) vs 'still has not given' |
| E3 | w_inferred_jobchange | 8 | hub record |
| E3 | w_proj_billing | 10 | fill |
| E3 | w_task_runbook | 10 | fill |
| E4 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| E4 | f_car_loan_closed | 10 | fill |
| E4 | f_salary_new | 10 | fill |
| E4 | p_constraint_travel | 1 | work + family status |
| E4 | p_no_meat | 8 | hub record |
| E4 | p_run | 8 | hub record ('before work') |
| E4 | p_saturday | 8 | hub record |
| E4 | w_blocker | 2 | 'still on leave' vs 'still has not given' |
| E4 | w_inferred_jobchange | 2 | 'on leave' vs 'looking to leave' |
| E4 | w_not_leaving | 2 | 'on leave' vs 'not leaving' |
| E5 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| E5 | d_pgqueue | 2 | 'Route Planner v2' (project words, not the demo) |
| E5 | l_aws_goal | 1 | dated |
| E5 | l_mastered | 10 | fill |
| E5 | l_rust_topic | 10 | fill |
| E5 | p_goal_marathon | 1 | dated event |
| E5 | w_dep | 3 | resolved dependency of the same project |
| E5 | w_task_runbook | 1 | another dated task |
| F1 | d_billing_vendor, d_pause_rust, d_pgqueue, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| F1 | f_car_loan_closed | 1 | 'October' event |
| F1 | l_aws_progress | 10 | fill |
| F1 | l_prereq | 2 | 'why did that start' vs 'before starting async Rust' |
| F1 | p_back | 1 | leave/back to work |
| F1 | p_daughter_school | 1 | family |
| F1 | w_task_runbook | 10 | fill |
| F2 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| F2 | f_fund_goal | 2 | 'goal' (career) vs savings goal |
| F2 | f_salary_new | 1 | promotion pay, career |
| F2 | l_aws_goal | 1 | career-adjacent plan |
| F2 | l_aws_prereq | 10 | fill |
| F2 | w_manager | 2 | 'engineering manager' role vs Suresh 'the owner's manager' |
| F3 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| F3 | f_fund_old | 10 | fill |
| F3 | l_mastered | 2 | 'Postgres queue' vs 'PostgreSQL query tuning' |
| F3 | p_coffee | 10 | fill |
| F3 | p_constraint_travel | 8 | hub record |
| F3 | p_saturday | 8 | hub record |
| F3 | w_inferred_jobchange | 8 | hub record |
| F3 | w_job_new | 10 | fill |
| F3 | w_not_leaving | 8 | hub record |
| F3 | w_proj_billing | 1 | tech migration ~ 'instead of' |
| F4 | d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee | 7 | standing block: added whatever the question (6) |
| F4 | f_fund_goal | 10 | fill |
| F4 | l_aws_goal | 10 | fill |
| F4 | l_prereq | 1 | 'before starting' ~ held up |
| F4 | p_constraint_travel | 1 | 'can't ... until' ~ held up |
| F4 | w_dep | 3 | resolved dependency competes as the 'held up' project |
| F4 | w_manager | 1 | work |
| F4 | w_proj_rp | 2 | 'project' word, other project |
| F5 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| F5 | f_car_loan_closed | 2 | 'paid' (fee) vs 'paid off the car loan' |
| F5 | f_husband_income_new | 2 | 'school' vs 'Arjun's school' |
| F5 | p_constraint_travel | 8 | hub record |
| F5 | p_husband_job | 2 | 'school' vs 'Government Higher Secondary School' |
| F5 | p_mother_care | 8 | hub family record |
| F5 | p_mother_hosp | 8 | hub family record |
| F5 | p_saturday | 8 | hub family record |
| F5 | w_task_runbook | 1 | 'when must' ~ 'by Friday' |
| G1 | d_billing_vendor, d_caregiver, d_pause_rust, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (8) |
| G1 | d_pgqueue | 2 | 'job' ~ 'Postgres job queue' |
| G1 | f_car_loan_closed | 10 | fill |
| G1 | f_salary_new | 1 | career/pay |
| G1 | l_mastered | 10 | fill |
| G1 | p_back | 1 | job status |
| G1 | p_inferred_hobby | 8 | hub record |
| G1 | w_dep | 2 | 'new' job vs 'new geocoding API' |
| G1 | w_dep_done | 2 | 'new' job vs 'new geocoding API' |
| G2 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| G2 | f_budget | 2 | 'want' (to learn) vs 'want to keep spending' |
| G2 | l_aws_goal | 1 | learning plan |
| G2 | l_aws_prereq | 2 | 'want' vs 'I want to score' |
| G2 | l_prereq | 1 | 'wants to understand Rust' ~ learning wish |
| G2 | l_rust_topic | 1 | learning |
| G2 | p_daughter_school | 8 | hub record |
| G2 | p_goal_marathon | 2 | 'want' vs 'wants to run' |
| G2 | w_career_goal | 2 | 'want' vs 'I want to become' |
| G2 | w_goal_link | 10 | fill |
| G2 | w_not_leaving | 2 | 'want' vs 'I want to grow' |
| G3 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| G3 | f_budget | 1 | money ~ credit |
| G3 | f_car_loan_closed | 1 | loan ~ credit |
| G3 | f_emi | 1 | loan ~ credit |
| G3 | f_fund_goal | 1 | money |
| G3 | f_fund_old | 1 | money |
| G3 | f_salary_new | 1 | money |
| G3 | l_aws_goal | 10 | fill |
| G3 | l_aws_prereq | 2 | 'credit score' vs 'score at least 80%' |
| G3 | l_aws_progress | 2 | 'credit score' vs 'scored 68%' |
| G3 | p_anniv | 8 | hub record |
| G3 | w_task_runbook | 10 | fill |
| G4 | d_billing_vendor, d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (9) |
| G4 | f_salary_new | 1 | career pay |
| G4 | l_aws_goal | 1 | 'next year' ~ March 2027 |
| G4 | l_aws_prereq | 10 | fill |
| G4 | w_manager | 2 | 'engineering manager role' vs Suresh 'manager' |
| G4 | w_task_demo | 11 | the next milestone of the way to the role; gold accepts w_proj_rp/w_goal_link |
| G5 | d_billing_vendor, d_pause_rust, d_pgqueue, i_demo, i_fee, i_payflow_followup, i_runbook | 7 | standing block: added whatever the question (7) |
| G5 | f_budget | 10 | fill |
| G5 | f_fund_old | 10 | fill |
| G5 | f_salary_new | 10 | fill |
| G5 | p_back | 8 | hub record |
| G5 | p_constraint_travel | 11 | the care burden behind the caregiver idea; gold accepts p_mother_care |
| G5 | p_inferred_hobby | 8 | hub record |
| G5 | w_inferred_jobchange | 8 | hub record |
| G6 | d_caregiver, d_pause_rust, d_pgqueue, i_clinic, i_demo, i_fee | 7 | standing block: added whatever the question (6) |
| G6 | f_budget | 1 | money |
| G6 | f_car_loan_closed | 1 | money |
| G6 | f_fund_goal | 1 | money |
| G6 | f_fund_old | 1 | money |
| G6 | i_runbook | 2 | 'billing' notice ~ 'Billing migration runbook' |
| G6 | l_aws_goal | 10 | fill |
| G6 | l_prereq | 10 | fill |
| G6 | w_task_runbook | 2 | 'billing notice' vs 'Billing migration runbook' |
| O6 | p_coffee | 10 | change tenant has 12 records; top-10 search takes the off-topic one |

## 2. Each cause: reproduction, code path, fix, risk

### Cause 7: decision/intention block mixed in (311 items, 49%)

**Reproduction:** A1, "How do I take my coffee?"
- **Expected:** `p_coffee`.
- **Actual:** 20 items:
  - `p_coffee`;
  - 4 decisions: `d_pgqueue`, `d_pause_rust`, `d_caregiver`, `d_billing_vendor`;
  - 5 intentions: `i_runbook`, `i_payflow_followup`, `i_demo`, `i_fee`, and `i_clinic` (keyword "take");
  - 10 other memories.
- **Precision:** 0.05.

**Why the irrelevant items got in:**
- **Current decisions:** `_decisions` adds `_current_decisions()` whatever the query (`snapshot.py:1235-1245`). That query is `snapshot.py:879-897`, `.limit(SIDE_LIMIT)` with `SIDE_LIMIT = 5` (`:231`). The tenant has only 4 current decisions, so all 4 are in every snapshot.
- **Due intentions:** `_intentions` adds `_due_intentions()` (`:1268-1273`, `:900-945`, `DUE_WINDOW = 14 days` at `:199`). All 5 seeded open intentions with a trigger fall within 14 days, so all 5 are in every snapshot.
- **The ordering prior never removes them.** `REASON_SCORE` gives them 0.21–0.22 (`:206-215`), but `apply_budget` (`:766-777`) only drops items beyond 40 items or 6,000 characters (`Budget`, `:288-297`). Snapshots peak at 22 items, so the budget never binds.
- **The block was added on purpose by the D2 fix**, to lift recall on O1, O3, O4 and O8 (audit §4 D2). It is labelled honestly: `STANDING_REASONS` never makes a snapshot sufficient (`:197`, `:1302`), and the explanation says "listed whatever the question" (`:1341-1345`). But every one of its items counts against precision.

**Proposed correction (B):**
1. Gate the block on the query's intent. Keep intentions for commitment, deadline and priority questions, and decisions for decision, priority and plan questions. Detect intent from the query's words, in English and Tamil.
2. For every other question, replace the any-word keyword match with a semantic match on `Decision.embedding` (`models/judgment.py:279`) and the intention embedding (`snapshot.py:863` defers it), with a floor. Allow at most 1–2 items.

Optional, as a contract change: move the standing items out of `items` into a separate `agenda` field that consumers treat as agenda, not evidence.

**Recall and safety risk:**
- **Four required records come only from the standing block.** They are A2 `i_clinic`, D1 `d_pause_rust`, F1 `i_clinic` and F2 `i_demo`.
- **The rule alone costs recall.** With rule-gating plus the existing keyword path, my simulation gives precision **0.39** and micro recall **0.94 → 0.90** (91/97 → 87/97). Semantic matching must recover those four.
- **O6 change detection depends on the block.** `intention_approaching:i_runbook` and the `d_pgqueue` → `d_kafka` supersession come through it (D5 depended on D2), and `changes.py` diffs snapshots. Keep the block in changes mode.
- **The eval does not seed decision or intention embeddings yet.** Only memories are seeded (`eval_context_quality.py:260`). Whether production writes them must be checked before relying on them.

### Cause 1: loose semantic similarity (103 items, 16%)

**Reproduction:** C3, "How big is our emergency fund?"
- **Expected:** `f_fund_old`; acceptable `f_fund_goal` and `f_sip`.
- **Actual noise:**
  - loose neighbours: `f_budget`, `f_car_loan_closed`, `f_emi`, `f_injection`, `f_salary_new`. All are finance, and none answers the question.
  - filler: `l_aws_prereq`, `w_job_new`, `p_anniv`, and the standing 9.

**Why the irrelevant items got in:**
- `retrieve()` asks `hybrid_search` for `CANDIDATES = 10` (`retrieval.py:33`, `:818-826`).
- The fusion is Reciprocal Rank Fusion, normalised by rank (`postgres.py:642-649`, `RRF_K = 60`, `:54`). Its scores say how high a record ranked, not how similar it is, and `LIMIT :result_limit` always returns 10 if 10 exist.
- `judge=False` (`snapshot.py:1177-1183`) takes the unjudged path, which returns every candidate (`retrieval.py:916-931`). The snapshot passes `limit=budget.max_items=40`, so nothing slices the result to fewer than the candidates.
- **The module itself states that no score threshold separates relevant from unrelated** (`retrieval.py:3-6`, `evals/score-separability.md`). The judge that removes these items is exactly what the snapshot turns off.

**Proposed correction (A + F):**
- Expose the raw cosine from the vector leg alongside the RRF rank.
- Cut at a relative gap (for example, keep hits within Δ of the top cosine, with a minimum of 1 and a maximum of K).
- Alternatively, use a deterministic local cross-encoder reranker. This is a contract change: "No model is called" (`snapshot.py:12-17`).

**Risk:**
- Questions that need many records lose recall. O9 needs 7 records, O1 needs 8.
- A paraphrase with no word overlap leans on the vector leg.
- Every threshold must be tuned on a held-out split, not on these 45 questions.

### Cause 10: ranking / top-K fill (73 items, 12%)

**Reproduction:** A4, "When is our wedding anniversary?"
- **Expected:** `p_anniv`, one record.
- **Actual:** 10 search hits, for example `f_budget`, `f_car_loan_closed`, `f_fund_goal`, `f_fund_old`, `f_salary_new` and `l_aws_prereq`, plus the standing 9. Precision 0.05.
- **Second reproduction:** G3, "credit score". `insufficient=True` is correct, but the snapshot still returns 20 items (`snapshot.py:1421-1435` returns `kept` whatever `is_insufficient` says), and all 20 count as noise.

**Why the irrelevant items got in:**
- The search leg uses the same fixed K=10 as cause 1.
- Expansion runs from the top 5 seeds whether or not those seeds are relevant: neighbours via `LINK_SEEDS = 5`, `LINKED_CANDIDATES = 6` (`retrieval.py:37-39`, `:886-887`, `:154-167`), and entity links via `ENTITY_CANDIDATES = 8` (`:35`, `:849-866`).
- Example: A1's `w_job_new` is the ASSOCIATED ("promotion") neighbour of `f_salary_new`, which itself matched only on the word "take".

**Proposed correction (F, adaptive budget):**
- Size K to the query's shape: a single-fact "what/when/who is X" question gets 3 items; a list, priority or summary question gets 10.
- Take the score gap from cause 1 into account.
- Expand only from seeds above the floor.
- When the snapshot is `insufficient`, return only the standing agenda, or no answering items at all.

**Risk:**
- Recall on wide questions that look narrow.
- G3 and O10 explanations then carry no records, which is the honest answer.

### Cause 8: generic personal info in an unrelated question (60 items, 10%)

**Reproduction:** B1, "What is my current job title?"
- **Expected:** `w_job_new`.
- **Actual noise includes:** `p_anniv`, `p_constraint_travel`.

**Why the irrelevant items got in:** a handful of short first-person or "The owner …" sentences are *hubs*, close in vector space to almost any first-person question. Across the 45 questions:

| Record | Questions where it is noise |
|---|---|
| `p_constraint_travel` | 21 |
| `p_back` | 15 |
| `w_inferred_jobchange` | 15 |
| `p_inferred_hobby` | 12 |

In RRF, a vector-only hit still earns `vw/(k+rank)` with no keyword support (`postgres.py:642-647`), so a hub ranks in the top 10 with no word of the question.

**Proposed correction (D, noise reduction):**
- Add a hubness penalty, for example cross-domain similarity local scaling: subtract each record's mean similarity to a fixed set of generic probe queries.
- Or require either keyword support or a cosine above the gap floor for any vector-only hit below rank 3.

**Risk:**
- Hub records are sometimes the answer. `p_back` is required for E4.
- So this must be a penalty, not a drop. Check E4, G1 and G2, where `w_inferred_jobchange` and `p_inferred_hobby` are gold.

### Cause 2: keyword overlap, different meaning (60 items, 10%: 48 memories, 12 decisions/intentions)

**Reproduction:** E4, "Am I still on leave from work?"
- **Expected:** `p_back`.
- **Actual noise:**
  - `w_inferred_jobchange` ("leave" Kovai);
  - `w_not_leaving` ("leaving");
  - `w_blocker` ("still has not given").

**Other reproductions on the decision/intention side:**
- D2: `i_aws_book` matches "book" (Rust book vs booking an exam).
- G1 and B1: `d_pgqueue` matches "job" (a job search vs a job queue).
- A1, C1 and O10: `i_clinic` matches "take".

**Why the irrelevant items got in:**
- **Memories:** the keyword leg matches ANY content word, ranked by BM25 inverse document frequency, then fused by rank (`postgres.py` `hybrid_search`, `_or_tsquery`). One shared stemmed word gives a rank, and RRF turns any rank into credit.
- **Decisions and intentions:** `_tsquery` ORs every word of the query (`snapshot.py:811-818`, used at `:821-839` and `:855-876`). English stemming joins:
  - book / booking / booked;
  - leave / leaving;
  - run / running;
  - take / takes / take-home.

**Proposed correction (B/E):**
- **Decisions and intentions:** require at least 2 content words, or a semantic match above a floor, instead of any one word.
- **Memories:** give no keyword credit for a match on a single word that is common in the tenant (low inverse document frequency) when the vector rank is poor.
- **An evidence check:** `assess_candidate_evidence`, `retrieval.py:371`, is already computed per memory and dropped by the snapshot.

**Risk:**
- Name and rare-term lookups gained a lot from the keyword leg (77% → 97% top-5, `postgres.py` docstring). Keep rare words at full weight.
- Tamil questions have no keyword leg at all (`mostly_tamil`), and D10 shows how fragile tokenising is.

### Cause 11: scoring artefact, gold too narrow (10 items, 2%)

These are defensible and arguably should be acceptable:

| q | Records | Why defensible |
|---|---|---|
| O1 | `w_not_leaving` | Owner-stated career aim. |
| O2 | `f_budget`, `p_run` | A spending target the owner set; the training habit behind the marathon goal. |
| O3 | `l_aws_goal` | The parent plan of the required `i_aws_book`. |
| O4 | `p_constraint_travel` | An owner rule set 25 days ago; the gold already accepts `f_car_loan_closed`, 26 days old. |
| O10 | `p_mother_care`, `w_job_new` | Dependants' costs and employment both bear on a second loan. |
| C5 | `f_husband_income_new` | The gold already accepts `f_salary_new`. |
| G4 | `w_task_demo` | The next milestone on the way to the role. |
| G5 | `p_constraint_travel` | The care burden behind the caregiver idea. |

**Why they count as noise:** the gold sets in `questions.json` are hand-drawn. Scoring treats anything outside required ∪ acceptable ∪ forbidden as noise (`eval_context_quality.py:512-513`, `:529`).

**Proposed correction:** have a second person, blind to the run, re-label the acceptable sets. Record every change with its reason.

**Risk:**
- **Gaming**, if the gold is widened to hit a target.
- **Little gain:** the effect is small, +0.012 overall (from 210/839 to 220/839).

### Cause 9: query ambiguity (8 items, all in O)

**Reproduction:** O3, "Which of my commitments are still not done?"
- **Expected:** six intentions.
- **Actual noise:**
  - financial "commitments": `f_budget`, `f_fund_goal`, `f_car_loan_closed`;
  - an ongoing project: `w_proj_billing`.
- **Related reproductions:**
  - O4 "decide recently": `f_budget`, `l_aws_goal` and `p_goal_marathon` read as decisions;
  - O8: `p_pickup` read as a deadline (a weekday duty).

**Why:** retrieval has no notion of record type, so a word with several readings ranks records for every reading.

**Proposed correction (B):** an intent → record-type map, so commitment means intention rows or task memories and decision means decision rows. Also tighten the gold wording.

**Risk:** low. A wrong intent costs recall on that question.

### Cause 3: historical record competing with the current one (4 items)

**Reproduction:** E5 (also O3, O8 and F4).
- **Expected:** `i_demo`, `w_task_demo`; acceptable `w_dep_done`.
- **Actual:** `w_dep` ("Route Planner v2 depends on the maps team …") is also present. It is resolved, but still active.

**Why:**
- Nothing marks it resolved: no supersession and no `valid_until`.
- Retrieval filters only on status, supersession and valid time (`retrieval.py:893-901`, `visible_at`).
- The `RELATED_TO` link to `w_dep_done` is read only after selection, for display (`snapshot.py:1116-1160`).

**Proposed correction (C):**
- At selection time, demote a record that a newer kept record resolves.
- This needs a link type with that meaning: `RELATED_TO` is too generic, so add `RESOLVES`, or supersede at ingestion.

**Risk:**
- B3 asks about the dependency itself, and `w_dep` is required there. So demote, never drop.

### Causes 4 and 5: no noise items

- **Cause 4, state:** superseded, expired, pending, hostile, completed and discarded records never appear: forbidden-as-current is 0 in both arms. The filters are `snapshot.py:1189-1195` and `retrieval.visible_at`. They show up only in `exclusions`.
- **Cause 5, duplicates:** near-duplicate clusters do exist:
  - `w_task_runbook` / `i_runbook`;
  - `w_task_demo` / `i_demo`;
  - `p_mother_care` / `p_saturday` / `i_clinic`.

  The gold accepts both copies wherever they are relevant, so they never count as noise. In unrelated questions such as A3 and F5, the clinic cluster shows up as cause 8 or 10 filler. Collapsing duplicates (D) would save 1–2 slots there.

## 3. Items returned vs relevant, per question (bge-m3)

Columns: items in the snapshot; standing items (current_decision + due_intention, never question-dependent); items that are required or acceptable (ok); required found / required; gold size (|required ∪ acceptable|); noise; precision; the best precision a snapshot of *this size* could reach (min(gold, items)/items).

| q | items | standing | ok | req found | gold size | noise | P | P ceiling at this size |
|---|---|---|---|---|---|---|---|---|
| O1 | 19 | 9 | 13 | 6/8 | 25 | 6 | 0.68 | 1.00 |
| O2 | 19 | 9 | 7 | 3/4 | 13 | 12 | 0.37 | 0.68 |
| O3 | 20 | 8 | 6 | 5/6 | 11 | 14 | 0.30 | 0.55 |
| O4 | 19 | 9 | 6 | 2/2 | 8 | 13 | 0.32 | 0.42 |
| O5 | 21 | 9 | 6 | 1/1 | 9 | 15 | 0.29 | 0.43 |
| O7 | 20 | 9 | 8 | 2/2 | 9 | 12 | 0.40 | 0.45 |
| O8 | 22 | 9 | 7 | 4/4 | 8 | 15 | 0.32 | 0.36 |
| O9 | 19 | 7 | 9 | 7/7 | 11 | 10 | 0.47 | 0.58 |
| O10 | 20 | 8 | 6 | 3/4 | 9 | 14 | 0.30 | 0.45 |
| A1 | 20 | 8 | 1 | 1/1 | 1 | 19 | 0.05 | 0.05 |
| A2 | 19 | 9 | 6 | 3/3 | 6 | 13 | 0.32 | 0.32 |
| A3 | 19 | 8 | 4 | 1/1 | 4 | 15 | 0.21 | 0.21 |
| A4 | 20 | 9 | 1 | 1/1 | 1 | 19 | 0.05 | 0.05 |
| A5 | 19 | 9 | 4 | 2/2 | 4 | 15 | 0.21 | 0.21 |
| B1 | 19 | 8 | 3 | 1/1 | 5 | 16 | 0.16 | 0.26 |
| B2 | 19 | 9 | 3 | 1/1 | 4 | 16 | 0.16 | 0.21 |
| B3 | 19 | 7 | 7 | 2/2 | 7 | 12 | 0.37 | 0.37 |
| B4 | 19 | 8 | 6 | 2/2 | 6 | 13 | 0.32 | 0.32 |
| B5 | 20 | 9 | 4 | 1/1 | 6 | 16 | 0.20 | 0.30 |
| C1 | 20 | 8 | 5 | 1/1 | 5 | 15 | 0.25 | 0.25 |
| C2 | 20 | 9 | 3 | 1/1 | 3 | 17 | 0.15 | 0.15 |
| C3 | 20 | 9 | 3 | 1/1 | 3 | 17 | 0.15 | 0.15 |
| C4 | 20 | 9 | 4 | 2/2 | 4 | 16 | 0.20 | 0.20 |
| C5 | 20 | 8 | 5 | 1/1 | 5 | 15 | 0.25 | 0.25 |
| D1 | 20 | 9 | 6 | 3/3 | 9 | 14 | 0.30 | 0.45 |
| D2 | 20 | 8 | 4 | 1/1 | 4 | 16 | 0.20 | 0.20 |
| D3 | 20 | 8 | 5 | 3/3 | 5 | 15 | 0.25 | 0.25 |
| D4 | 19 | 9 | 3 | 1/1 | 3 | 16 | 0.16 | 0.16 |
| E1 | 1 | 0 | 1 | 1/1 | 1 | 0 | 1.00 | 1.00 |
| E2 | 3 | 0 | 1 | 1/1 | 1 | 2 | 0.33 | 0.33 |
| E3 | 21 | 8 | 2 | 1/1 | 2 | 19 | 0.10 | 0.10 |
| E4 | 19 | 9 | 1 | 1/1 | 1 | 18 | 0.05 | 0.05 |
| E5 | 19 | 7 | 5 | 2/2 | 5 | 14 | 0.26 | 0.26 |
| F1 | 19 | 9 | 6 | 4/4 | 6 | 13 | 0.32 | 0.32 |
| F2 | 20 | 9 | 7 | 4/5 | 11 | 13 | 0.35 | 0.55 |
| F3 | 19 | 8 | 2 | 2/2 | 3 | 17 | 0.11 | 0.16 |
| F4 | 20 | 7 | 7 | 2/2 | 7 | 13 | 0.35 | 0.35 |
| F5 | 19 | 8 | 3 | 2/2 | 4 | 16 | 0.16 | 0.21 |
| G1 | 19 | 8 | 3 | 1/1 | 4 | 16 | 0.16 | 0.21 |
| G2 | 20 | 9 | 1 | 1/1 | 1 | 19 | 0.05 | 0.05 |
| G3 | 20 | 9 | 0 | 0/0 | 0 | 20 | 0.00 | 0.00 |
| G4 | 19 | 9 | 5 | 1/1 | 6 | 14 | 0.26 | 0.32 |
| G5 | 19 | 8 | 5 | 1/1 | 5 | 14 | 0.26 | 0.26 |
| G6 | 19 | 6 | 5 | 1/1 | 5 | 14 | 0.26 | 0.26 |
| O6 | 12 | 2 | 11 | 4/4 | 11 | 1 | 0.92 | 0.92 |
| **all** | **839** | | **210** | | | **629** | **0.25** | **0.30** |

**Where the size is set:**

| Knob | Where | Effect here |
|---|---|---|
| `Budget(max_items=40, max_chars=6000, item_chars=300)` | `snapshot.py:288-297`, applied `:766-777`, `:1407` | Never binds (peak 22 items). |
| `retrieve(limit=budget.max_items)` | `snapshot.py:1177-1183` | 40, so it does not cut. |
| `CANDIDATES = 10` search hits | `retrieval.py:33`, `:821` | **The real memory size.** |
| `ENTITY_CANDIDATES = 8`, `LINK_SEEDS = 5`, `LINKED_CANDIDATES = 6` | `retrieval.py:35-39` | +0–3 expansions. |
| `SIDE_LIMIT = 5` for current decisions, due intentions and open-intention keywords; `SIDE_LIMIT * 2` for keyword decisions | `snapshot.py:231`, `:834`, `:871`, `:892`, `:945` | 4 + 5 standing items. |
| `DUE_WINDOW = 14 days` | `snapshot.py:199` | Every seeded timed intention is "due". |
| No score floor anywhere | `postgres.py:642-649` (rank fusion) | Always fills K. |

**Typical snapshot:**
- 10 search hits + 0–3 expansions + 4 decisions + 5 intentions = **19–22 items**.
- The gold relevant set has a median of 5 (range 0–25), and there are 1–2 required records in 32 of 45 questions.
- The as_of questions (E1 and E2) show the contrast: there, the `created_at <= ref` filter removes the standing block and most memories, leaving 1 and 3 items, with precision 1.00 and 0.33.

## 4. Approaches A–F: which causes each one addresses, and a precision ceiling

The ceilings are computed from this run by removing the noise of the causes each approach addresses. "Optimistic" assumes no gold item is lost.

| Approach | Addresses causes | Alone (estimate) | Notes |
|---|---|---|---|
| **A** Ranking by relevance, confidence, freshness and evidence | 1, 10, part of 8, 3 (freshness), part of 2 | **≈0.25–0.32** | Ordering alone changes nothing, because the budget never binds. A matters only with a cutoff (F). Removing all 10 + 8 memory noise and half of cause 1 gives 210/654 = 0.32: the standing block still dominates. |
| **B** Query-aware type filtering (standing-block gating, intent → type, semantic matching of decisions/intentions) | 7, the 12 decision/intention items of 2, 9; recall for O2 `l_aws_goal` and O3 `i_aws_book` | **0.39–0.40** | Simulated rule (intentions only for O1/O3/O8, decisions only for O1/O4/O5, keyword noise removed): P 0.388, recall 0.94 → 0.90 (91/97 → 87/97: 4 required records lost). With semantic matching recovering them: P 0.393, recall unchanged. Oracle (all 311 cause-7 items gone, nothing lost): 0.398. |
| **C** Structured selection via typed links | 3, 6 (the F2 miss), "luck" hits | ≈0.25 → 0.26 directly | Small direct gain (4 items). Its value is that it lets K shrink without losing linked records (goal → project → task). It needs typed links that ingestion does not write today (audit §5: production has 180 links, all ASSOCIATED). |
| **D** Dedupe and noise reduction (hubness penalty, near-duplicate collapse) | 8, 5, part of 10 | ≈0.27 alone, +0.07 on top of B | Removing all 60 cause-8 items gives 210/779 = 0.27 alone. |
| **E** Evidence-aware selection (use the per-memory evidence `retrieve` already computes; trust tier; inferred/outside labels) | Part of 8 (inferred hubs: 27 items), part of 2 (`f_injection` ×5, entailment), part of 1 | ≈+0.02–0.04 | Demote only: `w_inferred_jobchange` and `p_inferred_hobby` are gold for G1 and G2, `f_injection` for G6. |
| **F** Adaptive budget (K by query shape, score-gap cutoff, nothing extra when insufficient) | 10, most of 1, G3/O10 payloads | ≈0.27 alone, +0.14 on top of B | Fixes the 0.30 size ceiling, which no other approach can lift. |

**Combined (B + semantic matching, D, F, A as cutoff, E):**

| Scenario | Precision | Recall |
|---|---|---|
| B + remove the memory noise of causes 8 and 10 | 0.53 | – |
| + gold fixes (cause 11) | 0.56 | – |
| + remove causes 2 and 3 | **0.65** | 0.94 (optimistic) |
| Everything except cause 1, with gold fixes | 0.68 | – |
| 0.70 needs, on top | ≥ 0.70 | – |

- **The 0.70 line:** on top of the 0.65 scenario, at least 23 of the 103 cause-1 items (22%) must also go, with zero loss of gold items.
- **Realistic deterministic estimate:** about **0.55–0.62**, assuming partial effectiveness (≈70% of causes 8/10, 50% of 2, 25% of 1, and ≈5% of gold memories lost).

## 5. Are precision ≥ 0.70 and recall ≥ 0.90 reachable without gaming?

**On this dataset, arithmetically yes; with today's deterministic toolset, probably not; honestly, only with one of two design changes and a held-out check.**

1. **The size ceiling must go first.**
   - At the current 19–22 items, the best possible precision is 0.30.
   - At 0.70, the 210 gold-or-acceptable items found today fit in at most about 300 items (about 6.7 per question, against 18.6 today).
   - Recall ≥ 0.90 needs about 88 of the 97 required records. They are already found today (91/97, 0.94), so the room is in cutting, not finding.
2. **B + D + F remove about 70% of the noise without touching retrieval quality.** That reaches about 0.53–0.65 and keeps recall above 0.90, provided:
   - decisions and intentions get semantic matching, so A2, D1, F1 and F2 are not lost;
   - changes mode keeps the standing block.
3. **The last stretch is cause 1, the 103 loose semantic neighbours.** They are same-topic records that do not answer, for example the finance records in C3.
   - The store's own evidence says no score threshold separates them (`retrieval.py:3-6`), and RRF scores are ranks, not similarity.
   - Separating them needs a relevance model: the existing local judge (`retrieve(judge=True)`), or a deterministic local cross-encoder.
   - Both break the snapshot's "no model, byte-identical" contract (`snapshot.py:12-19`). That is an owner or ADR decision, not a tuning knob.
4. **Ways it could be gamed, which should be refused:**
   - word lists or per-category K tuned to these 45 questions;
   - widening the gold sets (cause 11 is worth only +0.012 and should be re-labelled blind);
   - dropping standing items from the denominator without moving them out of `items` in the contract.

**The honest protocol has four parts:**
1. Freeze the thresholds on a split, for example tune on A–D and test on E–G and O, or tune on the ingest arm.
2. Report two numbers: precision of answering items, and precision of all items.
3. Keep the per-category recall floors and the zero-tolerance gates.
4. Add per-item key, reason and score to `report.json`, so this analysis does not have to infer reasons again.

**Bottom line:**
- **Deterministic ceiling:** precision about 0.55–0.62 at recall ≥ 0.90, with B + D + F + A-as-cutoff, and no model.
- **≥ 0.70 / ≥ 0.90** is credible only with a local relevance reranker or judge in the snapshot path, proven on a held-out split.
