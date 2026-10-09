import csv
from pathlib import Path
from typing import Any, Dict, Iterable


def export_csv(rows: Iterable[Dict[str, Any]], output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)

    if not rows:
        path.write_text("", encoding="utf-8")
        return str(path)

    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    return str(path)
