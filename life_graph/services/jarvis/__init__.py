"""The Jarvis phone app's screens, one module each.

- today: the Today screen in one call (was jarvis_today)
- plan: the Plan screen, the next days one row each (was jarvis_plan)
- memory: the Memory screens (was jarvis_memory)
- cards: answer cards for the phone's chat (was jarvis_cards)
- inbox: contacts and mail waiting (was jarvis_inbox)

Grouped here 2026-11-18; they were flat modules in life_graph/services/.
Each old module is an alias of the new one -- the same module object --
for code on other branches. Nothing is imported here, so importing one
submodule loads only that one.
"""
