import os
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests
from dotenv import load_dotenv

load_dotenv()


def _get_access_token(session, token_url):
    response = session.post(
        token_url,
        json={
            "grant_type": "client_credentials",
            "client_id": os.getenv("OAUTH_CLIENT_ID", "demo-client"),
            "client_secret": os.getenv("OAUTH_CLIENT_SECRET", "demo-secret"),
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_all(url, api_key=None, per_page=5, session=None, sleep_seconds=1):
    """Fetch every page using offset/limit; refresh OAuth token once after a 401.

    The API key remains required by the service. OAuth client credentials are
    demonstrated separately through the mock /oauth/token endpoint.
    """
    session = session or requests.Session()
    api_key = api_key or os.getenv("API_KEY", "dev-api-key")
    parsed = urlparse(url)
    token_url = urlunparse((parsed.scheme, parsed.netloc, "/oauth/token", "", "", ""))
    token = _get_access_token(session, token_url)

    all_items = []
    offset = 0
    while True:
        params = dict(parse_qs(parsed.query))
        params = {key: values[-1] for key, values in params.items()}
        params.update({"offset": offset, "limit": per_page})
        page_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, parsed.params,
            urlencode(params), parsed.fragment
        ))
        headers = {"X-API-Key": api_key, "Authorization": f"Bearer {token}"}
        response = session.get(page_url, headers=headers, timeout=10)

        if response.status_code == 401:
            token = _get_access_token(session, token_url)
            headers["Authorization"] = f"Bearer {token}"
            response = session.get(page_url, headers=headers, timeout=10)

        response.raise_for_status()
        batch = response.json()
        all_items.extend(batch)

        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            time.sleep(sleep_seconds)

        if len(batch) < per_page:
            break
        offset += per_page

    return all_items


if __name__ == "__main__":
    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    customers = fetch_all(f"{api_base}/customers")
    print(f"Fetched {len(customers)} customers")
    for customer in customers:
        print(customer)
