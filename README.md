# Task 4 — Secured FastAPI API with Integration Tests

## 1. Setup

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set your own `API_KEY` and `WEBHOOK_SECRET`.

## 2. Run the API

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Every customer endpoint and the webhook require `X-API-Key`.
- Missing key: HTTP 401
- Incorrect key: HTTP 403
- Duplicate email: HTTP 409
- Invalid request body: HTTP 422
- Unknown customer: HTTP 404

The webhook additionally requires `X-Signature`, which is the lowercase
hex HMAC-SHA256 digest of the exact raw request body using `WEBHOOK_SECRET`.

## 3. Run integration tests

```bash
pytest -v
```

The API integration tests use a temporary SQLite database created per test; they do not modify
your development database. Client tests verify offset pagination, OAuth token refresh after
401, and waiting when `X-RateLimit-Remaining` is `0`.

Expected: `11 passed` (includes create/list, auth failures, 404, 409, 422,
valid/tampered webhook, update/delete).

## 4. Run the pagination client

Keep the API running in another terminal:

```bash
python client.py
```

`fetch_all(url)` uses offset/limit pagination, obtains a mock OAuth
client-credentials token from `/oauth/token`, retries once after HTTP 401,
and sleeps when `X-RateLimit-Remaining: 0` is returned.

## 5. Example requests

```bash
curl -H "X-API-Key: YOUR_KEY" \
  "http://127.0.0.1:8000/customers?page=1&per_page=5"

curl -X POST "http://127.0.0.1:8000/customers" \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"name":"Arun Kumar","email":"arun@example.com"}'
```

For production, store secrets in a secret manager, use HTTPS, add real
rate-limit middleware that sets `X-RateLimit-Remaining`, and move webhook
processing to a background queue after returning the acknowledgement.
