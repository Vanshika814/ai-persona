"""Calendar router for the voice FastAPI backend.

Provides:
- ``GET /calendar/slots`` — Fetch available Cal.com slots.
- ``POST /calendar/book`` — Book a Cal.com slot.
- ``GET /calendar/booking/{booking_id}`` — Retrieve booking details.
"""

from __future__ import annotations

import logging
import traceback
from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services import calendar as cal_service

logger = logging.getLogger("voice.calendar")

router = APIRouter(prefix="/calendar", tags=["calendar"])


# ──────────────────────────────────────────────
#  Request models
# ──────────────────────────────────────────────


class BookRequest(BaseModel):
    """Request body for booking a slot."""

    datetime_str: str
    attendee_name: str
    attendee_email: str
    notes: str = ""


# ──────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────


@router.get("/slots")
async def get_slots(
    date_param: str = Query(
        default=None,
        alias="date",
        description="Start date in YYYY-MM-DD format. Defaults to today.",
    ),
    days_ahead: int = Query(
        default=5,
        description="Number of days ahead to search for slots.",
    ),
) -> dict[str, Any]:
    """Fetch available Cal.com slots for the given date range.

    Args:
        date_param: Start date (YYYY-MM-DD). Defaults to today.
        days_ahead: Number of days to look ahead.

    Returns:
        ``{"slots": [...], "count": <int>}``
    """
    if date_param is None:
        date_param = date.today().isoformat()

    logger.info(
        "GET /calendar/slots — date=%s days_ahead=%d",
        date_param,
        days_ahead,
    )

    try:
        slots = await cal_service.get_available_slots(
            date=date_param,
            days_ahead=days_ahead,
        )
        return {"slots": slots, "count": len(slots)}

    except Exception as exc:
        logger.error(
            "GET /calendar/slots failed: %s\n%s", exc, traceback.format_exc()
        )
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


@router.post("/book")
async def book(body: BookRequest) -> dict[str, Any]:
    """Book a Cal.com slot.

    Args:
        body: Parsed ``BookRequest`` with datetime, attendee info, and
            optional notes.

    Returns:
        Booking confirmation dict from Cal.com.
    """
    logger.info(
        "POST /calendar/book — datetime=%s attendee=%s",
        body.datetime_str,
        body.attendee_email,
    )

    try:
        result = await cal_service.book_slot(
            datetime_str=body.datetime_str,
            attendee_name=body.attendee_name,
            attendee_email=body.attendee_email,
            notes=body.notes,
        )
        return result

    except Exception as exc:
        logger.error(
            "POST /calendar/book failed: %s\n%s", exc, traceback.format_exc()
        )
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


@router.get("/booking/{booking_id}")
async def get_booking(booking_id: str) -> dict[str, Any]:
    """Retrieve details for a specific booking.

    Args:
        booking_id: The unique booking identifier.

    Returns:
        Booking details dict from Cal.com.
    """
    logger.info("GET /calendar/booking/%s", booking_id)

    try:
        result = await cal_service.get_booking(booking_id=booking_id)
        return result

    except Exception as exc:
        logger.error(
            "GET /calendar/booking/%s failed: %s\n%s",
            booking_id,
            exc,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )
