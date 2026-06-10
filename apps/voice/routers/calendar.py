from __future__ import annotations

import logging
import os
import traceback
from datetime import date
from typing import Any

import httpx

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services import calendar as cal_service

logger = logging.getLogger("voice.calendar")

router = APIRouter(prefix="/calendar", tags=["calendar"])

class BookRequest(BaseModel):
    """Request body for booking a slot."""

    datetime_str: str
    attendee_name: str
    attendee_email: str
    notes: str = ""


class ScheduleCallRequest(BaseModel):
    """Request body for scheduling a call."""

    phone_number: str
    attendee_name: str
    datetime_str: str

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


@router.post("/schedule-call")
async def schedule_call(body: ScheduleCallRequest) -> dict[str, Any]:
    
    logger.info(
        "POST /calendar/schedule-call — phone=%s attendee=%s datetime=%s",
        body.phone_number,
        body.attendee_name,
        body.datetime_str,
    )

    vapi_api_key = os.getenv("VAPI_API_KEY")
    vapi_phone_number_id = os.getenv("VAPI_PHONE_NUMBER_ID")
    vapi_outbound_assistant_id = os.getenv("VAPI_OUTBOUND_ASSISTANT_ID")

    if not vapi_api_key or not vapi_phone_number_id or not vapi_outbound_assistant_id:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Vapi environment variables (VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, VAPI_OUTBOUND_ASSISTANT_ID) are not set."
            },
        )

    headers = {
        "Authorization": f"Bearer {vapi_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "phoneNumberId": vapi_phone_number_id,
        "assistantId": vapi_outbound_assistant_id,
        "customer": {
            "number": body.phone_number,
            "name": body.attendee_name,
        },
        "assistantOverrides": {
            "variableValues": {
                "attendee_name": body.attendee_name,
                "scheduled_time": body.datetime_str,
            }
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.vapi.ai/call/phone",
                headers=headers,
                json=payload,
            )
            response_json = response.json()
            if not response.is_success:
                error_msg = response_json.get("error", {}).get("message") or response.text
                return JSONResponse(
                    status_code=response.status_code,
                    content={"error": f"Vapi API returned error: {error_msg}"},
                )
            return {"success": True, "call_id": response_json.get("id")}
        except Exception as exc:
            logger.error("POST /calendar/schedule-call failed: %s\n%s", exc, traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"error": f"API request failed: {exc}"},
            )
