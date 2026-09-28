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
    """Use the configured LLM provider, model, and API key to classify full conversation intent."""
    if not organization_id:
        return None

    instructions_block = ""
    if agent_instructions and agent_instructions.strip():
        instructions_block = (
            f"Agent Role, Purpose & Guidelines:\n{agent_instructions.strip()}\n\n"
        )

    prompt = (
        "You are an expert voice call evaluator and user intent classifier.\n"
        "Analyze the full conversation between the AI assistant and the caller/user in the following call transcript across any language (Telugu, Hindi, English, etc.).\n\n"
        f"{instructions_block}"
        f"Call Transcript:\n{transcript_text}\n\n"
        "Instructions:\n"
        "Carefully evaluate what the AI asked and what the user replied in context.\n"
        "Classify the caller's intent or outcome into the single most accurate, appropriate category:\n"
        "- 'Interested': The caller agreed, engaged constructively, answered questions/survey cooperatively, wanted details/service/quote/demo, or responded positively to the agent's offer.\n"
        "- 'Did Not Speak': The caller connected but remained silent, did not speak any words, or disconnected without speaking.\n"
        "- 'Positive': The caller provided praise, high satisfaction, or strong approval.\n"
        "- 'Negative': The caller expressed disappointment, dissatisfaction, or negative sentiment.\n"
        "- 'Neutral': The caller was non-committal, acknowledged information without interest or disinterest, or gave routine answers/greetings like 'hello'.\n"
        "- 'Grievance': The caller raised a specific complaint, defect, issue, or dispute needing escalation.\n"
        "- 'Callback Requested': The caller requested to be contacted later or was busy/driving.\n"
        "- 'Inquiry': The caller asked clarifying questions or sought information.\n"
        "- 'Not Connected': The call failed to connect, was busy, no-answer, or 0s duration.\n\n"
        "Respond ONLY with the exact single category name from above. Do not include any explanations, markdown, or punctuation."
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
        if v2_config:
            org_llm = None
            if v2_config.mode == "byok" and v2_config.byok:
                # In realtime mode, LLM configuration lives under byok.realtime.llm
                if v2_config.byok.mode == "realtime" and v2_config.byok.realtime and v2_config.byok.realtime.llm:
                    org_llm = v2_config.byok.realtime.llm
                elif v2_config.byok.mode == "pipeline" and v2_config.byok.pipeline and v2_config.byok.pipeline.llm:
                    org_llm = v2_config.byok.pipeline.llm
                elif v2_config.byok.realtime and v2_config.byok.realtime.llm:
                    org_llm = v2_config.byok.realtime.llm
                elif v2_config.byok.pipeline and v2_config.byok.pipeline.llm:
                    org_llm = v2_config.byok.pipeline.llm
            elif v2_config.mode == "dograh" and v2_config.dograh:
                api_key = v2_config.dograh.api_key
                provider = "dograh"
                model = "default"

            if org_llm and org_llm.api_key:
                raw_key = org_llm.api_key
                k = raw_key[0] if isinstance(raw_key, list) and raw_key else (raw_key if isinstance(raw_key, str) else "")
                if k and not k.startswith("***"):
                    api_key = k
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
                raw_key = effective.llm.api_key
                k = raw_key[0] if isinstance(raw_key, list) and raw_key else (raw_key if isinstance(raw_key, str) else "")
                if k and not k.startswith("***"):
                    api_key = k
                    provider = effective.llm.provider.value if hasattr(effective.llm.provider, "value") else str(effective.llm.provider)
                    model = effective.llm.model
                    if getattr(effective.llm, "endpoint", None):
                        base_url = effective.llm.endpoint
                    elif getattr(effective.llm, "base_url", None):
                        base_url = effective.llm.base_url

            # Secondary fallback: if LLM not found, check OpenRouter in embeddings config
            if not api_key and effective and effective.embeddings and effective.embeddings.api_key:
                raw_key = effective.embeddings.api_key
                k = raw_key[0] if isinstance(raw_key, list) and raw_key else (raw_key if isinstance(raw_key, str) else "")
                if k and not k.startswith("***"):
                    emb_prov = effective.embeddings.provider.value if hasattr(effective.embeddings.provider, "value") else str(effective.embeddings.provider)
                    if "openrouter" in emb_prov.lower():
                        api_key = k
                        provider = "openrouter"
                        model = "openai/gpt-4o-mini"
                        base_url = getattr(effective.embeddings, "base_url", "https://openrouter.ai/api/v1")
    except Exception as e:
        logger.warning(f"Failed to fetch Models Page LLM config for intent detection: {e}")

    # If user has not selected an API key, provider, or model: do NOT make random external calls
    if not api_key or not provider or not model:
        logger.info(f"Skipping LLM intent analysis: api_key={bool(api_key)}, provider={provider}, model={model}")
        return None

    # Handle string extraction if api_key was somehow still a list
    if isinstance(api_key, list):
        api_key = api_key[0] if api_key else ""

    prov_lower = provider.lower()

    # Sarvam AI model alias: sarvam-30b and sarvam-2b were deprecated; map to conversational model
    if "sarvam" in prov_lower:
        if not model or model in ("sarvam-30b", "sarvam-2b", "default"):
            model = "sarvam-105b-conversations"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            content = ""

            if "gemini" in prov_lower or ("google" in prov_lower and "vertex" not in prov_lower and "openrouter" not in prov_lower):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 30},
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    result_data = resp.json()
                    candidates = result_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            content = parts[0].get("text", "").strip()
                else:
                    logger.warning(f"Gemini intent classification returned status {resp.status_code}: {resp.text[:200]}")
            elif "sarvam" in prov_lower:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "api-subscription-key": api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 50,
                }
                url = base_url or "https://api.sarvam.ai/v1/chat/completions"
                if not url.endswith("/chat/completions"):
                    url = url.rstrip("/") + "/chat/completions"
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    result_data = resp.json()
                    choices = result_data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
                else:
                    logger.warning(f"Sarvam intent classification returned status {resp.status_code}: {resp.text[:200]}")
            else:
                # OpenRouter, OpenAI, Groq, Azure, or any OpenAI-compatible provider
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 50,
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
                    choices = result_data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = (msg.get("content") or msg.get("reasoning") or "").strip()
                else:
                    logger.warning(f"LLM intent classification returned status {resp.status_code}: {resp.text[:200]}")

            if content:
                clean_content = content.replace("*", "").replace('"', '').replace("'", "").strip()
                lines = [l.strip() for l in clean_content.splitlines() if l.strip()]
                target_text = lines[-1] if lines else clean_content

                # Check standard categories
                for cat in [
                    "Not Interested",
                    "Did Not Speak",
                    "Interested",
                    "Callback Requested",
                    "Positive",
                    "Negative",
                    "Neutral",
                    "Grievance",
                    "Inquiry",
                    "Not Connected",
                ]:
                    if cat.lower() in clean_content.lower():
                        return cat

                # Clean short 1-3 word classification
                words = target_text.split()
                if 0 < len(words) <= 3 and len(target_text) <= 30:
                    return target_text.title()
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
    """Async intent detection reading full conversation context with AI LLM and multilingual understanding."""
    gathered = gathered_context or {}

    # 0. Check manual user override - HIGHEST PRECEDENCE
    if gathered.get("user_intent_manual") is True:
        val = str(gathered.get("user_intent") or "").strip()
        if val:
            return val

    # Explicit qualification flags
    if (
        gathered.get("user_qualified") is True
        or (disposition or "").lower() in ("user_qualified", "qualified", "transfer_call", "xfer")
    ):
        return "Interested"
    if (
        gathered.get("user_qualified") is False
        or (disposition or "").lower() in ("disqualified", "not_qualified", "dnc")
    ):
        return "Not Interested"

    disposition_clean = (disposition or "").lower().strip()

    # 1. Unconnected calls (0s duration, busy, no-answer, failed, canceled)
    # Strictly reserved for 0-second / failed calls
    if duration <= 0 or disposition_clean in (
        "busy",
        "no-answer",
        "failed",
        "canceled",
        "cancelled",
        "initialized",
    ):
        return "Not Connected"

    # 2. Check if user actually spoke on this connected call
    has_user_speech = False
    if transcript_text and len(transcript_text.strip()) > 5:
        text_lower = transcript_text.lower()
        has_user_speech = any(
            marker in text_lower
            for marker in ["user:", "caller:", "human:", "speaker 1:", "[user]", "speaker 0:"]
        )

    # If call connected (duration > 0) but user NEVER spoke: show "Did Not Speak"
    if not has_user_speech:
        return "Did Not Speak"

    # 3. Extract agent instructions from workflow definition if not explicitly passed
    if not agent_instructions and workflow_definition:
        agent_instructions = extract_workflow_instructions(workflow_definition)

    # 4. Analyze Transcript with AI
    if transcript_text and len(transcript_text.strip()) > 5:
        llm_intent = await _analyze_intent_with_llm(
            transcript_text=transcript_text,
            organization_id=organization_id,
            agent_instructions=agent_instructions,
        )
        if llm_intent:
            # Prevent connected speaking calls from being labeled Not Connected or Did Not Speak
            if llm_intent == "Not Connected":
                return "Neutral"
            if llm_intent == "Did Not Speak" and has_user_speech:
                return "Neutral"
            return llm_intent

    # 5. Fallback heuristic
    if transcript_text and len(transcript_text.strip()) > 5:
        heuristic = detect_user_intent(
            gathered_context=gathered_context,
            transcript_text=transcript_text,
            disposition=disposition,
            duration=duration,
        )
        if heuristic:
            if heuristic == "Not Connected":
                return "Neutral"
            if heuristic == "Did Not Speak" and has_user_speech:
                return "Neutral"
            return heuristic

    # 6. Default for connected calls where user spoke
    return "Neutral"


def detect_user_intent(
    gathered_context: dict | None = None,
    transcript_text: str | None = None,
    disposition: str | None = None,
    duration: float = 0.0,
) -> str:
    """Detect user intent based on user's spoken words in transcript across English, Telugu, Hindi."""
    gathered = gathered_context or {}

    # 0. Check manual user override
    if gathered.get("user_intent_manual") is True:
        val = str(gathered.get("user_intent") or "").strip()
        if val:
            return val

    disposition_clean = (disposition or "").lower().strip()

    # 1. Not connected conditions: strictly duration <= 0 or unconnected statuses
    if duration <= 0 or disposition_clean in (
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

    # 2. Inspect spoken user turns in transcript
    if transcript_text and len(transcript_text.strip()) > 5:
        user_lines = []
        for line in transcript_text.splitlines():
            l_lower = line.lower()
            if any(l_lower.startswith(p) or f" {p}" in l_lower for p in ["user:", "caller:", "human:"]):
                user_lines.append(l_lower)

        if not user_lines:
            # Caller connected (>0s) but never spoke
            return "Did Not Speak"

        user_content = " ".join(user_lines)

        # Negative keywords (Telugu script, Hindi script, phonetic Telugu/Hindi, English)
        negative_words = [
            "not interested", "no interest", "don't call", "dont call", "stop calling",
            "vaddhu", "voddhu", "voddu", "vadhu", "nakko", "nahi chahiye", "nahi",
            "interest ledu", "avsaram ledu", "avasaram ledu", "waste", "call cheyodu",
            "వద్దు", "వద్దండి", "వద్దులెండి", "అవసరం లేదు", "చేయకండి", "చేయవద్దు", "ఇంట్రెస్ట్ లేదు",
            "లేదు", "రాంగ్ నెంబర్", "కాల్ చేయొద్దు", "నహీ", "నహీ చాహియే", "రోకో",
            "नहीं", "नहीं चाहिए", "मत करो", "बंद करो", "गलत नंबर",
        ]
        if any(w in user_content for w in negative_words):
            return "Not Interested"

        # Callback keywords
        callback_words = [
            "callback", "call back", "later", "driving", "meeting", "busy",
            "tarvata", "taruvatha", "malli cheyandi", "malli call", "repu cheyandi",
            "తర్వాత", "తరువాత", "రేపు", "మళ్ళీ", "మళ్లీ", "డ్రైవింగ్", "బిజీ", "తర్వాత చేయండి",
            "बाद में", "ड्राइविंग", "बिजी", "कल करो",
        ]
        if any(w in user_content for w in callback_words):
            return "Callback Requested"

        # Grievance keywords
        grievance_words = [
            "complaint", "grievance", "problem", "issue", "samasyalu", "samasya",
            "raledu", "bad", "daridram", "damage", "defect",
            "సమస్య", "కంప్లైంట్", "రాలేదు", "సరిగా లేదు", "గోల", "ఖరాబ్", "ఇబ్బంది",
            "शिकायत", "समस्या", "दिक्कत", "खराब",
        ]
        if any(w in user_content for w in grievance_words):
            return "Grievance"

        # Positive keywords (Telugu script, Hindi script, phonetic, English)
        positive_words = [
            "interested", "yes", "sure", "avunu", "ha", "haan", "cheppandi",
            "matladandi", "bagundi", "satisfactory", "santhuptikaram", "correct",
            "send details", "ok", "okay", "sare", "manchidi", "super",
            "బాగుంది", "బాగున్నాయి", "సరే", "చెప్పండి", "మాట్లాడండి", "అవును", "హా",
            "సంతోషం", "సంతృప్తికరంగా", "మంచిది", "పర్లేదు", "పర్లేదండి", "వివరాలు పంపండి",
            "हाँ", "अच्छा", "ठीक है", "बात करो", "बताओ", "चाहिए", "संतुष्ट",
        ]
        if any(w in user_content for w in positive_words):
            return "Interested"

        # If user spoke and engaged neutrally / greetings
        return "Neutral"

    # If call connected but no transcript
    return "Did Not Speak" if disposition_clean == "user_hangup" else "Neutral"



