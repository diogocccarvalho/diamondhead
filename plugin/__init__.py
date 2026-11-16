import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import core


def register(ctx):
    core.init()
    cfg = {
        "d1_url": ctx.get_config("d1_url") or "http://127.0.0.1:8080/v1/systemone",
        "haystack_url": ctx.get_config("haystack_url") or "http://127.0.0.1:8083/query",
        "min_confidence": float(ctx.get_config("min_confidence") or 0.85),
        "inject_enabled": ctx.get_config("inject_enabled") is not False,
        "promote_n": int(ctx.get_config("promote_n") or 20),
    }

    def pre_llm_call(session_id="", user_message="", conversation_history=None,
                     is_first_turn=False, model="", platform="", **kwargs):
        t0 = time.monotonic()
        if not cfg["inject_enabled"] or not user_message:
            return None
        try:
            corr = core.note_correction(user_message)
            if corr:
                core.record_correction(corr, core.mhash(user_message))
        except Exception:
            pass
        try:
            text, conf, ms = core.choose(user_message, cfg,
                                         history=conversation_history or "")
        except Exception:
            core.log_event("chooser_crash", err=traceback.format_exc()[-200:])
            return None
        core.log_event("turn", ms=round((time.monotonic() - t0) * 1000),
                       injected=bool(text), platform=platform or "",
                       mh=core.mhash(user_message))
        return text

    def post_tool_call(tool_name="", args=None, result="", task_id="",
                       duration_ms=0, **kwargs):
        try:
            core.observe_tool(tool_name, duration_ms, task_id, args)
        except Exception:
            pass

    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_tool_call", post_tool_call)
