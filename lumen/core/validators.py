from typing import Iterable, List
from urllib.parse import urlparse


SUSPICIOUS_KEYWORDS = {
    "bit.ly",
    "tinyurl",
    "t.co",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "lnkd.in",
    "u.to",
    "shorturl",
    "tiny.cc",
    "buf.sh",
    "x.co",
    "urlr.me",
    "click",
}


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL is empty")
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    return cleaned


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def is_suspicious_domain(url: str) -> bool:
    domain = extract_domain(normalize_url(url))
    if not domain:
        return True

    domain_name = domain.replace("www.", "")
    if any(keyword in domain_name for keyword in SUSPICIOUS_KEYWORDS):
        return True

    return False


def score_domain(url: str) -> int:
    score = 0
    domain = extract_domain(normalize_url(url))
    if any(keyword in domain for keyword in SUSPICIOUS_KEYWORDS):
        score += 50
    if domain.count(".") < 2:
        score += 10
    return score
