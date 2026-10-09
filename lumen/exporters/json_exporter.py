import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def export_json(data: Any, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def export_txt(data: Any, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            lines.append(f"{key}: {value}")
        content = "\n".join(lines)
    else:
        content = str(data)

    path.write_text(content, encoding="utf-8")
    return str(path)


def export_csv(rows: Iterable[Dict[str, Any]], output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    items = list(rows)
    if not items:
        path.write_text("", encoding="utf-8")
        return str(path)

    fieldnames = sorted({key for item in items for key in item.keys()})
    import csv

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({key: item.get(key, "") for key in fieldnames})

    return str(path)
