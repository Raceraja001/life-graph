"""Classify every bge-m3 noise item of the context-quality baseline into one root cause.

Read-only: reads the baseline report + dataset/questions, writes generated tables.
"""
import collections
import json
import sys

SP = "/mnt/c/Users/FusionGamingMasterPc/AppData/Local/Temp/claude/9730f2128050b369/8151da67-1a35-4b43-aee5-184c5b146179/scratchpad/prec"
WT = "/home/raja/worktrees/life-graph/prec-baseline"
R = json.load(open(f"{SP}/baseline_report.json"))
Q = {q["id"]: q for q in json.load(open(f"{WT}/evals/context_quality/questions.json"))["questions"]}
DS = json.load(open(f"{WT}/evals/context_quality/dataset.json"))

CAUSES = {
    1: "loose semantic similarity",
    2: "keyword overlap, different meaning",
    3: "historical record competing with current",
    4: "pending/rejected/superseded/expired",
    5: "duplicate / near-duplicate",
    6: "missing relationship",
    7: "decision/intention block mixed in",
    8: "generic personal info, unrelated question",
    9: "query ambiguity",
    10: "ranking / top-K fill",
    11: "scoring artefact (gold too narrow)",
}

# Decisions / intentions that came in through the KEYWORD path (reason
# "decision" / "open_intention"), worked out from snapshot._tsquery (any word)
# against the titles; every count matches the per-question reason counts.
KW_DI = {
    ("O3", "d_pause_rust"): "'done' in 'until the AWS exam is done'",
    ("O9", "d_caregiver"): "'consider' ~ 'Considered after the October hospital stay'",
    ("B1", "d_pgqueue"): "'job' ~ 'Postgres job queue'",
    ("C5", "d_pgqueue"): "'much' ~ 'costs too much to run'",
    ("E3", "d_pgqueue"): "'running' ~ 'too much to run'",
    ("E5", "d_pgqueue"): "'Route Planner v2' (project words, not the demo)",
    ("G1", "d_pgqueue"): "'job' ~ 'Postgres job queue'",
    ("O10", "i_clinic"): "'take' ~ 'Take Kamala to the clinic'",
    ("A1", "i_clinic"): "'take' (my coffee) ~ 'Take Kamala'",
    ("C1", "i_clinic"): "'take(-home)' ~ 'Take Kamala'",
    ("D2", "i_aws_book"): "'book' (Rust book) ~ 'Book the AWS exam slot'",
    ("G6", "i_runbook"): "'billing' notice ~ 'Billing migration runbook'",
}

# Memory noise: (cause, why). Every memory noise item of the bge-m3 arm.
M = {
 "O1": {"f_fund_old": (10, "savings figure, no tie to priorities"),
        "f_injection": (2, "external email says 'top priority' (injection bait)"),
        "w_inferred_jobchange": (8, "inferred career guess, hub record"),
        "w_job_new": (1, "'current' job state, not a priority"),
        "w_not_leaving": (11, "owner-stated career aim; gold accepts w_goal_link")},
 "O2": {"f_budget": (11, "owner-stated money target ('I want to keep ... under'); gold accepts f_fund_old"),
        "p_constraint_travel": (1, "constraint, not a goal"),
        "p_inferred_hobby": (1, "inferred interest, not an active goal"),
        "p_run": (11, "training habit behind the marathon goal; gold accepts l_aws_progress for AWS")},
 "O3": {"f_budget": (9, "'commitments' read as financial commitments"),
        "f_car_loan_closed": (9, "a financial commitment that is done"),
        "f_fund_goal": (9, "savings goal read as commitment"),
        "f_fund_old": (10, "fill"),
        "l_aws_goal": (11, "dated plan whose child i_aws_book is required"),
        "p_back": (8, "hub record"),
        "p_constraint_travel": (1, "'can't ... until' ~ 'not done'"),
        "w_blocker": (1, "blocked work, shares 'still'"),
        "w_dep": (3, "resolved dependency still active beside w_dep_done"),
        "w_proj_billing": (9, "ongoing project read as a commitment")},
 "O4": {"f_budget": (9, "owner rule, 60 days old: decision-like"),
        "l_aws_goal": (9, "plan, decision-like"),
        "p_constraint_travel": (11, "owner-stated rule 25 days ago; gold accepts f_car_loan_closed (26 d)"),
        "p_goal_marathon": (9, "plan, decision-like"),
        "p_inferred_hobby": (8, "hub record"),
        "p_no_meat": (8, "hub personal rule"),
        "w_inferred_jobchange": (8, "hub record"),
        "w_proj_billing": (10, "fill")},
 "O5": {"f_budget": (10, "fill"),
        "f_car_loan_closed": (1, "something ended ~ 'replaced'"),
        "f_fund_old": (1, "value with a pending successor ~ 'replaced'"),
        "f_injection": (2, "'ignore previous instructions / OVERRIDE' ~ superseded"),
        "p_constraint_travel": (8, "hub record"),
        "p_no_meat": (8, "hub record"),
        "w_blocker": (10, "fill"),
        "w_inferred_jobchange": (8, "hub record"),
        "w_proj_billing": (1, "'moving from the old PHP system' ~ replaced"),
        "w_task_runbook": (10, "fill")},
 "O6": {"p_coffee": (10, "change tenant has 12 records; top-10 search takes the off-topic one")},
 "O7": {"f_budget": (10, "fill"), "f_fund_goal": (10, "fill"), "f_fund_old": (10, "fill"),
        "p_constraint_travel": (1, "a constraint ~ 'blocked'"),
        "w_inferred_jobchange": (8, "hub record"),
        "w_kafka_consequence": (1, "project change, not a block")},
 "O8": {"l_aws_goal": (1, "dated, months away"), "l_aws_prereq": (1, "'before booking'"),
        "p_back": (1, "dated 21 Nov, past"), "p_goal_marathon": (1, "dated, Feb 2027"),
        "p_pickup": (9, "fixed weekday duty: 'deadline' vs schedule"),
        "p_run": (1, "weekday routine"), "w_blocker": (1, "dated 4 Nov request"),
        "w_career_goal": (1, "dated, 2027"),
        "w_dep": (3, "resolved dependency"), "w_inferred_jobchange": (8, "hub record"),
        "w_proj_billing": (10, "fill")},
 "O9": {"w_job_new": (1, "promotion ~ income; f_salary_new already holds the figure"),
        "w_not_leaving": (2, "'new' job vs 'new' laptop")},
 "O10": {"l_aws_prereq": (1, "'before I can' prerequisite phrasing"),
         "l_prereq": (1, "'before starting' prerequisite phrasing"),
         "p_constraint_travel": (8, "hub record"),
         "p_mother_care": (11, "dependent's ongoing care cost bears on a second loan"),
         "p_saturday": (2, "'second Saturday' vs 'second home loan'"),
         "w_job_new": (11, "employment/role bears on loan eligibility")},
 "A1": {"f_husband_income_new": (2, "'take' (coffee) vs 'take-home pay'"),
        "f_salary_new": (2, "'take' vs 'take-home salary'"),
        "p_back": (8, "hub record"), "p_constraint_travel": (8, "hub record"),
        "p_inferred_hobby": (8, "hub record"),
        "p_mother_care": (2, "'take' vs 'takes her to the clinic'"),
        "p_no_meat": (1, "food preference, same topic"),
        "p_run": (1, "morning routine ~ morning coffee"),
        "w_inferred_jobchange": (8, "hub record"),
        "w_job_new": (10, "ASSOCIATED neighbour of keyword-matched f_salary_new ('promotion' group)")},
 "A2": {"f_budget": (10, "fill"), "f_fund_goal": (10, "fill"),
        "p_back": (8, "hub record"), "p_inferred_hobby": (8, "hub record"),
        "w_inferred_jobchange": (2, "'look after' vs 'looking to leave'"),
        "w_not_leaving": (2, "'look after' vs 'not looking for a new job'")},
 "A3": {"f_husband_income_new": (2, "'school' (Ila's) vs 'Arjun's school cut his hours'"),
        "p_back": (8, "hub record"), "p_constraint_travel": (8, "hub record"),
        "p_mother_care": (1, "another family duty with a day pattern"),
        "p_mother_hosp": (1, "family, dates"), "p_run": (1, "'which days' ~ Mon/Wed/Fri"),
        "p_saturday": (1, "'which days' ~ every second Saturday")},
 "A4": {"f_budget": (10, "fill"), "f_car_loan_closed": (10, "fill"), "f_fund_goal": (10, "fill"),
        "f_fund_old": (10, "fill"), "f_salary_new": (10, "fill"),
        "l_aws_goal": (1, "'when' ~ 'by March 2027'"), "l_aws_prereq": (10, "fill"),
        "p_goal_marathon": (1, "'when' ~ 'February 2027'"), "p_inferred_hobby": (8, "hub record"),
        "w_task_runbook": (1, "'when' ~ 'by Friday 28 November'")},
 "A5": {"f_budget": (10, "fill"), "f_fund_goal": (2, "'goals' (fitness) vs savings 'goal'"),
        "f_salary_new": (10, "fill"), "l_aws_prereq": (10, "fill"),
        "p_constraint_travel": (8, "hub record"), "p_inferred_hobby": (1, "hobby ~ habits")},
 "B1": {"f_fund_goal": (10, "fill"), "f_fund_old": (10, "fill"), "p_anniv": (8, "hub record"),
        "p_back": (1, "work status"), "p_constraint_travel": (8, "hub record"),
        "w_inferred_jobchange": (1, "'job', career, not the title"),
        "w_not_leaving": (1, "'job', career, not the title")},
 "B2": {"f_fund_goal": (10, "fill"), "f_salary_new": (10, "fill"), "p_back": (8, "hub record"),
        "p_inferred_hobby": (8, "hub record"),
        "w_goal_link": (2, "'engineering manager' role vs 'my manager' person"),
        "w_inferred_jobchange": (1, "work/career"), "w_proj_billing": (1, "work")},
 "B3": {"l_prereq": (1, "'before starting' ~ 'depend on'"), "p_back": (8, "hub record"),
        "p_constraint_travel": (1, "'until' ~ 'waiting'"),
        "w_blocker": (1, "another project's blocker, shares 'still'"),
        "w_inferred_jobchange": (8, "hub record")},
 "B4": {"f_budget": (10, "fill"),
        "f_injection": (2, "PayFlow 'billing notice' vs 'Billing migration'"),
        "p_back": (8, "hub record"), "p_constraint_travel": (8, "hub record"),
        "w_goal_link": (1, "work"), "w_inferred_jobchange": (8, "hub record"),
        "w_not_leaving": (8, "hub record")},
 "B5": {"f_budget": (10, "fill"), "f_fund_goal": (2, "career 'goal' vs savings 'goal'"),
        "f_fund_old": (10, "fill"), "f_salary_new": (1, "promotion pay, career-adjacent"),
        "l_aws_prereq": (1, "certification, career-adjacent"),
        "p_constraint_travel": (8, "hub record"),
        "p_goal_marathon": (2, "career 'goal' vs fitness goal")},
 "C1": {"f_budget": (1, "monthly money"), "f_car_loan_closed": (1, "money"),
        "f_fund_goal": (1, "money"), "f_fund_old": (1, "money"), "p_back": (8, "hub record"),
        "p_mother_care": (2, "'take(-home)' vs 'takes her'")},
 "C2": {"f_fund_goal": (1, "money"), "f_fund_old": (1, "money"), "f_salary_new": (1, "money"),
        "l_prereq": (10, "fill"), "p_back": (8, "hub record"),
        "w_blocker": (2, "'still repaying' vs 'still has not given'"),
        "w_proj_billing": (10, "fill"), "w_task_runbook": (10, "fill")},
 "C3": {"f_budget": (1, "money"), "f_car_loan_closed": (1, "money"), "f_emi": (1, "money"),
        "f_injection": (1, "money transfer email"), "f_salary_new": (1, "money"),
        "l_aws_prereq": (10, "fill"), "p_anniv": (8, "hub record"), "w_job_new": (10, "fill")},
 "C4": {"f_car_loan_closed": (1, "money"), "f_emi": (1, "money"), "f_fund_goal": (1, "money"),
        "f_fund_old": (1, "money"), "f_sip": (1, "money"), "p_anniv": (8, "hub record"),
        "w_proj_billing": (10, "fill")},
 "C5": {"f_car_loan_closed": (1, "money"), "f_fund_old": (1, "money"),
        "f_husband_income_new": (11, "household income; gold accepts f_salary_new"),
        "p_constraint_travel": (8, "hub record"), "p_no_meat": (8, "hub record"),
        "w_job_new": (10, "fill")},
 "D1": {"f_salary_new": (10, "fill"), "p_inferred_hobby": (1, "'learning' the veena, inferred"),
        "w_career_goal": (10, "fill"), "w_job_new": (10, "fill"),
        "w_not_leaving": (8, "hub record"), "w_proj_billing": (10, "fill")},
 "D2": {"f_car_loan_closed": (10, "fill"), "l_aws_goal": (1, "other course"),
        "l_aws_prereq": (2, "'Rust book' vs 'booking the AWS exam'"),
        "l_aws_progress": (1, "progress on another course"),
        "p_inferred_hobby": (1, "learning"),
        "w_kafka_consequence": (2, "'book' vs 'training she had booked'"),
        "w_task_runbook": (10, "fill")},
 "D3": {"l_mastered": (1, "learning"), "l_prereq": (1, "prerequisite of another course"),
        "l_rust_progress_new": (2, "'booking' vs 'Rust book'"),
        "l_rust_topic": (2, "'booking' vs 'Rust book'"),
        "p_constraint_travel": (8, "hub record"),
        "w_kafka_consequence": (2, "'booking' vs 'training she had booked'"),
        "w_task_runbook": (10, "fill")},
 "D4": {"f_car_loan_closed": (10, "fill"), "f_salary_new": (10, "fill"),
        "l_aws_goal": (1, "learning, not mastered"), "l_aws_prereq": (1, "learning"),
        "l_aws_progress": (1, "learning, 68%"), "p_inferred_hobby": (1, "learning"),
        "w_job_new": (10, "fill")},
 "E2": {"f_emi": (2, "'home' / 'March' in 'Home loan ... March 2034'"),
        "f_husband_income_old": (1, "husband's take-home pay, other person (as_of history)")},
 "E3": {"f_fund_old": (1, "money"), "l_prereq": (10, "fill"), "p_back": (8, "hub record"),
        "p_constraint_travel": (8, "hub record"),
        "p_goal_marathon": (2, "'running' (loan) vs 'run the half marathon'"),
        "p_run": (2, "'running' vs 'runs 5 km'"),
        "w_blocker": (2, "'still' (running) vs 'still has not given'"),
        "w_inferred_jobchange": (8, "hub record"), "w_proj_billing": (10, "fill"),
        "w_task_runbook": (10, "fill")},
 "E4": {"f_car_loan_closed": (10, "fill"), "f_salary_new": (10, "fill"),
        "p_constraint_travel": (1, "work + family status"), "p_no_meat": (8, "hub record"),
        "p_run": (8, "hub record ('before work')"), "p_saturday": (8, "hub record"),
        "w_blocker": (2, "'still on leave' vs 'still has not given'"),
        "w_inferred_jobchange": (2, "'on leave' vs 'looking to leave'"),
        "w_not_leaving": (2, "'on leave' vs 'not leaving'")},
 "E5": {"l_aws_goal": (1, "dated"), "l_mastered": (10, "fill"), "l_rust_topic": (10, "fill"),
        "p_goal_marathon": (1, "dated event"),
        "w_dep": (3, "resolved dependency of the same project"),
        "w_task_runbook": (1, "another dated task")},
 "F1": {"f_car_loan_closed": (1, "'October' event"), "l_aws_progress": (10, "fill"),
        "l_prereq": (2, "'why did that start' vs 'before starting async Rust'"),
        "p_back": (1, "leave/back to work"), "p_daughter_school": (1, "family"),
        "w_task_runbook": (10, "fill")},
 "F2": {"f_fund_goal": (2, "'goal' (career) vs savings goal"),
        "f_salary_new": (1, "promotion pay, career"), "l_aws_goal": (1, "career-adjacent plan"),
        "l_aws_prereq": (10, "fill"),
        "w_manager": (2, "'engineering manager' role vs Suresh 'the owner's manager'")},
 "F3": {"f_fund_old": (10, "fill"),
        "l_mastered": (2, "'Postgres queue' vs 'PostgreSQL query tuning'"),
        "p_coffee": (10, "fill"), "p_constraint_travel": (8, "hub record"),
        "p_saturday": (8, "hub record"), "w_inferred_jobchange": (8, "hub record"),
        "w_job_new": (10, "fill"), "w_not_leaving": (8, "hub record"),
        "w_proj_billing": (1, "tech migration ~ 'instead of'")},
 "F4": {"f_fund_goal": (10, "fill"), "l_aws_goal": (10, "fill"),
        "l_prereq": (1, "'before starting' ~ held up"),
        "p_constraint_travel": (1, "'can't ... until' ~ held up"),
        "w_dep": (3, "resolved dependency competes as the 'held up' project"),
        "w_manager": (1, "work"), "w_proj_rp": (2, "'project' word, other project")},
 "F5": {"f_car_loan_closed": (2, "'paid' (fee) vs 'paid off the car loan'"),
        "f_husband_income_new": (2, "'school' vs 'Arjun's school'"),
        "p_constraint_travel": (8, "hub record"),
        "p_husband_job": (2, "'school' vs 'Government Higher Secondary School'"),
        "p_mother_care": (8, "hub family record"), "p_mother_hosp": (8, "hub family record"),
        "p_saturday": (8, "hub family record"), "w_task_runbook": (1, "'when must' ~ 'by Friday'")},
 "G1": {"f_car_loan_closed": (10, "fill"), "f_salary_new": (1, "career/pay"),
        "l_mastered": (10, "fill"), "p_back": (1, "job status"),
        "p_inferred_hobby": (8, "hub record"),
        "w_dep": (2, "'new' job vs 'new geocoding API'"),
        "w_dep_done": (2, "'new' job vs 'new geocoding API'")},
 "G2": {"f_budget": (2, "'want' (to learn) vs 'want to keep spending'"),
        "l_aws_goal": (1, "learning plan"), "l_aws_prereq": (2, "'want' vs 'I want to score'"),
        "l_prereq": (1, "'wants to understand Rust' ~ learning wish"),
        "l_rust_topic": (1, "learning"), "p_daughter_school": (8, "hub record"),
        "p_goal_marathon": (2, "'want' vs 'wants to run'"),
        "w_career_goal": (2, "'want' vs 'I want to become'"),
        "w_goal_link": (10, "fill"), "w_not_leaving": (2, "'want' vs 'I want to grow'")},
 "G3": {"f_budget": (1, "money ~ credit"), "f_car_loan_closed": (1, "loan ~ credit"),
        "f_emi": (1, "loan ~ credit"), "f_fund_goal": (1, "money"), "f_fund_old": (1, "money"),
        "f_salary_new": (1, "money"), "l_aws_goal": (10, "fill"),
        "l_aws_prereq": (2, "'credit score' vs 'score at least 80%'"),
        "l_aws_progress": (2, "'credit score' vs 'scored 68%'"),
        "p_anniv": (8, "hub record"), "w_task_runbook": (10, "fill")},
 "G4": {"f_salary_new": (1, "career pay"), "l_aws_goal": (1, "'next year' ~ March 2027"),
        "l_aws_prereq": (10, "fill"),
        "w_manager": (2, "'engineering manager role' vs Suresh 'manager'"),
        "w_task_demo": (11, "the next milestone of the way to the role; gold accepts w_proj_rp/w_goal_link")},
 "G5": {"f_budget": (10, "fill"), "f_fund_old": (10, "fill"), "f_salary_new": (10, "fill"),
        "p_back": (8, "hub record"),
        "p_constraint_travel": (11, "the care burden behind the caregiver idea; gold accepts p_mother_care"),
        "p_inferred_hobby": (8, "hub record"), "w_inferred_jobchange": (8, "hub record")},
 "G6": {"f_budget": (1, "money"), "f_car_loan_closed": (1, "money"), "f_fund_goal": (1, "money"),
        "f_fund_old": (1, "money"), "l_aws_goal": (10, "fill"), "l_prereq": (10, "fill"),
        "w_task_runbook": (2, "'billing notice' vs 'Billing migration runbook'")},
}

arm = R["arms"]["bge-m3"]["per_question"]
rows = []  # (q, cat, key, cause, why, path)
errors = []
for qid, r in arm.items():
    cat = Q[qid]["category"]
    for k in r["noise"]:
        if k[:2] in ("d_", "i_"):
            if (qid, k) in KW_DI:
                rows.append((qid, cat, k, 2, KW_DI[(qid, k)], "keyword"))
            else:
                kind = "current_decision" if k.startswith("d_") else "due_intention"
                rows.append((qid, cat, k, 7, f"standing {kind}", kind))
        else:
            if k not in M.get(qid, {}):
                errors.append((qid, k))
                continue
            c, why = M[qid][k]
            rows.append((qid, cat, k, c, why, "memory"))
    for k in M.get(qid, {}):
        if k not in r["noise"]:
            errors.append(("extra", qid, k))
if errors:
    print("ERRORS", errors)
    sys.exit(1)

tot = len(rows)
by_cause = collections.Counter(r[3] for r in rows)
by_cat = collections.defaultdict(collections.Counter)
for r in rows:
    by_cat[r[1]][r[3]] += 1
cats = ["O", "A", "B", "C", "D", "E", "F", "G"]

out = []
out.append("### 1a. Counts per cause and category (bge-m3 arm, 629 noise items)\n")
out.append("| cause | " + " | ".join(cats) + " | total | share |")
out.append("|---|" + "---|" * (len(cats) + 2))
for c in range(1, 12):
    cells = [str(by_cat[x][c]) for x in cats]
    out.append(f"| {c}. {CAUSES[c]} | " + " | ".join(cells) + f" | **{by_cause[c]}** | {by_cause[c]/tot:.0%} |")
out.append("| **all** | " + " | ".join(str(sum(by_cat[x].values())) for x in cats) + f" | **{tot}** | 100% |")
out.append("")

# per-question summary
out.append("### 3. Items returned vs relevant, per question (bge-m3)\n")
out.append("Columns: items in the snapshot; standing items (current_decision + due_intention, never question-dependent); "
           "items that are required or acceptable (ok); required found / required; gold size (|required ∪ acceptable|); "
           "noise; precision; the best precision a snapshot of *this size* could reach (min(gold, items)/items).\n")
out.append("| q | items | standing | ok | req found | gold size | noise | P | P ceiling at this size |")
out.append("|---|---|---|---|---|---|---|---|---|")
S_items = S_ok = S_gold_cap = 0
for qid, r in arm.items():
    q = Q[qid]
    gold = len(set(q.get("required", [])) | set(q.get("acceptable", [])))
    if qid == "O6":
        sg = DS["change_scenario"]["snapshot_gold"]
        gold = len(set(sg["required"]) | set(sg["acceptable"]))
    st = r["reasons"].get("current_decision", 0) + r["reasons"].get("due_intention", 0)
    n = r["items"]
    p = r["ok_items"] / n if n else 0
    cap = min(gold, n) / n if n else 0
    S_items += n; S_ok += r["ok_items"]; S_gold_cap += min(gold, n)
    out.append(f"| {qid} | {n} | {st} | {r['ok_items']} | {r['found_required']}/{r['required']} | {gold} | {len(r['noise'])} | {p:.2f} | {cap:.2f} |")
out.append(f"| **all** | **{S_items}** | | **{S_ok}** | | | **{tot}** | **{S_ok/S_items:.2f}** | **{S_gold_cap/S_items:.2f}** |")
out.append("")

# full item table
out.append("### 1b. Every noise item (bge-m3), one primary cause each\n")
out.append("Standing decision/intention items share one cause and one code path, so they are grouped per question; "
           "every memory item and every keyword-matched decision/intention has its own row.\n")
out.append("| q | item(s) | cause | why |")
out.append("|---|---|---|---|")
for qid in arm:
    qrows = [r for r in rows if r[0] == qid]
    st = [r[2] for r in qrows if r[3] == 7]
    if st:
        out.append(f"| {qid} | {', '.join(st)} | 7 | standing block: added whatever the question ({len(st)}) |")
    for r in qrows:
        if r[3] == 7:
            continue
        out.append(f"| {qid} | {r[2]} | {r[3]} | {r[4]} |")
out.append("")
open(f"{SP}/_gen_tables.md", "w").write("\n".join(out))

# ---- numbers for the narrative
print("total", tot, dict(sorted(by_cause.items())))
for x in cats:
    print(x, dict(sorted(by_cat[x].items())), sum(by_cat[x].values()))
items_all = sum(r["items"] for r in arm.values())
ok_all = sum(r["ok_items"] for r in arm.values())
print("items", items_all, "ok", ok_all, "P", ok_all / items_all)

# ---- ceilings: remove noise of given causes, optionally add cause-11 to ok
def ceil(remove, fix11=False):
    rem = sum(by_cause[c] for c in remove)
    ok = ok_all + (by_cause[11] if fix11 else 0)
    items = items_all - rem
    return ok / items

for name, rm, f11 in [
    ("drop standing noise (7)", [7], False),
    ("7 + keyword d/i", [7], False),
    ("7,10", [7, 10], False),
    ("7,10,8", [7, 10, 8], False),
    ("7,10,8,3,5", [7, 10, 8, 3, 5], False),
    ("7,10,8 + fix11", [7, 10, 8], True),
    ("7,10,8,2 + fix11", [7, 10, 8, 2], True),
    ("7,10,8,2,9 + fix11", [7, 10, 8, 2, 9], True),
    ("all but 1 + fix11", [2, 3, 4, 5, 6, 7, 8, 9, 10], True),
]:
    print(f"ceiling {name}: {ceil(rm, f11):.3f}")

# Rule-based B: standing intentions only for O1,O3,O8; standing decisions only O1,O4,O5
keepI = {"O1", "O3", "O8", "O6"}
keepD = {"O1", "O4", "O5", "O6"}
items_b = ok_b = 0
req_tot = req_found_b = 0
lost = []
for qid, r in arm.items():
    q = Q[qid]
    req = set(q.get("required", []))
    acc = set(q.get("acceptable", []))
    okset = req | acc
    # included d/i: 4 current decisions + 5 due intentions (+ keyword i_aws_book in D2/D3), as_of questions none
    st_n = r["reasons"].get("current_decision", 0) + r["reasons"].get("due_intention", 0)
    dec = ["d_pgqueue", "d_pause_rust", "d_caregiver", "d_billing_vendor"]
    due = ["i_runbook", "i_payflow_followup", "i_clinic", "i_demo", "i_fee"]
    kw = {k for (qq, k) in KW_DI if qq == qid}
    # keyword-matched ok items (not noise) per the reason counts
    kw_ok = {"O9": {"i_fee"}, "A3": {"i_fee"}, "B3": {"d_pgqueue", "i_demo"}, "B4": {"i_runbook"},
             "D2": {"d_pause_rust"}, "D3": {"d_pause_rust", "i_aws_book"}, "E5": {"i_demo"},
             "F3": {"d_pgqueue"}, "F4": {"d_billing_vendor", "i_payflow_followup"}, "F5": {"i_fee"},
             "G5": {"d_caregiver"}, "G6": {"d_billing_vendor", "i_payflow_followup"}}.get(qid, set())
    if qid in ("E1", "E2"):
        di_in = set()
    elif qid == "O6":
        di_in = None
    else:
        di_in = set(dec) | set(due) | kw | kw_ok
    n = r["items"]; ok = r["ok_items"]
    if di_in is not None:
        drop = set()
        for k in di_in:
            via_kw = k in kw or k in kw_ok
            if k.startswith("d_") and qid not in keepD and not via_kw:
                drop.add(k)
            if k.startswith("i_") and qid not in keepI and not via_kw:
                drop.add(k)
            if k in kw and k not in okset:  # semantic matching instead of any-word keyword drops these
                drop.add(k)
        for k in drop:
            n -= 1
            if k in okset:
                ok -= 1
            if k in req:
                lost.append((qid, k))
    items_b += n; ok_b += ok
    req_tot += len(req)
    req_found_b += r["found_required"] - sum(1 for (qq, k) in lost if qq == qid)
print("B rule: P", ok_b / items_b, "items", items_b, "ok", ok_b, "recall(micro)", req_found_b / req_tot, "lost", lost)
base_req_found = sum(r["found_required"] for r in arm.values())
print("baseline recall micro", base_req_found / req_tot, req_tot)
# B + the 4 lost restored by an embedding match (assume exact)
print("B+semantic restore: P", (ok_b + len(lost)) / (items_b + len(lost)))
# B + remove memory noise of causes 10, 8 (A/D/F optimistic) + fix 11
mem_rm = sum(1 for r in rows if r[5] == "memory" and r[3] in (10, 8))
mem_rm2 = sum(1 for r in rows if r[5] == "memory" and r[3] in (10, 8, 3, 2))
n11 = by_cause[11]
print("B+sem + drop mem 8/10:", (ok_b + len(lost)) / (items_b + len(lost) - mem_rm))
print("B+sem + drop mem 8/10 + fix11:", (ok_b + len(lost) + n11) / (items_b + len(lost) - mem_rm))
print("B+sem + drop mem 2/3/8/10 + fix11:", (ok_b + len(lost) + n11) / (items_b + len(lost) - mem_rm2))
print("mem noise counts", collections.Counter(r[3] for r in rows if r[5] == "memory"))
print("mem items total", items_all - sum(r["reasons"].get("current_decision", 0) + r["reasons"].get("due_intention", 0) + r["reasons"].get("decision", 0) + r["reasons"].get("open_intention", 0) for r in arm.values()))
