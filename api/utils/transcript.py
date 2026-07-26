from typing import List

from pipecat.utils.enums import RealtimeFeedbackType


def generate_transcript_text(events: List[dict]) -> str:
    """Generate transcript text from realtime feedback events.

    Filters for rtf-user-transcription (final) and rtf-bot-text events,
    formats them as '[timestamp] user/assistant: text\n'.
    """
    lines: List[str] = []
    for event in events:
        event_type = event.get("type")
        payload = event.get("payload", {})

        if (
            event_type == RealtimeFeedbackType.USER_TRANSCRIPTION.value
            and payload.get("final") is True
        ):
            text = payload.get("text", "").strip()
            if text:
                timestamp = event.get("timestamp", "")
                prefix = f"[{timestamp}] " if timestamp else ""
                lines.append(f"{prefix}user: {text}\n")
        elif event_type == RealtimeFeedbackType.BOT_TEXT.value:
            text = payload.get("text", "").strip()
            if text:
                timestamp = event.get("timestamp", "")
                prefix = f"[{timestamp}] " if timestamp else ""
                lines.append(f"{prefix}assistant: {text}\n")

    return "".join(lines)


def detect_user_intent(
    gathered_context: dict | None = None,
    transcript_text: str | None = None,
    disposition: str | None = None,
    duration: float = 0.0,
) -> str:
    """Detect user intent (Interested, Not Interested, Neutral, Not Connected).

    Combines gathered_context indicators, disposition code, and full transcript analysis.
    """
    gathered = gathered_context or {}
    disposition_clean = (disposition or "").lower().strip()

    # 1. Check if call was disconnected / not answered
    if duration <= 0 and disposition_clean in (
        "busy",
        "no-answer",
        "failed",
        "canceled",
        "cancelled",
        "initialized",
    ):
        return "Not Connected"

    # 2. Check explicit gathered_context fields
    explicit_intent = (
        gathered.get("user_intent")
        or gathered.get("intent")
        or gathered.get("interest_level")
        or gathered.get("interest")
        or gathered.get("lead_status")
        or gathered.get("qualification")
    )
    if isinstance(explicit_intent, str) and explicit_intent.strip():
        val = explicit_intent.lower()
        if any(
            k in val
            for k in [
                "not interested",
                "uninterested",
                "disqualified",
                "no_interest",
                "rejected",
                "low",
                "not_interested",
            ]
        ):
            return "Not Interested"
        if any(
            k in val
            for k in [
                "interested",
                "qualified",
                "high",
                "positive",
                "hot",
                "warm",
                "yes",
            ]
        ):
            return "Interested"

    if (
        gathered.get("user_qualified") is True
        or disposition_clean in ("user_qualified", "qualified", "transfer_call", "xfer")
    ):
        return "Interested"
    if (
        gathered.get("user_qualified") is False
        or disposition_clean in ("disqualified", "not_qualified", "dnc")
    ):
        return "Not Interested"

    # 3. Analyze Full Transcript Text (User's actual spoken words)
    if transcript_text:
        text_lower = transcript_text.lower()

        # Isolate user lines if formatted
        user_lines = [
            line.strip()
            for line in text_lower.split("\n")
            if line.strip().startswith(("user:", "caller:", "human:"))
            or " user: " in line.strip()
        ]
        target_text = " ".join(user_lines) if user_lines else text_lower

        # Strong Not Interested signals in transcript
        not_interested_signals = [
            "not interested", "no interest", "don't want", "dont want", "do not want",
            "stop calling", "don't call", "dont call", "remove my number", "remove number",
            "not needed", "no thanks", "no thank you", "wrong number", "busy right now",
            "don't need", "dont need", "no need", "cancel", "reject",
            "vaddhu", "voddhu", "nakko", "nahi chahiye", "mat karo", "nako"
        ]
        if any(signal in target_text for signal in not_interested_signals):
            return "Not Interested"

        # Strong Interested signals in transcript
        interested_signals = [
            "interested", "send details", "send info", "share details", "whatsapp me",
            "tell me more", "book appointment", "schedule call", "call back later",
            "sure send", "sounds good", "yes please", "i want to", "i would like to",
            "what is the price", "how much", "cost", "pricing",
            "chahiye", "avunu", "haan send", "ha send"
        ]
        if any(signal in target_text for signal in interested_signals):
            return "Interested"

    # 4. Fallback for connected calls with speech/turns
    if duration > 0 or disposition_clean in ("user_hangup", "agent_hangup", "completed", "answered"):
        return "Neutral"

    return "Not Connected"


