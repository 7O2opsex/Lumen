import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from PIL import Image
from pypdf import PdfReader, PdfWriter
import piexif

from lumen.config import SUPPORTED_FILE_EXTENSIONS


def _safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_value(v) for k, v in value.items()}
    return str(value)


def _normalize_exif_dict(exif_data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in exif_data.items():
        if isinstance(value, bytes):
            try:
                cleaned[str(key)] = value.decode("utf-8", errors="ignore")
            except Exception:
                cleaned[str(key)] = str(value)
        else:
            cleaned[str(key)] = _safe_value(value)
    return cleaned


def _extract_gps_info(exif: Dict[str, Any]) -> Dict[str, Any]:
    gps = exif.get("GPSInfo")
    if not gps:
        return {}
    try:
        return {str(k): _safe_value(v) for k, v in gps.items()}
    except Exception:
        return {"raw": str(gps)}


def _extract_pdf_metadata(path: Path) -> Dict[str, Any]:
    reader = PdfReader(str(path))
    metadata = reader.metadata or {}
    if metadata is None:
        return {}

    return {
        str(key): _safe_value(value)
        for key, value in metadata.items()
    }


def extract_metadata_for_file(file_path: str) -> Dict[str, Any]:
    """Return a structured metadata dictionary for an image or PDF file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    summary: Dict[str, Any] = {
        "path": str(path),
        "file_name": path.name,
        "extension": ext,
        "type": "PDF" if ext == ".pdf" else "Image",
        "metadata": {},
    }

    if ext in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        with Image.open(path) as image:
            summary["size"] = {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format,
            }
            info = dict(image.info)
            exif_raw = image.getexif()
            summary["metadata"]["basic_info"] = {
                key: _safe_value(value)
                for key, value in info.items()
            }
            if exif_raw:
                summary["metadata"]["exif"] = _normalize_exif_dict(dict(exif_raw.items()))
                summary["metadata"]["gps"] = _extract_gps_info(summary["metadata"]["exif"])

            try:
                if hasattr(image, "getxmp"):
                    xmp = image.getxmp()
                    if xmp:
                        summary["metadata"]["xmp"] = _safe_value(xmp)
            except Exception:
                pass

            if "xmp" in info:
                summary["metadata"]["xmp_raw"] = _safe_value(info["xmp"])

    elif ext == ".pdf":
        summary["metadata"] = _extract_pdf_metadata(path)

    return summary


def clean_metadata_file(file_path: str, preserve_fields: Optional[Sequence[str]] = None, remove_all: bool = False) -> str:
    """Create a cleaned-copy metadata file and return the new path."""
    path = Path(file_path)
    ext = path.suffix.lower()
    output_path = path.with_name(f"{path.stem}_cleaned{ext}")

    if ext in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        with Image.open(path) as img:
            cleaned = Image.new(img.mode, img.size)
            cleaned.putdata(list(img.getdata()))
            if remove_all:
                cleaned.save(output_path, format=img.format or "PNG")
            else:
                cleaned.save(output_path, format=img.format or "PNG")
            if preserve_fields:
                # preserve_fields is a best-effort feature for selected metadata items.
                pass
        return str(output_path)

    if ext == ".pdf":
        reader = PdfReader(str(path))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        return str(output_path)

    raise ValueError(f"Unsupported file type for metadata cleaning: {ext}")


def read_metadata_report(file_path: str) -> str:
    """Return a pretty-printed JSON representation of file metadata."""
    data = extract_metadata_for_file(file_path)
    return json.dumps(data, indent=2, ensure_ascii=False)
