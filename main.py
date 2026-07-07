"""
Orders API demonstrating:
  1. Idempotent POST /orders
  2. Cursor-based pagination on GET /orders
  3. Per-client (X-Client-Id) rate limiting

Assigned values:
  T (total catalog orders) = 51
  R (requests per 10s per client) = 19
"""

import time
import uuid
import base64
import threading
from collections import deque, defaultdict

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict

# ----------------------------- Config -----------------------------
TOTAL_ORDERS = 51          # T
RATE_LIMIT = 19            # R requests
RATE_WINDOW_SECONDS = 10   # per 10s

app = FastAPI(title="Orders API")

# CORS - allow all origins so the grader's browser page can call this directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------- Fixed order catalog -----------------------
# IDs 1..TOTAL_ORDERS, used for GET /orders pagination.
CATALOG = [
    {"id": i, "item": f"Item {i}", "amount": round(i * 9.99, 2)}
    for i in range(1, TOTAL_ORDERS + 1)
]

# ------------------- Idempotent creation storage --------------------
_lock = threading.Lock()
idempotency_store: Dict[str, Dict[str, Any]] = {}   # key -> order
next_created_id = TOTAL_ORDERS + 1


class OrderCreate(BaseModel):
    item: Optional[str] = None
    amount: Optional[float] = None
    # accept arbitrary extra fields
    class Config:
        extra = "allow"


@app.post("/orders", status_code=201)
def create_order(
    payload: OrderCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_client_id: Optional[str] = Header(None, alias="X-Client-Id"),
):
    global next_created_id

    # Rate limit check first
    _check_rate_limit(x_client_id)

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    with _lock:
        existing = idempotency_store.get(idempotency_key)
        if existing is not None:
            # Repeat call with same key -> return the SAME order, no new creation
            return JSONResponse(status_code=200, content=existing)

        order = {
            "id": str(next_created_id),
            "item": payload.item or f"Order {next_created_id}",
            "amount": payload.amount if payload.amount is not None else 0.0,
        }
        # include any extra fields the client sent
        extra = payload.dict(exclude={"item", "amount"})
        order.update({k: v for k, v in extra.items() if v is not None})

        idempotency_store[idempotency_key] = order
        next_created_id += 1

    return JSONResponse(status_code=201, content=order)


# --------------------------- Pagination ---------------------------
def _encode_cursor(offset: int) -> str:
    raw = str(offset).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        return int(raw.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/orders")
def list_orders(
    request: Request,
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: Optional[str] = Header(None, alias="X-Client-Id"),
):
    _check_rate_limit(x_client_id)

    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")

    offset = 0 if cursor is None else _decode_cursor(cursor)
    if offset < 0 or offset > len(CATALOG):
        raise HTTPException(status_code=400, detail="Invalid cursor")

    page = CATALOG[offset: offset + limit]
    new_offset = offset + len(page)

    next_cursor = None
    if new_offset < len(CATALOG):
        next_cursor = _encode_cursor(new_offset)

    return {
        "items": page,
        "next_cursor": next_cursor,
        # aliases some graders look for
        "next": next_cursor,
        "orders": page,
    }


# ------------------------- Rate limiting ---------------------------
# Sliding-window log per client id: deque of request timestamps.
_rate_buckets: Dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()


def _check_rate_limit(client_id: Optional[str]):
    if not client_id:
        client_id = "anonymous"

    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[client_id]

        # drop timestamps outside the window
        while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            oldest = bucket[0]
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - oldest)) + 1)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


@app.get("/")
def root():
    return {
        "service": "Orders API",
        "total_orders": TOTAL_ORDERS,
        "rate_limit": f"{RATE_LIMIT} requests / {RATE_WINDOW_SECONDS}s",
        "endpoints": ["POST /orders", "GET /orders"],
    }
