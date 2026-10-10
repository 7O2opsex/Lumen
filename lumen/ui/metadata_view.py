"""Readable formatting helpers for extracted file metadata."""

from __future__ import annotations

import json
from typing import Any

from PIL import ExifTags


FIELD_LABELS = {
    "path": "Emplacement",
    "file_name": "Nom du fichier",
    "extension": "Extension",
    "type": "Type",
    "size": "Dimensions",
    "width": "Largeur",
    "height": "Hauteur",
    "mode": "Mode couleur",
    "format": "Format",
    "metadata": "Métadonnées",
    "basic_info": "Informations générales",
    "exif": "EXIF",
    "gps": "Localisation GPS",
    "xmp": "XMP",
    "xmp_raw": "XMP brut",
    "raw": "Valeur brute",
    "title": "Titre",
    "author": "Auteur",
    "creator": "Créateur",
    "producer": "Logiciel producteur",
    "subject": "Sujet",
    "keywords": "Mots-clés",
    "creation_date": "Date de création",
    "modification_date": "Date de modification",
    "GPSInfo": "Localisation GPS",
    "Make": "Fabricant de l’appareil",
    "Model": "Modèle de l’appareil",
    "DateTime": "Date et heure",
    "DateTimeOriginal": "Date de prise de vue",
    "DateTimeDigitized": "Date de numérisation",
    "Software": "Logiciel",
    "Orientation": "Orientation",
    "Artist": "Photographe",
    "Copyright": "Droits d’auteur",
    "ImageDescription": "Description",
    "ExposureTime": "Temps d’exposition",
    "FNumber": "Ouverture",
    "ISOSpeedRatings": "Sensibilité ISO",
    "PhotographicSensitivity": "Sensibilité ISO",
    "FocalLength": "Distance focale",
    "Flash": "Flash",
    "ColorSpace": "Espace colorimétrique",
    "PixelXDimension": "Largeur en pixels",
    "PixelYDimension": "Hauteur en pixels",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "gpslatitude": "Latitude",
    "gpslongitude": "Longitude",
    "gpsaltitude": "Altitude",
    "gpsaltituderef": "Référence d’altitude",
    "gpsdatestamp": "Date GPS",
    "gpstimestamp": "Heure GPS",
    "CreationDate": "Date de création",
    "ModDate": "Date de modification",
    "PageLayout": "Mise en page",
    "PageMode": "Mode d’affichage",
}


def _field_label(key: Any) -> str:
    name = str(key).lstrip("/")
    if name.isdecimal():
        number = int(name)
        name = ExifTags.TAGS.get(
            number,
            getattr(ExifTags, "GPSTAGS", {}).get(number, name),
        )
    return FIELD_LABELS.get(
        str(name),
        FIELD_LABELS.get(
            str(name).casefold(),
            str(name).replace("_", " ").capitalize(),
        ),
    )


def _display_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip() or "Données binaires"
    if isinstance(value, dict):
        return "; ".join(
            f"{_field_label(key)} : {_display_value(item)}"
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in value)
    if value is None:
        return "Non renseigné"
    return str(value).strip() or "Non renseigné"


def format_metadata_report(report: dict[str, Any]) -> str:
    """Format extracted metadata as grouped, human-readable French text."""
    lines: list[str] = []

    def add_section(title: str, values: dict[str, Any], *, depth: int = 0) -> None:
        if not values:
            return
        indent = "  " * depth
        if lines:
            lines.append("")
        lines.append(f"{indent}── {title} ──")
        for key, value in values.items():
            label = _field_label(key)
            if isinstance(value, dict) and value:
                add_section(label, value, depth=depth + 1)
            else:
                lines.append(f"{indent}{label} : {_display_value(value)}")

    summary = {
        key: report[key]
        for key in ("file_name", "path", "extension", "type", "size")
        if key in report
    }
    metadata = report.get("metadata", {})
    add_section("APERÇU DU FICHIER", summary)
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            label = _field_label(key).upper()
            if isinstance(value, dict):
                add_section(label, value)
            else:
                add_section(label, {"Valeur": value})

    other = {
        key: value
        for key, value in report.items()
        if key not in summary and key != "metadata"
    }
    if other:
        add_section("AUTRES INFORMATIONS", other)
    if not lines:
        return "Aucune métadonnée lisible n’a été trouvée dans ce fichier."
    return "\n".join(lines)


def format_report_as_json(report: dict[str, Any]) -> str:
    """Preserve an indented JSON representation for explicit export/use."""
    return json.dumps(report, indent=2, ensure_ascii=False)
