"""The owner's money: transactions, budgets, the check-in, and invoices.

- money: transactions from statements and bank alerts, categories, budgets
- checkin: the money check-in -- where it went, what is over (was money_checkin)
- invoices: draft, number, render, track and chase what clients owe

Named finance, not money: a package and a module cannot share a name, and
services/money.py was an alias of finance/money.py until 2026-11-24.

Grouped here 2026-11-18; they were flat modules in life_graph/services/.
The old-name aliases
were deleted on 2026-11-24 (audit L1). Nothing is imported here, so
importing one submodule loads only that one.
"""
