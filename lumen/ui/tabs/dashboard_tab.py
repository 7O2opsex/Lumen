from datetime import datetime


def local_dashboard_summary(history: list[dict]) -> str:
    if not history:
        return "No history available."

    items = []
    for entry in history:
        created = entry.get("created_at", str(datetime.now()))
        items.append(f"{created} :: {entry.get('kind', 'unknown')} :: {entry.get('title', 'Untitled')}")
    return "\n".join(items)
