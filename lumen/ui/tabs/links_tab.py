from urllib.parse import urlparse


def domain_risk_score(url: str) -> int:
    domain = urlparse(url).netloc.lower()
    score = 0
    if any(keyword in domain for keyword in ["bit.ly", "tinyurl", "t.co", "is.gd", "goo.gl"]):
        score += 70
    return score
