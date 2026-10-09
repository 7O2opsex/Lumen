import os
from pathlib import Path

from PIL import Image


def is_supported_image(path: str) -> bool:
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def preview_file(path: str, max_size: tuple[int, int] = (200, 200)) -> dict:
    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(path)

    if image_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        with Image.open(image_path) as image:
            image.thumbnail(max_size)
            return {"width": image.width, "height": image.height, "mode": image.mode}

    return {"status": "PDF preview not generated in this version"}
