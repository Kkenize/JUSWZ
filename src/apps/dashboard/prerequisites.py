"""Shared prerequisite metadata for training categories and levels."""

from __future__ import annotations

from typing import Dict, List, Optional


TRAINING_SECTIONS: Dict[str, Dict[str, Dict[int, List[str]]]] = {
    "3d_printing": {
        "label": "3D Printing",
        "levels": {
            1: [
                "Lvl 1 – Intro to 3D Printing Training",
            ],
            2: [
                "Lvl 2 – High-Detail Resin 3D Printing Training",
                "Lvl 2 – Multi-Material 3D Printing Training",
            ],
            3: [
                "Lvl 3 – Photo-Realistic 3D Printing Training",
            ],
        },
    },
    "textile": {
        "label": "Textile",
        "levels": {
            1: [
                "Lvl 1 – Sewing Machine Basics Training",
            ],
            2: [
                "Lvl 2 – Embroidery Machine Training",
            ],
        },
    },
    "laser": {
        "label": "Laser Cutter",
        "levels": {
            1: [
                "Lvl 1 – Laser Cutting Basics Training",
            ],
            2: [
                "Lvl 2 – Laser Cutter Rotary Training",
                "Lvl 2 – Multi-Surface UV Printer Training",
            ],
        },
    },
    "vinyl_screen": {
        "label": "Vinyl & Screen Printing",
        "levels": {
            1: [
                "Lvl 1 – Vinyl Cutting Basics Training",
                "Lvl 1 – Screen Printing Training",
            ],
            2: [
                "Lvl 2 – Direct-to-Garment Printing Training",
                "Lvl 2 – Sticker Printing Training",
            ],
        },
    },
    "woodworking": {
        "label": "Woodworking",
        "levels": {
            1: [
                "Lvl 1 – Woodworking Basics Training",
            ],
            2: [
                "Lvl 2 – CNC Routing Training",
                "Lvl 2 – Intermediate Woodworking Training",
                "Lvl 2 – Chisel & Plane Training (In Development)",
            ],
            3: [
                "Lvl 3 – Advanced Woodworking Training",
                "Lvl 3 – Wood Lathe Training (In Development)",
            ],
        },
    },
    "electronics": {
        "label": "Electronics",
        "levels": {
            1: [
                "Lvl 1 – Circuitry Basics Training",
                "Lvl 1 – Soldering Basics Training",
            ],
            2: [
                "Lvl 2 – Circuitry 2 Training",
            ],
        },
    },
    "metalworking": {
        "label": "Metalworking",
        "levels": {
            1: [
                "Lvl 1 – Waterjet Cutting Training",
                "Lvl 1 – Machining Basics Training (In Development)",
            ],
            2: [
                "Lvl 2 – Conversational Programming Training (In Development)",
            ],
            3: [
                "Lvl 3 – CAM Programming Training (In Development)",
            ],
        },
    },
}


def _normalize_title(title: Optional[str]) -> str:
    return (title or "").strip().lower()


def _build_training_lookup() -> Dict[str, Dict[str, object]]:
    lookup: Dict[str, Dict[str, object]] = {}
    for category_key, config in TRAINING_SECTIONS.items():
        label = config.get("label", category_key.replace("_", " ").title())
        levels = config.get("levels", {})
        for level, titles in levels.items():
            for raw_title in titles:
                normalized = _normalize_title(raw_title)
                if not normalized:
                    continue
                lookup[normalized] = {
                    "category": category_key,
                    "category_label": label,
                    "level": int(level),
                    "title": raw_title,
                }
    return lookup


TRAINING_LOOKUP = _build_training_lookup()


def get_training_metadata(title: Optional[str]) -> Optional[Dict[str, object]]:
    """Return the prerequisite metadata for the provided training title."""

    if not title:
        return None
    return TRAINING_LOOKUP.get(_normalize_title(title))


def serialize_prereq_map() -> Dict[str, object]:
    """Return a JSON-serializable map with lookup data for the UI."""

    categories = {
        key: {
            "label": value.get("label"),
            "level_one_titles": list(value.get("levels", {}).get(1, [])),
        }
        for key, value in TRAINING_SECTIONS.items()
    }
    return {
        "by_title": TRAINING_LOOKUP,
        "categories": categories,
    }
