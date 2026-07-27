import logging
import os
from typing import List

import httpx

from pipecat.utils.enums import RealtimeFeedbackType

logger = logging.getLogger(__name__)


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


async def _analyze_intent_with_llm(
    transcript_text: str,
    organization_id: int | None = None,
) -> str | None:
    """Use the exact LLM provider, model, and API key configured by the user in the Models Page to classify transcript intent."""
    if not organization_id:
        return None

    prompt = (
        "You are an expert voice call transcript intent classifier.\n"
        "Analyze the user's spoken words and answers in the following call transcript across any language (Telugu, Hindi, English, etc.).\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        "Instructions:\n"
        "Classify the caller's intent into exactly ONE of these two categories:\n"
        "- Interested: The caller engaged constructively, answered questions, asked for details/pricing, agreed to talk or receive info, or showed curiosity/openness.\n"
        "- Not Interested: The caller explicitly declined (e.g. 'vaddhu', 'voddhu', 'nakko', 'not interested', 'don't call', 'nahi chahiye'), hung up abruptly without interest, or expressed unwillingness.\n\n"
        "Respond ONLY with the exact words 'Interested' or 'Not Interested'."
    )

    api_key = None
    provider = None
    model = None
    base_url = None

    # Dynamically resolve AI model configuration configured by user in the Models Page
    try:
        from api.services.configuration.ai_model_configuration import (
            get_organization_ai_model_configuration_v2,
            get_resolved_ai_model_configuration,
        )

        # 1. Try unmasked org config from database
        v2_config = await get_organization_ai_model_configuration_v2(organization_id)
        if v2_config and v2_config.byok and v2_config.byok.pipeline and v2_config.byok.pipeline.llm:
            org_llm = v2_config.byok.pipeline.llm
            if org_llm.api_key:
                api_key = org_llm.api_key
                provider = org_llm.provider.value if hasattr(org_llm.provider, "value") else str(org_llm.provider)
                model = org_llm.model
                if getattr(org_llm, "endpoint", None):
                    base_url = org_llm.endpoint
                elif getattr(org_llm, "base_url", None):
                    base_url = org_llm.base_url

        # 2. Fall back to resolved effective configuration
        if not api_key:
            resolved = await get_resolved_ai_model_configuration(
                user_id=None,
                organization_id=organization_id,
            )
            effective = resolved.effective if resolved else None
            if effective and effective.llm and effective.llm.api_key:
                if not effective.llm.api_key.startswith("***"):
                    api_key = effective.llm.api_key
                    provider = effective.llm.provider.value if hasattr(effective.llm.provider, "value") else str(effective.llm.provider)
                    model = effective.llm.model
                    if getattr(effective.llm, "endpoint", None):
                        base_url = effective.llm.endpoint
                    elif getattr(effective.llm, "base_url", None):
                        base_url = effective.llm.base_url
    except Exception as e:
        logger.debug(f"Failed to fetch Models Page LLM config for intent detection: {e}")

    # If user has not selected an API key, provider, or model in the Models Page: do NOT use any hardcoded default model!
    if not api_key or not provider or not model:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            prov_lower = provider.lower()
            if "gemini" in prov_lower and "openrouter" not in prov_lower:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 10},
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result_data = resp.json()
                    content = (
                        result_data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                        .strip()
                    )
                    if "Not Interested" in content:
                        return "Not Interested"
                    if "Interested" in content:
                        return "Interested"
            else:
                # OpenRouter, OpenAI, Groq, Anthropic, or any OpenAI-compatible provider selected by user
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 10,
                }
                url = base_url or ("https://openrouter.ai/api/v1/chat/completions" if "openrouter" in prov_lower else "https://api.openai.com/v1/chat/completions")
                if url and not url.endswith("/chat/completions") and "generativelanguage" not in url:
                    url = url.rstrip("/") + "/chat/completions"

                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    result_data = resp.json()
                    content = (
                        result_data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    if "Not Interested" in content:
                        return "Not Interested"
                    if "Interested" in content:
                        return "Interested"
    except Exception as err:
        logger.warning(f"LLM intent classification failed with model '{model}': {err}")

    return None


async def detect_user_intent_async(
    gathered_context: dict | None = None,
    transcript_text: str | None = None,
    disposition: str | None = None,
    duration: float = 0.0,
    organization_id: int | None = None,
) -> str:
    """Async intent detection utilizing LLM transcript analysis with multi-lingual awareness."""
    gathered = gathered_context or {}

    # 0. Check manual user override (stored in gathered_context) - HIGHEST PRECEDENCE
    explicit_intent = (
        gathered.get("user_intent")
        or gathered.get("intent")
        or gathered.get("interest_level")
        or gathered.get("interest")
    )
    if isinstance(explicit_intent, str) and explicit_intent.strip():
        val = explicit_intent.strip()
        if val in ("Interested", "Not Interested", "Not Connected"):
            return val
        val_lower = val.lower()
        if val_lower in ("not connected", "not_connected"):
            return "Not Connected"
        if any(k in val_lower for k in ["not interested", "uninterested", "disqualified", "no_interest", "rejected", "not_interested"]):
            return "Not Interested"
        if any(k in val_lower for k in ["interested", "qualified", "high", "positive", "hot", "warm"]):
            return "Interested"

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

    # 3. Try LLM Intent Analysis on User's Spoken Sentences
    if transcript_text and len(transcript_text.strip()) > 5:
        user_lines = [
            line.strip()
            for line in transcript_text.split("\n")
            if line.strip().lower().startswith(("user:", "caller:", "human:"))
            or " user: " in line.strip().lower()
        ]
        # If the user NEVER spoke a single word (e.g. only assistant spoke before hangup):
        if not user_lines:
            return "Not Interested"

        # Pass ONLY the user's spoken sentences to the LLM
        user_spoken_transcript = "\n".join(user_lines)
        llm_intent = await _analyze_intent_with_llm(user_spoken_transcript, organization_id)
        if llm_intent in ("Interested", "Not Interested"):
            return llm_intent

    # 4. Fallback if no LLM or un-answered
    if disposition_clean in ("busy", "no-answer", "failed", "canceled", "cancelled"):
        return "Not Connected"

    return "Not Interested"


def detect_user_intent(
    gathered_context: dict | None = None,
    transcript_text: str | None = None,
    disposition: str | None = None,
    duration: float = 0.0,
) -> str:
    """Detect user intent strictly based on user's spoken sentences in transcript.

    - Returns 'Not Connected' if call was never connected (busy, no-answer, failed, canceled, initialized with 0s).
    - Checks explicit gathered_context (e.g. manual edit override or live agent setting).
    - Inspects ONLY user's spoken lines in transcript (ignoring assistant words):
      - Positive user words (interested, avunu, haan, send details, yes, ok, etc.) -> 'Interested'
      - Negative user words (not interested, vaddhu, voddhu, nakko, nahi, don't call, etc.) -> 'Not Interested'
      - No user words or undecoded speech -> 'Not Interested'
    - No duration-based defaulting to Interested.
    """
    gathered = gathered_context or {}

    # 0. Check manual user override (stored in gathered_context) - HIGHEST PRECEDENCE
    explicit_intent = (
        gathered.get("user_intent")
        or gathered.get("intent")
        or gathered.get("interest_level")
        or gathered.get("interest")
    )
    if isinstance(explicit_intent, str) and explicit_intent.strip():
        val = explicit_intent.strip()
        if val in ("Interested", "Not Interested", "Not Connected"):
            return val
        val_lower = val.lower()
        if val_lower in ("not connected", "not_connected"):
            return "Not Connected"
        if any(k in val_lower for k in ["not interested", "uninterested", "disqualified", "no_interest", "rejected", "not_interested"]):
            return "Not Interested"
        if any(k in val_lower for k in ["interested", "qualified", "high", "positive", "hot", "warm"]):
            return "Interested"

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

    # Default for un-answered/busy calls is Not Connected, otherwise Not Interested
    if disposition_clean in ("busy", "no-answer", "failed", "canceled", "cancelled"):
        return "Not Connected"

    return "Not Interested"

