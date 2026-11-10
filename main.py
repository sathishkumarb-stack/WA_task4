import hashlib
import hmac
import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field

load_dotenv()

API_KEY = os.getenv("API_KEY", "dev-api-key")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")
DATABASE_PATH = os.getenv("DATABASE_PATH", "customers.db")

app = FastAPI(title="Secured Customers API", version="1.0.0")


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        """)
        conn.commit()


init_db()


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class CustomerUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class CustomerOut(BaseModel):
    id: int
    name: str
    email: str


class TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="X-API-Key header is required")
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.post("/customers", response_model=CustomerOut, status_code=201,
          dependencies=[Depends(require_api_key)])
def create_customer(customer: CustomerCreate):
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO customers (name, email) VALUES (?, ?)",
                (customer.name, str(customer.email))
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, name, email FROM customers WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Customer email already exists")


@app.get("/customers", response_model=list[CustomerOut],
         dependencies=[Depends(require_api_key)])
def list_customers(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=5, ge=1, le=100),
    offset: Optional[int] = Query(default=None, ge=0),
    limit: Optional[int] = Query(default=None, ge=1, le=100),
):
    # Supports the assignment's page/per_page API and offset/limit client pagination.
    actual_limit = limit if limit is not None else per_page
    actual_offset = offset if offset is not None else (page - 1) * per_page
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email FROM customers ORDER BY id LIMIT ? OFFSET ?",
            (actual_limit, actual_offset)
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/customers/{customer_id}", response_model=CustomerOut,
         dependencies=[Depends(require_api_key)])
def get_customer(customer_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return dict(row)


@app.put("/customers/{customer_id}", response_model=CustomerOut,
         dependencies=[Depends(require_api_key)])
def update_customer(customer_id: int, customer: CustomerUpdate):
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE customers SET name = ?, email = ? WHERE id = ?",
                (customer.name, str(customer.email), customer_id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Customer not found")
            conn.commit()
            row = conn.execute(
                "SELECT id, name, email FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Customer email already exists")


@app.delete("/customers/{customer_id}", status_code=204,
            dependencies=[Depends(require_api_key)])
def delete_customer(customer_id: int):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
        conn.commit()
    return None


@app.post("/webhooks/order-events", status_code=200,
          dependencies=[Depends(require_api_key)])
async def order_events(
    request: Request,
    x_signature: Optional[str] = Header(default=None, alias="X-Signature")
):
    body = await request.body()
    if not x_signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    # Acknowledge immediately; process the event asynchronously in a real deployment.
    return {"status": "received"}


@app.post("/oauth/token")
def mock_token_endpoint(credentials: TokenRequest):
    expected_id = os.getenv("OAUTH_CLIENT_ID", "demo-client")
    expected_secret = os.getenv("OAUTH_CLIENT_SECRET", "demo-secret")
    if credentials.grant_type != "client_credentials" or credentials.client_id != expected_id or credentials.client_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    return {"access_token": "mock-access-token", "token_type": "bearer", "expires_in": 3600}
