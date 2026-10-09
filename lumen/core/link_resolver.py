from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from lumen.core.validators import is_suspicious_domain, normalize_url


def resolve_redirect_chain(url: str, timeout: int = 15) -> Dict[str, Any]:
    """Follow the redirect chain and summarize the final URL."""
    normalized = normalize_url(url)
    session = requests.Session()
    response = session.get(normalized, timeout=timeout, allow_redirects=True)

    steps: List[Dict[str, Any]] = []
    for history_response in response.history:
        steps.append(
            {
                "status_code": history_response.status_code,
                "url": history_response.url,
            }
        )

    result = {
        "input_url": normalized,
        "final_url": response.url,
        "status_code": response.status_code,
        "redirect_count": len(response.history),
        "redirect_steps": steps,
        "suspicious": is_suspicious_domain(response.url),
        "domain": urlparse(response.url).netloc,
    }
    return result
