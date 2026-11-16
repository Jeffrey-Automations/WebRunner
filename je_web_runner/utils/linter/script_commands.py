"""
會把整段腳本送進瀏覽器的命令
The commands that hand a whole script, or a raw DevTools call, to the browser. One list for the two
places that care: the executor's gate (``set_allow_arbitrary_script(False)`` refuses them) and the
linter's ``arbitrary_script`` warning. It lives with the linter because the executor imports the linter.
"""
from __future__ import annotations

ARBITRARY_SCRIPT_COMMANDS = frozenset({
    "WR_execute_script",
    "WR_execute_async_script",
    "WR_pw_evaluate",
    "WR_cdp",
    "WR_pw_cdp",
    "WR_execute_cdp_cmd",
    "WR_add_script_to_evaluate_on_new_document",
    "WR_pw_add_init_script",
})
