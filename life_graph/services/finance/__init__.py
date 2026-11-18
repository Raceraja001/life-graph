"""The owner's money: transactions, budgets, the check-in, and invoices.

- money: transactions from statements and bank alerts, categories, budgets
- checkin: the money check-in -- where it went, what is over (was money_checkin)
- invoices: draft, number, render, track and chase what clients owe

Named finance, not money, so services/money.py can stay an alias of
finance/money.py (a package and a module cannot share a name).

Grouped here 2026-11-18; they were flat modules in life_graph/services/.
Each old module is an alias of the new one -- the same module object --
for code on other branches. Nothing is imported here, so importing one
submodule loads only that one.
"""
