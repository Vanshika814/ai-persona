from __future__ import annotations

from collections.abc import AsyncGenerator
import json
import os
import re

import contextvars
from dotenv import load_dotenv
from groq import AsyncGroq

from services.persona import format_prompt_with_context, get_voice_system_prompt
from services.persona import get_chat_system_prompt
load_dotenv()

# Context Var to track request-level session ID
current_session_id = contextvars.ContextVar("current_session_id", default="default_user")

CHAT_STATE = {
    "flow": None,              # interview | call
    "selected_slot": None,
    "awaiting_contact": False,
}

# Global session state
SESSIONS: dict[str, dict] = {}


def get_session(user_id: str) -> dict:
    """Retrieve or initialize session state for a given user."""
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {
            "flow": None,
            "last_slots": [],
            "selected_slot": None,
        }
    return SESSIONS[user_id]


def resolve_slot_id(user_id: str, slot_id: str) -> str:
    """Resolve ordinal slot references (like 'second', '2') to their raw slot_id."""
    session = get_session(user_id)
    slots = session.get("last_slots", [])
    if not slots:
        return slot_id

    slot_id_clean = slot_id.strip().lower()

    # Digits mapping (e.g., '1', '2', '3')
    if slot_id_clean.isdigit():
        idx = int(slot_id_clean) - 1
        if 0 <= idx < len(slots):
            return slots[idx]["slot_id"]

    # Keyword mapping
    mapping = {
        "first": 0, "1st": 0, "one": 0, "1": 0,
        "second": 1, "2nd": 1, "two": 1, "2": 1, "second one": 1,
        "third": 2, "3rd": 2, "three": 2, "3": 2, "third one": 2
    }

    for term, idx in mapping.items():
        if term in slot_id_clean:
            if idx < len(slots):
                return slots[idx]["slot_id"]

    return slot_id

_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    """Return a configured Groq client, creating it on first call."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set.")
        _client = AsyncGroq(api_key=api_key)
    return _client

MODEL = "llama-3.3-70b-versatile"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_next_slots",
            "description": "Get next 3 available interview slots. Use when user wants to book without specifying date/time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "offset": {
                        "type": "integer",
                        "description": "0 for first 3 slots, 3 for next 3, 6 for next 6"
                    }
                },
                "required": []
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slots_by_date",
            "description": "Get slots for a specific date or day like Friday, June 10 etc",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "Date like 2026-06-10 or Friday",
                    }
                },
                "required": ["date_str"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_slot",
            "description": "Book a confirmed slot. Only call after user selected a slot AND gave name and email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string",
                        "description": "The datetime string of selected slot",
                    },
                    "attendee_name": {"type": "string"},
                    "attendee_email": {"type": "string"},
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_vapi_call",
            "description": "Schedule an outbound Vapi phone call to the user. Only call after user selected a slot AND gave name and phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Phone number with country code, e.g. +1234567890",
                    },
                    "attendee_name": {"type": "string"},
                    "datetime_str": {
                        "type": "string",
                        "description": "The slot_id (datetime string) selected by the user",
                    },
                }
            },
        },
    },
]


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool dynamically using the CalComService."""
    from services.calcom import calcom

    user_id = current_session_id.get()
    session = get_session(user_id)

    if name == "get_next_slots":
        slots = await calcom.get_next_slots(offset=args.get("offset", 0))
        if not slots:
            result = "No available slots found."
        else:
            session["last_slots"] = slots
            result = "### Available Slots\n\n"

            result += "\n".join(
                [
                    f"- {s['display']} [id: {s['slot_id']}]"
                    for s in slots
                ]
            )

            result += (
                "\n\nWhich one works for you?"
                "\n\nOr say **more options** for different slots."
            )

    elif name == "get_slots_by_date":
        slots = await calcom.get_slots_by_date(args["date_str"])
        if not slots:
            result = f"No slots available for {args['date_str']}."
        else:
            session["last_slots"] = slots
            result = f"### Available Slots for {args['date_str']}\n\n"
            result += "\n".join(
                [
                    f"- {s['display']} [id: {s['slot_id']}]"
                    for s in slots
                ]
            )
            result += "\n\nWhich one works for you?"



    elif name == "book_slot":
        attendee_name = args.get("attendee_name", "")
        attendee_email = args.get("attendee_email", "")
        if attendee_name in ("User Name", "User", "") or attendee_email in ("user@example.com", ""):
            result = "Error: Cannot book slot. Attendee name and email are required. Do not guess these. Please ask the user to provide their real name and email."
        else:
            slot_id = resolve_slot_id(user_id, args["slot_id"])
            session["selected_slot"] = slot_id
            booking_res = await calcom.book(
                slot_id, attendee_name, attendee_email
            )
            if booking_res.get("success"):
                result = (
                    "✅ Booking Confirmed!\n\n"
                    f"Interview scheduled for:\n"
                    f"{booking_res.get('confirmation_message')}\n\n"
                    f"A confirmation has been sent to {attendee_email}."
                )
            else:
                result = f"Booking failed: {booking_res.get('error')}"

    elif name == "schedule_vapi_call":
        call_res = await calcom.schedule_call(
            phone_number=args["phone_number"],
            attendee_name=args["attendee_name"],
            datetime_str=args["datetime_str"],
        )

        if call_res.get("success"):
            result = (
                f"📞 Call scheduled successfully!\n\n"
                f"Call ID: {call_res.get('call_id')}\n"
                f"Status: {call_res.get('status', 'created')}\n"
                f"Phone Number: {args['phone_number']}\n"
                f"Scheduled Time: {args['datetime_str']}"
            )
        else:
            result = f"Call scheduling failed: {call_res.get('error')}"

    else:
        result = f"Unknown tool: {name}"

    print("=" * 50)
    print(result)
    print("=" * 50)
    return result

async def simple_chat(
    user_message: str,
    context: str,
    conversation_history: list[dict],
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """Execute conversational chat for Q&A, using streaming and NO tools."""
    client = get_groq_client()

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    for turn in conversation_history:
        messages.append(
            {
                "role": turn.get("role", "user"),
                "content": turn.get("content", ""),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": format_prompt_with_context(user_message, context),
        }
    )

    try:
        stream = await client.chat.completions.create(
            model=MODEL, messages=messages, stream=True
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta is not None:
                yield delta
    except Exception as exc:
        print(f"[llm] simple_chat stream failed: {exc}")
        yield f"Error calling AI model: {exc}"


async def agentic_chat(
    user_message: str,
    context: str,
    conversation_history: list[dict],
    system_prompt: str,
    session_id: str = "default_user",
) -> AsyncGenerator[str, None]:
    token = current_session_id.set(session_id)
    try:
        msg = user_message.lower()

        if any(
            x in msg
            for x in [
                "interview",
                "book interview",
                "schedule interview",
            ]
        ):
            CHAT_STATE["flow"] = "interview"

        if any(
            x in msg
            for x in [
                "call me",
                "phone call",
                "callback",
                "voice call",
            ]
        ):
            CHAT_STATE["flow"] = "call"

        slot_match = re.search(
            r"\[id:\s*(.*?)\]",
            user_message
        )

        if slot_match:
            CHAT_STATE["selected_slot"] = slot_match.group(1)
            CHAT_STATE["awaiting_contact"] = True

            if CHAT_STATE["flow"] == "interview":
                yield "Great! Could I get your full name and email?"
                return

            if CHAT_STATE["flow"] == "call":
                yield (
                    "Great! Could I get your name and phone number "
                    "with country code?"
                )
                return

        if CHAT_STATE["awaiting_contact"]:
            if CHAT_STATE["flow"] == "interview":
                email_match = re.search(
                    r"[\w\.-]+@[\w\.-]+\.\w+",
                    user_message
                )
                if email_match:
                    email = email_match.group(0)
                    name = user_message.replace(
                        email,
                        ""
                    ).strip()
                    result = await execute_tool(
                        "book_slot",
                        {
                            "slot_id":
                                CHAT_STATE["selected_slot"],
                            "attendee_name":
                                name,
                            "attendee_email":
                                email,
                        },
                    )
                    CHAT_STATE["awaiting_contact"] = False
                    yield result
                    return

            if CHAT_STATE["flow"] == "call":
                phone_match = re.search(
                    r"\+\d{10,15}",
                    user_message
                )
                if phone_match:
                    phone = phone_match.group(0)
                    name = user_message.replace(
                        phone,
                        ""
                    ).strip()
                    result = await execute_tool(
                        "schedule_vapi_call",
                        {
                            "datetime_str":
                                CHAT_STATE["selected_slot"],
                            "attendee_name":
                                name,
                            "phone_number":
                                phone,
                        },
                    )
                    CHAT_STATE["awaiting_contact"] = False
                    yield result
                    return

        client = get_groq_client()

        messages = [{"role": "system", "content": system_prompt}]
        for turn in conversation_history:
            messages.append(
                {
                    "role": turn.get("role", "user"),
                    "content": turn.get("content", ""),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": format_prompt_with_context(user_message, context),
            }
        )

        # Non-streaming call to detect tool use
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                stream=False,
                temperature=0.0,
            )
            choice = response.choices[0]
        except Exception as exc:
            print(f"[llm] agentic_chat initial completion failed: {exc}")
            yield f"Error calling AI model: {exc}"
            return

        if choice.finish_reason == "tool_calls":
            # Add assistant's tool call decision
            messages.append(choice.message)

            # Execute tools and collect results
            slot_results = []
            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments)
                result = await execute_tool(tc.function.name, args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
                if "slots" in tc.function.name:
                    slot_results.append(result)

            # If slots were fetched, yield them directly without LLM
            if slot_results:
                print("SLOT RESULTS:")
                print(slot_results)
                for result in slot_results:
                    yield result
                return

            # For non-slot tools (booking), let LLM format the response
            try:
                final = await client.chat.completions.create(
                    model=MODEL, messages=messages, stream=True
                )
                async for chunk in final:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            except Exception as exc:
                print(f"[llm] agentic_chat final stream failed: {exc}")
                yield f"Error generating final response: {exc}"

        else:
            # No tool call - yield directly
            if choice.message.content:
                yield choice.message.content
    finally:
        current_session_id.reset(token)

async def stream_chat(
    user_message: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Wrapper that routes streaming chat to either simple_chat or agentic_chat flow."""
    if conversation_history is None:
        conversation_history = []
    sys_prompt = (
        system_prompt
        if system_prompt is not None
        else get_chat_system_prompt()
    )

    async for chunk in agentic_chat(
        user_message=user_message,
        context=context,
        conversation_history=conversation_history,
        system_prompt=sys_prompt,
    ):
        yield chunk


async def chat_completion(
    user_message: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
) -> str:
    """Synchronous completion helper that calls the routed stream and yields final text."""
    if conversation_history is None:
        conversation_history = []
    sys_prompt = (
        system_prompt
        if system_prompt is not None
        else get_voice_system_prompt()
    )

    chunks = []
    async for chunk in stream_chat(
        user_message=user_message,
        context=context,
        conversation_history=conversation_history,
        system_prompt=sys_prompt,
    ):
        chunks.append(chunk)
    return "".join(chunks)

_CALENDAR_KEYWORDS: set[str] = {
    "schedule",
    "book",
    "meeting",
    "call",
    "available",
    "availability",
    "slot",
    "interview",
    "when",
    "time",
}


def is_calendar_intent(message: str) -> bool:
    """Detect calendar scheduling requests based on keyword search."""
    words = set(message.lower().split())
    return bool(words & _CALENDAR_KEYWORDS)


def check_health() -> dict[str, str]:
    """Check Groq configuration and initialization health."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"status": "unhealthy", "error": "GROQ_API_KEY is not set"}
    try:
        get_groq_client()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}
