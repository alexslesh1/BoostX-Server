"""Future payments integration (Lava) — stub only.

This router is a placeholder for a LATER integration with Lava as the
payment processor. Do not build real payment logic against this endpoint
yet — it exists purely to reserve the contract path for the desktop client.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.exceptions import NotImplementedException

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook/lava")
async def lava_webhook(request: Request) -> None:
    """Lava payment webhook receiver (not implemented yet).

    Once wired up, this endpoint will:
      1. Verify the incoming request's signature against Lava's webhook
         secret (reject anything that doesn't match).
      2. Parse the payment/subscription event payload.
      3. Look up the associated user (e.g. via an order/customer reference)
         and update their Subscription row's `plan`, `status`, and
         `current_period_end` accordingly.
      4. Return 200 promptly so Lava does not retry unnecessarily.

    For now it always returns 501 so the desktop client can distinguish
    "not built yet" from a real failure.
    """
    raise NotImplementedException("Not implemented yet")
