from pathlib import Path
from typing import Any


def export_txt(data: Any, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = data if isinstance(data, str) else str(data)
    path.write_text(content, encoding="utf-8")
    return str(path)
