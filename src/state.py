from typing import Dict, Any

_SESSION_STORE: Dict[str, Dict[str, Any]] = {}

def init_state() -> Dict[str, Any]:
    return {
        "history": [],
        "last_query_text": None,
        "last_query_embedding": None,
        "last_results": [],
        "shown": 0,
        "page_size": 5,
        "last_limit": 5,
        "last_focus": [],
        "active_topic": None,
        "records": [],
        "cursor": 0,
        "output_mode": "full",
        "active_tafsir": "all",
        "score_threshold": 0.70
    }

def get_state(session_id: str) -> Dict[str, Any]:
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = init_state()
    return _SESSION_STORE[session_id]

def reset_state(session_id: str) -> None:
    _SESSION_STORE[session_id] = init_state()
