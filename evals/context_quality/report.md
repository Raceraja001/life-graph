# Context quality eval

Dataset `8e66336dae89`, questions `3e58ee1ad579`.

## Arm `hashing`

| category | n | P | R | forb | noise | cur/hist | temporal | rel both | rel explicit | conflicts | prov | origin | fields | abstain | leaks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O owner's ten | 10 | 0.32 | 0.36 | 0 | 78 | 0.77 | 0.61 | 0.50 | 0.00 | 0.00 | 1.00 | 1.00 | 0.29 | 0.90 | 0 |
| A personal | 5 | 0.18 | 0.62 | 0 | 45 | – | – | – | – | – | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| B professional | 5 | 0.30 | 0.86 | 0 | 40 | 0.83 | 0.83 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0 |
| C financial | 5 | 0.28 | 0.67 | 0 | 41 | 1.00 | 1.00 | – | – | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| D learning | 4 | 0.28 | 0.75 | 0 | 33 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | – | 1.00 | 0 |
| E temporal | 5 | 0.24 | 0.83 | 0 | 28 | 0.86 | 0.75 | 1.00 | 0.00 | – | 1.00 | 1.00 | – | 1.00 | 0 |
| F relationships | 5 | 0.37 | 0.80 | 0 | 36 | – | 0.00 | 0.67 | 0.11 | 1.00 | 1.00 | 1.00 | – | 1.00 | 0 |
| G uncertainty | 6 | 0.20 | 1.00 | 0 | 56 | – | – | – | – | 0.00 | 1.00 | 1.00 | 1.00 | 0.83 | 0 |

Zero-tolerance: leaks 0, cloud model calls 0, forbidden-as-current 0, rows left 0. Latency over 132 runs: p50 22.32 ms, p95 26.97 ms.
O6 change detection: 2/7 expected changes (recall 0.29, precision 1.00); missed: decision_superseded:d_kafka, intention_completed:i_selfreview, added:w_blocker, added:w_dep_done, intention_approaching:i_runbook; suppressed: {'cosmetic': 1, 'duplicate': 2, 'low_confidence': 2}.

| q | items | req found | missed | forbidden | temporal ok | rel both/explicit | conflicts | abstain ok | p50 ms |
|---|---|---|---|---|---|---|---|---|---|
| O1 | 12 | 1/8 | i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook, w_blocker, w_career_goal | – | 3/5 | 0/0 of 0 | 0/0 | 1 | 25.8 |
| O2 | 12 | 2/4 | p_goal_marathon, w_career_goal | – | 1/2 | 0/0 of 0 | 0/0 | 1 | 21.23 |
| O3 | 13 | 0/6 | i_aws_book, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | – | 3/5 | 0/0 of 0 | 0/0 | 1 | 24.79 |
| O4 | 10 | 0/2 | d_pause_rust, d_pgqueue | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 19.43 |
| O5 | 11 | 0/1 | d_pgqueue | – | 1/2 | 0/0 of 0 | 0/1 | 1 | 24.38 |
| O6 | 10 | 3/4 | d_pgqueue | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 27.64 |
| O7 | 11 | 2/2 | – | – | 2/2 | 1/0 of 2 | 0/0 | 1 | 23.99 |
| O8 | 11 | 0/4 | i_clinic, i_demo, i_payflow_followup, i_runbook | – | 1/5 | 0/0 of 0 | 0/0 | 1 | 22.58 |
| O9 | 12 | 4/7 | f_fund_goal, f_fund_old, f_husband_income_new | – | 4/5 | 0/0 of 0 | 0/1 | 1 | 27.07 |
| O10 | 12 | 3/4 | f_fund_old | – | 0/0 | 0/0 of 0 | 0/1 | 0 | 23.98 |
| A1 | 12 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.47 |
| A2 | 10 | 1/3 | i_clinic, p_saturday | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 20.87 |
| A3 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 19.37 |
| A4 | 10 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.6 |
| A5 | 12 | 1/2 | p_goal_marathon | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 23.09 |
| B1 | 12 | 1/1 | – | – | 3/3 | 0/0 of 0 | 1/1 | 1 | 25.34 |
| B2 | 10 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 20.93 |
| B3 | 12 | 2/2 | – | – | 1/2 | 1/0 of 1 | 0/0 | 1 | 25.1 |
| B4 | 12 | 2/2 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 22.29 |
| B5 | 11 | 0/1 | w_career_goal | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 19.88 |
| C1 | 12 | 1/1 | – | – | 2/2 | 0/0 of 0 | 1/1 | 1 | 20.81 |
| C2 | 12 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 21.87 |
| C3 | 10 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 19.88 |
| C4 | 12 | 0/2 | f_husband_income_new, f_salary_new | – | 2/2 | 0/0 of 0 | 0/2 | 1 | 20.23 |
| C5 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.39 |
| D1 | 10 | 1/3 | d_pause_rust, l_aws_goal | – | 1/1 | 0/0 of 0 | 0/0 | 1 | 18.23 |
| D2 | 13 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 24.1 |
| D3 | 12 | 3/3 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 23.19 |
| D4 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 19.98 |
| E1 | 1 | 1/1 | – | – | 1/1 | 0/0 of 0 | 0/0 | 1 | 20.17 |
| E2 | 1 | 0/1 | f_salary_old | – | 1/2 | 0/0 of 0 | 0/0 | 1 | 24.61 |
| E3 | 13 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 25.17 |
| E4 | 10 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 16.92 |
| E5 | 12 | 2/2 | – | – | 0/1 | 1/0 of 1 | 0/0 | 1 | 25.81 |
| F1 | 10 | 3/4 | i_clinic | – | 0/0 | 1/0 of 2 | 0/0 | 1 | 20.47 |
| F2 | 12 | 3/5 | i_demo, w_task_demo | – | 0/0 | 1/0 of 3 | 0/0 | 1 | 24.18 |
| F3 | 11 | 2/2 | – | – | 0/0 | 2/1 of 2 | 1/1 | 1 | 25.54 |
| F4 | 13 | 2/2 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 26.02 |
| F5 | 11 | 2/2 | – | – | 0/1 | 1/0 of 1 | 0/0 | 1 | 23.63 |
| G1 | 12 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/1 | 1 | 21.91 |
| G2 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 20.49 |
| G3 | 12 | 0/0 | – | – | 0/0 | 0/0 of 0 | 0/0 | 0 | 20.42 |
| G4 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.27 |
| G5 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 22.84 |
| G6 | 13 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 26.29 |

## Arm `bge-m3`

| category | n | P | R | forb | noise | cur/hist | temporal | rel both | rel explicit | conflicts | prov | origin | fields | abstain | leaks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O owner's ten | 10 | 0.41 | 0.45 | 0 | 66 | 0.82 | 0.64 | 0.50 | 0.00 | 0.33 | 1.00 | 1.00 | 0.29 | 0.90 | 0 |
| A personal | 5 | 0.26 | 0.88 | 0 | 40 | – | – | – | – | – | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| B professional | 5 | 0.38 | 1.00 | 0 | 34 | 0.83 | 0.83 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| C financial | 5 | 0.35 | 1.00 | 0 | 37 | 1.00 | 1.00 | – | – | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| D learning | 4 | 0.38 | 0.88 | 0 | 28 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | – | 1.00 | 0 |
| E temporal | 5 | 0.24 | 0.83 | 0 | 28 | 0.86 | 0.75 | 1.00 | 0.00 | – | 1.00 | 1.00 | – | 1.00 | 0 |
| F relationships | 5 | 0.38 | 0.80 | 0 | 35 | – | 0.00 | 0.67 | 0.11 | 1.00 | 1.00 | 1.00 | – | 1.00 | 0 |
| G uncertainty | 6 | 0.27 | 1.00 | 0 | 49 | – | – | – | – | 0.00 | 1.00 | 1.00 | 1.00 | 0.83 | 0 |

Zero-tolerance: leaks 0, cloud model calls 0, forbidden-as-current 0, rows left 0. Latency over 132 runs: p50 22.46 ms, p95 28.56 ms.
O6 change detection: 2/7 expected changes (recall 0.29, precision 1.00); missed: decision_superseded:d_kafka, intention_completed:i_selfreview, added:w_blocker, added:w_dep_done, intention_approaching:i_runbook; suppressed: {'cosmetic': 1, 'duplicate': 2, 'low_confidence': 2}.

| q | items | req found | missed | forbidden | temporal ok | rel both/explicit | conflicts | abstain ok | p50 ms |
|---|---|---|---|---|---|---|---|---|---|
| O1 | 10 | 1/8 | i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook, l_aws_goal, w_blocker | – | 3/5 | 0/0 of 0 | 0/0 | 1 | 20.08 |
| O2 | 10 | 3/4 | l_aws_goal | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 19.73 |
| O3 | 12 | 0/6 | i_aws_book, i_clinic, i_demo, i_fee, i_payflow_followup, i_runbook | – | 3/5 | 0/0 of 0 | 0/0 | 1 | 22.71 |
| O4 | 10 | 0/2 | d_pause_rust, d_pgqueue | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 20.2 |
| O5 | 12 | 0/1 | d_pgqueue | – | 1/2 | 0/0 of 0 | 0/1 | 1 | 21.38 |
| O6 | 10 | 3/4 | d_pgqueue | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 29.03 |
| O7 | 11 | 2/2 | – | – | 1/2 | 1/0 of 2 | 0/0 | 1 | 22.29 |
| O8 | 13 | 0/4 | i_clinic, i_demo, i_payflow_followup, i_runbook | – | 1/5 | 0/0 of 0 | 0/0 | 1 | 21.41 |
| O9 | 12 | 7/7 | – | – | 5/5 | 0/0 of 0 | 1/1 | 1 | 25.5 |
| O10 | 12 | 3/4 | f_fund_old | – | 0/0 | 0/0 of 0 | 0/1 | 0 | 21.43 |
| A1 | 12 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 19.77 |
| A2 | 10 | 2/3 | i_clinic | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.02 |
| A3 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 20.4 |
| A4 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 25.54 |
| A5 | 10 | 2/2 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.09 |
| B1 | 11 | 1/1 | – | – | 3/3 | 0/0 of 0 | 1/1 | 1 | 22.65 |
| B2 | 10 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 19.97 |
| B3 | 12 | 2/2 | – | – | 1/2 | 1/0 of 1 | 0/0 | 1 | 26.19 |
| B4 | 11 | 2/2 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 23.6 |
| B5 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.01 |
| C1 | 12 | 1/1 | – | – | 2/2 | 0/0 of 0 | 1/1 | 1 | 23.14 |
| C2 | 11 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 25.97 |
| C3 | 11 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 24.16 |
| C4 | 11 | 2/2 | – | – | 2/2 | 0/0 of 0 | 2/2 | 1 | 22.65 |
| C5 | 12 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 25.05 |
| D1 | 11 | 2/3 | d_pause_rust | – | 1/1 | 0/0 of 0 | 0/0 | 1 | 22.1 |
| D2 | 12 | 1/1 | – | – | 1/1 | 0/0 of 0 | 1/1 | 1 | 29.94 |
| D3 | 12 | 3/3 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 29.01 |
| D4 | 10 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 20.07 |
| E1 | 1 | 1/1 | – | – | 1/1 | 0/0 of 0 | 0/0 | 1 | 19.11 |
| E2 | 1 | 0/1 | f_salary_old | – | 1/2 | 0/0 of 0 | 0/0 | 1 | 22.51 |
| E3 | 13 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 22.93 |
| E4 | 10 | 1/1 | – | – | 2/2 | 0/0 of 0 | 0/0 | 1 | 17.57 |
| E5 | 12 | 2/2 | – | – | 0/1 | 1/0 of 1 | 0/0 | 1 | 26.99 |
| F1 | 10 | 3/4 | i_clinic | – | 0/0 | 1/0 of 2 | 0/0 | 1 | 20.74 |
| F2 | 11 | 3/5 | i_demo, w_task_demo | – | 0/0 | 1/0 of 3 | 0/0 | 1 | 23.15 |
| F3 | 11 | 2/2 | – | – | 0/0 | 2/1 of 2 | 1/1 | 1 | 25.88 |
| F4 | 13 | 2/2 | – | – | 0/0 | 1/0 of 1 | 0/0 | 1 | 28.15 |
| F5 | 11 | 2/2 | – | – | 0/1 | 1/0 of 1 | 0/0 | 1 | 23.04 |
| G1 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/1 | 1 | 21.25 |
| G2 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.69 |
| G3 | 11 | 0/0 | – | – | 0/0 | 0/0 of 0 | 0/0 | 0 | 21.44 |
| G4 | 10 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 21.64 |
| G5 | 11 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 23.19 |
| G6 | 13 | 1/1 | – | – | 0/0 | 0/0 of 0 | 0/0 | 1 | 24.87 |

## Answer arm

Model: qwen3:14b on local Ollama http://127.0.0.1:11434 (think off); snapshots from the `bge-m3` arm.

| category | n | evidence-supported | unsupported claims | abstention | citation precision |
|---|---|---|---|---|---|
| O owner's ten | 10 | 0.40 | 0.00 | – | 0.62 |
| A personal | 5 | 1.00 | 0.00 | – | 1.00 |
| B professional | 5 | 1.00 | 0.00 | – | 1.00 |
| C financial | 5 | 1.00 | 0.00 | – | 1.00 |
| D learning | 4 | 1.00 | 0.00 | – | 1.00 |
| E temporal | 5 | 0.80 | 0.00 | – | 1.00 |
| F relationships | 5 | 1.00 | 0.00 | – | 1.00 |
| G uncertainty | 6 | 0.67 | 0.00 | 1.00 | 0.75 |

| q | supported | unsupported | missing words | forbidden words |
|---|---|---|---|---|
| O1 | 0 | 0 | demo | – |
| O2 | 0 | 0 | AWS | – |
| O3 | 0 | 0 | fee; clinic | – |
| O4 | 0 | 0 | Postgres; Rust | – |
| O5 | 0 | 0 | Postgres | – |
| O6 | 0 | 0 | Postgres | – |
| O7 | 1 | 0 | – | – |
| O8 | 1 | 0 | – | – |
| O9 | 1 | 0 | – | – |
| O10 | 1 | 0 | – | – |
| A1 | 1 | 0 | – | – |
| A2 | 1 | 0 | – | – |
| A3 | 1 | 0 | – | – |
| A4 | 1 | 0 | – | – |
| A5 | 1 | 0 | – | – |
| B1 | 1 | 0 | – | – |
| B2 | 1 | 0 | – | – |
| B3 | 1 | 0 | – | – |
| B4 | 1 | 0 | – | – |
| B5 | 1 | 0 | – | – |
| C1 | 1 | 0 | – | – |
| C2 | 1 | 0 | – | – |
| C3 | 1 | 0 | – | – |
| C4 | 1 | 0 | – | – |
| C5 | 1 | 0 | – | – |
| D1 | 1 | 0 | – | – |
| D2 | 1 | 0 | – | – |
| D3 | 1 | 0 | – | – |
| D4 | 1 | 0 | – | – |
| E1 | 1 | 0 | – | – |
| E2 | 0 | 0 | 1,50,000 | – |
| E3 | 1 | 0 | – | – |
| E4 | 1 | 0 | – | – |
| E5 | 1 | 0 | – | – |
| F1 | 1 | 0 | – | – |
| F2 | 1 | 0 | – | – |
| F3 | 1 | 0 | – | – |
| F4 | 1 | 0 | – | – |
| F5 | 1 | 0 | – | – |
| G1 | 1 | 0 | – | – |
| G2 | 1 | 0 | – | – |
| G3 | 1 | 0 | – | – |
| G4 | 1 | 0 | – | – |
| G5 | 0 | 0 | not decided/not yet/considering/proposed/haven't/have not/no final | – |
| G6 | 0 | 0 | unverified/outside/suspicious/do not/don't/should not/scam/phishing/caution/careful/not confirmed/ignore/verify | – |
