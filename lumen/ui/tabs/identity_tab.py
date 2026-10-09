from typing import Any


def build_identity_search_targets(name: str) -> list[dict]:
    return [
        {"label": "Name search", "query": name},
        {"label": "Username lookup", "query": name.replace(" ", "")},
    ]
