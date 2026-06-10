from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import httpx

load_dotenv()

BASE_URL = "https://api.cal.com/v2"


def get_cal_headers() -> dict[str, str]:
    
    api_key = os.getenv("CALCOM_API_KEY")
    if not api_key:
        raise ValueError("CALCOM_API_KEY is not set in the environment.")
    return {
        "Authorization": f"Bearer {api_key}",
        "cal-api-version": "2024-08-13",
        "Content-Type": "application/json",
    }


async def get_available_slots(date: str, days_ahead: int = 5) -> list[dict[str, Any]]:
    
    event_type_id = os.getenv("CALCOM_EVENT_TYPE_ID")
    if not event_type_id:
        raise ValueError("CALCOM_EVENT_TYPE_ID is not set in the environment.")

    # Calculate time range
    try:
        start_dt = datetime.strptime(date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=days_ahead)
        startTime = date
        endTime = end_dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing date parameter: {e}")
        return []

    api_key = os.getenv("CALCOM_API_KEY", "")

    params = {
        "startTime": startTime,
        "endTime": endTime,
        "eventTypeId": event_type_id,
        "apiKey": api_key,
    }

    headers = get_cal_headers()
    url = f"{BASE_URL}/slots/available"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            res_data = response.json()
        except Exception as e:
            print(f"Error calling Cal.com slots API: {e}")
            return []

    slots: list[dict[str, Any]] = []
    raw_slots: list[dict[str, Any]] = []

    # Parse response to extract slots list
    if isinstance(res_data, dict):
        data_field = res_data.get("data")
        slots_field = res_data.get("slots")

        if isinstance(data_field, dict) and "slots" in data_field:
            slots_field = data_field["slots"]
        elif isinstance(data_field, list):
            raw_slots = data_field

        if isinstance(slots_field, dict):
            for slots_list in slots_field.values():
                if isinstance(slots_list, list):
                    raw_slots.extend(slots_list)
        elif isinstance(slots_field, list):
            raw_slots.extend(slots_field)
    elif isinstance(res_data, list):
        raw_slots = res_data

    ist = ZoneInfo("Asia/Kolkata")

    for slot in raw_slots:
        dt_str = slot.get("time") or slot.get("start")
        if not dt_str:
            continue

        try:
            # Parse datetime handling UTC Z format
            clean_dt_str = dt_str.replace("Z", "+00:00")
            dt_val = datetime.fromisoformat(clean_dt_str)
            dt_ist = dt_val.astimezone(ist)

            slot_date = dt_ist.strftime("%Y-%m-%d")
            slot_time = dt_ist.strftime("%H:%M")
            slot_iso = dt_ist.isoformat()

            month_name = dt_ist.strftime("%B")
            day = dt_ist.day
            weekday = dt_ist.strftime("%A")
            time_str = dt_ist.strftime("%I:%M %p")
            if time_str.startswith("0"):
                time_str = time_str[1:]

            display = f"{month_name} {day}, {weekday} at {time_str} IST"

            slots.append({
                "date": slot_date,
                "time": slot_time,
                "datetime": slot_iso,
                "display": display
            })
        except Exception as e:
            print(f"Error parsing slot datetime '{dt_str}': {e}")
            continue

    return slots


async def book_slot(
    datetime_str: str,
    attendee_name: str,
    attendee_email: str,
    notes: str = "",
) -> dict[str, Any]:
    
    event_type_id = os.getenv("CALCOM_EVENT_TYPE_ID")
    if not event_type_id:
        return {"success": False, "error": "CALCOM_EVENT_TYPE_ID is not set."}

    try:
        dt = datetime.fromisoformat(datetime_str)
        dt_utc = dt.astimezone(timezone.utc)
        start_utc = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        return {"success": False, "error": f"Invalid datetime string format: {e}"}

    payload = {
        "eventTypeId": int(event_type_id),
        "start": start_utc,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": "Asia/Kolkata",
        },
        "metadata": {
            "notes": notes,
        },
    }

    headers = get_cal_headers()
    url = f"{BASE_URL}/bookings"

    print("=" * 80)
    print("BOOKING REQUEST")
    print("slot_id:", datetime_str)
    print("name:", attendee_name)
    print("email:", attendee_email)
    print("=" * 80)

    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            print("URL:", url)
            print("PAYLOAD:", payload)
            print("HEADERS:", headers)
            response = await client.post(url, headers=headers, json=payload)
            print("=" * 80)
            print("CAL RESPONSE")
            print(response.status_code)
            print(response.text)
            print("=" * 80)
            response_json = response.json()
            if not response.is_success:
                error_msg = response_json.get("error", {}).get("message") or response.text
                return {"success": False, "error": error_msg}
        except Exception as e:
            print("EXCEPTION IN BOOK_SLOT:", e)
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"API request failed: {e}"}

    # Extract details from response
    booking = response_json.get("data") or response_json
    booking_id = booking.get("uid") or booking.get("id") or "unknown"
    title = booking.get("title") or f"Meeting with {attendee_name}"
    start = booking.get("startTime") or booking.get("start") or datetime_str
    end = booking.get("endTime") or booking.get("end") or ""
    meet_link = booking.get("meetingUrl") or booking.get("location") or ""

    # Format confirmation message in IST timezone
    try:
        ist = ZoneInfo("Asia/Kolkata")
        dt_ist = dt.astimezone(ist)
        month_name = dt_ist.strftime("%B")
        day = dt_ist.day
        time_str = dt_ist.strftime("%I:%M %p")
        if time_str.startswith("0"):
            time_str = time_str[1:]
        confirmation_message = f"Your interview is confirmed for {month_name} {day} at {time_str} IST"
    except Exception:
        confirmation_message = f"Your interview is confirmed for {datetime_str}"

    return {
        "success": True,
        "booking_id": booking_id,
        "title": title,
        "start": start,
        "end": end,
        "meet_link": meet_link,
        "confirmation_message": confirmation_message,
    }


async def get_booking(booking_id: str) -> dict[str, Any]:
    
    headers = get_cal_headers()
    url = f"{BASE_URL}/bookings/{booking_id}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error retrieving booking {booking_id}: {e}")
            try:
                return response.json()
            except Exception:
                return {"error": str(e)}
