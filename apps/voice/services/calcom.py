from __future__ import annotations

from dotenv import load_dotenv
from typing import Any

load_dotenv()


class CalComService:

    async def get_next_slots(self, offset: int = 0) -> list[dict[str, Any]]:
        """Get next 3 available slots from Cal.com"""
        from datetime import date
        from services.calendar import get_available_slots

        slots = await get_available_slots(date.today().isoformat(), days_ahead=7)
        paginated = slots[offset : offset + 3]
        return [
            {
                "slot_id": s["datetime"],  # use datetime as ID
                "display": s["display"],
                "datetime": s["datetime"],
            }
            for s in paginated
        ]

    async def get_slots_by_date(self, date_str: str) -> list[dict[str, Any]]:
        """Get slots for a specific date"""
        from datetime import date
        from services.calendar import get_available_slots

        slots = await get_available_slots(date.today().isoformat(), days_ahead=7)
        filtered = [
            s
            for s in slots
            if date_str in s["date"] or date_str.lower() in s["display"].lower()
        ]
        return [
            {
                "slot_id": s["datetime"],
                "display": s["display"],
                "datetime": s["datetime"],
            }
            for s in filtered[:3]
        ]

    async def get_slots_by_time(self, preference: str) -> list[dict[str, Any]]:
        """Get slots by morning/afternoon/evening"""
        from datetime import date
        from services.calendar import get_available_slots

        ranges = {
            "morning": (9, 12),
            "afternoon": (12, 15),
            "evening": (15, 18),
        }
        h_start, h_end = ranges.get(preference, (9, 18))
        slots = await get_available_slots(date.today().isoformat(), days_ahead=7)
        filtered = [
            s
            for s in slots
            if h_start <= int(s["time"].split(":")[0]) < h_end
        ]
        return [
            {
                "slot_id": s["datetime"],
                "display": s["display"],
                "datetime": s["datetime"],
            }
            for s in filtered[:3]
        ]

    async def book(self, slot_id: str, name: str, email: str) -> dict[str, Any]:
        """Book a slot"""
        from services.calendar import book_slot

        return await book_slot(
            datetime_str=slot_id, attendee_name=name, attendee_email=email
        )

    async def schedule_call(self, phone_number: str, attendee_name: str, datetime_str: str) -> dict[str, Any]:
        """Schedule a Vapi outbound call"""
        import os
        import httpx

        vapi_api_key = os.getenv("VAPI_API_KEY")
        vapi_phone_number_id = os.getenv("VAPI_PHONE_NUMBER_ID")
        vapi_outbound_assistant_id = os.getenv("VAPI_OUTBOUND_ASSISTANT_ID")

        print("VAPI_API_KEY:", bool(vapi_api_key))
        print("VAPI_PHONE_NUMBER_ID:", bool(vapi_phone_number_id))
        print("VAPI_OUTBOUND_ASSISTANT_ID:", bool(vapi_outbound_assistant_id))

        print("=" * 50)
        print("KEY:", vapi_api_key[:8] if vapi_api_key else None)
        print("PHONE:", vapi_phone_number_id)
        print("ASSISTANT:", vapi_outbound_assistant_id)
        print("=" * 50)

        if not vapi_api_key or not vapi_phone_number_id or not vapi_outbound_assistant_id:
            return {
                "success": False,
                "error": "Vapi environment variables (VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, VAPI_OUTBOUND_ASSISTANT_ID) are not set."
            }

        headers = {
            "Authorization": f"Bearer {vapi_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "phoneNumberId": vapi_phone_number_id,
            "assistantId": vapi_outbound_assistant_id,
            "customer": {
                "number": phone_number,
                "name": attendee_name,
            },
            "assistantOverrides": {
                "variableValues": {
                    "attendee_name": attendee_name,
                    "scheduled_time": datetime_str,
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
                print("STATUS:", response.status_code)
                print("BODY:", response.text)
                response_json = response.json()
                if not response.is_success:
                    error_msg = response.text
                    if isinstance(response_json, dict):
                        err_field = response_json.get("error")
                        if isinstance(err_field, dict):
                            error_msg = err_field.get("message") or response_json.get("message")
                        else:
                            error_msg = response_json.get("message") or err_field or response.text
                    return {"success": False, "error": f"Vapi API returned error: {error_msg}"}
                print("=" * 80)
                print("VAPI RESPONSE")
                print(response.status_code)
                print(response_json)
                print("=" * 80)

                print("=" * 80)
                print("OUTBOUND CALL CREATED")
                print("Name:", attendee_name)
                print("Phone:", phone_number)
                print("Datetime:", datetime_str)
                print("Call ID:", response_json.get("id") if isinstance(response_json, dict) else None)
                print("=" * 80)

                return {
                    "success": True,
                    "call_id": response_json.get("id") if isinstance(response_json, dict) else None,
                    "status": response_json.get("status") if isinstance(response_json, dict) else "created",
                    "raw_response": response_json,
                }
            except Exception as exc:
                return {"success": False, "error": f"API request failed: {exc}"}


calcom = CalComService()
