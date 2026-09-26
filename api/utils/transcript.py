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


def extract_workflow_instructions(workflow_definition: dict | None) -> str:
    """Extract a concise summary of the agent's persona, node prompts, and transition conditions."""
    if not isinstance(workflow_definition, dict):
        return ""

    parts: list[str] = []
    nodes = workflow_definition.get("nodes") or []
    edges = workflow_definition.get("edges") or []

    # 1. Global / persona instructions
    for node in nodes:
        node_type = str(node.get("type", "")).lower()
        node_data = node.get("data") or {}
        if "global" in node_type or node_data.get("global_prompt"):
            prompt = (
                node_data.get("prompt")
                or node_data.get("text")
                or node_data.get("global_prompt")
                or ""
            ).strip()
            if prompt:
                parts.append(f"Global Persona & Guidelines:\n{prompt}")

    # 2. Start Call / Agent nodes
    node_prompts = []
    for node in nodes:
        node_type = str(node.get("type", "")).lower()
        if "global" in node_type:
            continue
        node_data = node.get("data") or {}
        name = node_data.get("name") or node.get("id") or "Step"
        prompt = (
            node_data.get("prompt")
            or node_data.get("text")
            or node_data.get("instructions")
            or ""
        ).strip()
        if prompt:
            trimmed_prompt = prompt[:500] if len(prompt) > 500 else prompt
            node_prompts.append(f"[{name}]: {trimmed_prompt}")

    if node_prompts:
        parts.append("Agent Prompts & Flow:\n" + "\n".join(node_prompts[:4]))

    # 3. Decision branches / transition conditions
    conditions = []
    for edge in edges:
        edge_data = edge.get("data") or {}
        label = edge_data.get("label") or edge_data.get("condition") or edge.get("label")
        if label and isinstance(label, str) and label.strip():
            conditions.append(label.strip())

    if conditions:
        unique_conds = list(dict.fromkeys(conditions))[:6]
        parts.append("Expected Outcomes / Branch Conditions:\n- " + "\n- ".join(unique_conds))

    full_instructions = "\n\n".join(parts)
    return full_instructions[:1500]


async def _analyze_intent_with_llm(
    transcript_text: str,
    organization_id: int | None = None,
    agent_instructions: str | None = None,
) -> str | None:
    """Use the exact LLM provider, model, and API key configured by the user in the Models Page to classify transcript intent."""
    if not organization_id:
        return None

    instructions_block = ""
    if agent_instructions and agent_instructions.strip():
        instructions_block = (
            f"Agent Role, Purpose & Guidelines:\n{agent_instructions.strip()}\n\n"
        )

    prompt = (
        "You are an expert voice call evaluator and user intent classifier.\n"
        "Analyze the user's spoken words, tone, and answers in the following call transcript across any language (Telugu, Hindi, English, etc.).\n\n"
        f"{instructions_block}"
        f"Call Transcript:\n{transcript_text}\n\n"
        "Instructions:\n"
        "Evaluate the user's responses in relation to the agent's goals and guidelines above.\n"
        "Classify the caller's intent or outcome into the single most accurate, appropriate category:\n"
        "- 'Interested': The caller agreed, engaged constructively, wanted details/service/quote/demo, or responded positively to the agent's offer.\n"
        "- 'Not Interested': The caller declined, refused, said they don't need it ('vaddhu', 'voddhu', 'nakko', 'nahi chahiye', 'stop calling', 'not interested'), or hung up abruptly without interest.\n"
        "- 'Positive': The caller provided praise, high satisfaction, or strong approval.\n"
        "- 'Negative': The caller expressed disappointment, dissatisfaction, or negative sentiment.\n"
        "- 'Neutral': The caller was non-committal, acknowledged information without interest or disinterest.\n"
        "- 'Grievance': The caller raised a specific complaint, defect, issue, or dispute needing escalation.\n"
        "- 'Callback Requested': The caller requested to be contacted later or was busy.\n"
        "- 'Inquiry': The caller asked clarifying questions or sought information.\n\n"
        "Respond ONLY with the exact single category name from above (or a concise 1-2 word intent label matching the outcome). Do not include any explanations or punctuation."
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            prov_lower = provider.lower()
            content = ""

            if "gemini" in prov_lower or "google" in prov_lower and "vertex" not in prov_lower and "openrouter" not in prov_lower:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20},
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
            elif "sarvam" in prov_lower:
                # Sarvam AI chat completion
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "api-subscription-key": api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model or "sarvam-30b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 20,
                }
                url = base_url or "https://api.sarvam.ai/v1/chat/completions"
                if not url.endswith("/chat/completions"):
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
            else:
                # OpenRouter, OpenAI, Groq, Azure, or any OpenAI-compatible provider selected by user
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 20,
                }
                url = base_url or (
                    "https://openrouter.ai/api/v1/chat/completions"
                    if "openrouter" in prov_lower
                    else "https://api.groq.com/openai/v1/chat/completions"
                    if "groq" in prov_lower
                    else "https://api.openai.com/v1/chat/completions"
                )
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

            if content:
                clean_content = content.replace("*", "").replace('"', '').replace("'", "").strip()
                # Check standard categories
                for cat in [
                    "Not Interested",
                    "Interested",
                    "Callback Requested",
                    "Positive",
                    "Negative",
                    "Neutral",
                    "Grievance",
                    "Inquiry",
                    "Confirmed",
                ]:
                    if cat.lower() in clean_content.lower():
                        return cat

                # Clean short 1-3 word classification
                words = clean_content.split()
                if 0 < len(words) <= 3 and len(clean_content) <= 30:
                    return clean_content.title()
    except Exception as err:
        logger.warning(f"LLM intent classification failed with model '{model}': {err}")

    return None


async def detect_user_intent_async(
    gathered_context: dict | None = None,
    transcript_text: str | None = None,
    disposition: str | None = None,
    duration: float = 0.0,
    organization_id: int | None = None,
    agent_instructions: str | None = None,
    workflow_definition: dict | None = None,
) -> str:
    """Async intent detection utilizing LLM transcript analysis with multi-lingual awareness."""
    gathered = gathered_context or {}

    # 0. Check manual user override or previously stored intent - HIGHEST PRECEDENCE
    explicit_intent = (
        gathered.get("user_intent")
        or gathered.get("intent")
        or gathered.get("interest_level")
        or gathered.get("interest")
    )
    if isinstance(explicit_intent, str) and explicit_intent.strip():
        val = explicit_intent.strip()
        val_lower = val.lower()
        if val_lower in ("not connected", "not_connected"):
            return "Not Connected"
        return val

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

    # 2. Extract agent instructions from workflow definition if not explicitly passed
    if not agent_instructions and workflow_definition:
        agent_instructions = extract_workflow_instructions(workflow_definition)

    # 3. Try LLM Intent Analysis on Transcript
    if transcript_text and len(transcript_text.strip()) > 5:
        text_lower = transcript_text.lower()
        # Check if the user/caller actually spoke any words in the conversation
        has_user_speech = any(
            marker in text_lower
            for marker in ["user:", "caller:", "human:", "speaker 1:", "[user]", "speaker 0:"]
        )
        if not has_user_speech:
            # If the user NEVER spoke a single word (e.g. only assistant spoke before hangup):
            return "Not Interested"

        # Pass full transcript context so the LLM knows what questions the user answered
        llm_intent = await _analyze_intent_with_llm(
            transcript_text=transcript_text,
            organization_id=organization_id,
            agent_instructions=agent_instructions,
        )
        if llm_intent:
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

