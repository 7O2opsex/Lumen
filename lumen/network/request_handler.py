from typing import Any, Dict

import requests

from lumen.core.validators import is_suspicious_domain, normalize_url


def resolve_redirect_chain(url: str, timeout: int = 15) -> Dict[str, Any]:
    normalized = normalize_url(url)
    session = requests.Session()
    response = session.get(normalized, timeout=timeout, allow_redirects=True)

    steps = []
    for item in response.history:
        steps.append({
            "status_code": item.status_code,
            "url": item.url,
        })

    return {
        "input_url": normalized,
        "final_url": response.url,
        "status_code": response.status_code,
        "redirect_count": len(response.history),
        "redirect_steps": steps,
        "suspicious": is_suspicious_domain(response.url),
    }
