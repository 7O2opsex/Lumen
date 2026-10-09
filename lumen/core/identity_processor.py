import re
from typing import Iterable, List, Sequence, Set
from urllib.parse import quote


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def generate_name_variants(name: str) -> List[str]:
    """Generate common identity variations around a full name."""
    raw = normalize_name(name)
    if not raw:
        return []

    tokens = raw.split()
    first = tokens[0].title()
    last = tokens[-1].title() if len(tokens) > 1 else ""
    middle = " ".join(tokens[1:-1]).title() if len(tokens) > 2 else ""

    variants: Set[str] = set()
    variants.add(raw)
    variants.add(raw.lower())
    variants.add(raw.upper())
    variants.add(first)
    variants.add(first + last)
    variants.add(f"{first}.{last}") if last else None
    variants.add(f"{first}_{last}") if last else None
    variants.add(f"{first}{last}") if last else None
    variants.add(f"{first} {last}") if last else None
    variants.add(f"{first} {middle} {last}") if middle else None
    variants.add(f"{first[0]}.{last}") if last else None
    variants.add(f"{first[0]}{last}") if last else None
    variants.add(f"{first} {last[0]}") if last else None

    # Include common nickname-like transformations
    if len(tokens) > 1:
        variants.add(f"{first.lower()}{last.lower()}")
        variants.add(f"{first.lower()}_{last.lower()}")
        variants.add(f"{first.lower()}.{last.lower()}")

    return sorted(v for v in variants if v)


def _tokenize(value: str) -> Set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9]+", value.lower()) if token}


def cross_reference(left: str, right: str) -> dict:
    """Generate a basic similarity score between two identity identifiers."""
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    overlap = sorted(left_tokens & right_tokens)
    union = sorted(left_tokens | right_tokens)
    score = round((len(overlap) / len(union)) * 100, 2) if union else 0.0

    return {
        "left": left,
        "right": right,
        "shared_tokens": overlap,
        "similarity_percent": score,
    }


def build_user_lookup_targets(name: str) -> List[dict]:
    """Generate a small list of search targets without making outbound calls by default."""
    encoded = quote(name)
    sites = [
        {"label": "Twitter/X", "query": f"https://x.com/search?q={encoded}"},
        {"label": "GitHub", "query": f"https://github.com/search?q={encoded}&type=users"},
        {"label": "DuckDuckGo", "query": f"https://duckduckgo.com/?q={encoded}"},
    ]
    return sites
