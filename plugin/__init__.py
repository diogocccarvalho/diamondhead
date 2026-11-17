import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import core

_HOUSEKEEP_LOCK = threading.Lock()
_HOUSEKEEP_EVERY = 20  # turns
_TURN_COUNT = [0]


def _housekeep(cfg):
    """Runs CONCURRENTLY with turns, never on the turn's critical path:
    dreaming + candidate mining happen in a daemon thread."""
    if not _HOUSEKEEP_LOCK.acquire(blocking=False):
        return
    try:
        # resolve() is required: the plugin is symlink-installed, so __file__
        # points under ~/.hermes/plugins and .parent.parent is not the repo.
        scripts = Path(core.__file__).resolve().parent.parent / "scripts"
        sys.path.insert(0, str(scripts))
        import dream
        dream.dream()
        core.nudge_check()
    except Exception:
        core.log_event("housekeep_error", err=traceback.format_exc()[-120:])
    finally:
        _HOUSEKEEP_LOCK.release()


def register(ctx):
    core.init()
    cfg = {
        "d1_url": ctx.get_config("d1_url") or "http://127.0.0.1:8080/v1/systemone",
        "haystack_url": ctx.get_config("haystack_url") or "http://127.0.0.1:8083/query",
        "min_confidence": float(ctx.get_config("min_confidence") or 0.80),
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
        # task direction: distilled once per session, compass every turn
        direction = None
        try:
            if is_first_turn and len(user_message.strip()) >= core.DIRECTION_MIN_LEN \
                    and not core.SKIP_RE.match(user_message.strip()):
                core.set_task_direction(session_id, user_message)
            direction = core.task_direction_inject(session_id)
        except Exception:
            pass
        try:
            text, conf, ms = core.choose(user_message, cfg,
                                         history=conversation_history or "")
        except Exception:
            core.log_event("chooser_crash", err=traceback.format_exc()[-200:])
            return direction
        core.log_event("turn", ms=round((time.monotonic() - t0) * 1000),
                       injected=bool(text) or bool(direction),
                       platform=platform or "",
                       mh=core.mhash(user_message))
        if _TURN_COUNT[0] % _HOUSEKEEP_EVERY == _HOUSEKEEP_EVERY - 1:
            threading.Thread(target=_housekeep, args=(cfg,), daemon=True).start()
        _TURN_COUNT[0] += 1
        if direction and text:
            return direction + "\n" + text
        return direction or text

    def post_tool_call(tool_name="", args=None, result="", task_id="",
                       duration_ms=0, **kwargs):
        try:
            core.observe_tool(tool_name, duration_ms, task_id, args)
        except Exception:
            pass

    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_tool_call", post_tool_call)
