import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import api.services.configuration.ai_model_configuration
from api.utils.transcript import detect_user_intent, detect_user_intent_async, _analyze_intent_with_llm


def test_heuristic_no_user_speech_short_call():
    """Test that a call where duration > 0 but only the bot speaks returns Did Not Speak."""
    transcript = "[2026-09-28T14:23:28] assistant: నమస్కారం అండి... తిరుమల తిరుపతి దేవస్థానం తరఫున మీకు కాల్ చేశాను."
    res = detect_user_intent(
        gathered_context={},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=11.0,
    )
    assert res == "Did Not Speak"


def test_heuristic_zero_duration_not_connected():
    """Test that 0 seconds or unconnected disposition returns Not Connected."""
    res = detect_user_intent(
        gathered_context={},
        transcript_text="",
        disposition="busy",
        duration=0.0,
    )
    assert res == "Not Connected"


def test_heuristic_telugu_positive():
    """Test Telugu positive keywords return Interested."""
    transcript = (
        "[2026-09-28T14:22:16] assistant: మాట్లాడవచ్చా అండి?\n"
        "[2026-09-28T14:22:19] user: చెప్పండి బాగుంది"
    )
    res = detect_user_intent(
        gathered_context={},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=35.0,
    )
    assert res == "Interested"


def test_heuristic_telugu_negative():
    """Test Telugu negative keywords return Not Interested."""
    transcript = (
        "[2026-09-28T14:22:16] assistant: మాట్లాడవచ్చా అండి?\n"
        "[2026-09-28T14:22:19] user: నాకు అవసరం లేదు vaddhu"
    )
    res = detect_user_intent(
        gathered_context={},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=20.0,
    )
    assert res == "Not Interested"


def test_heuristic_callback_requested():
    """Test callback keywords return Callback Requested."""
    transcript = (
        "[2026-09-28T14:22:16] assistant: మాట్లాడవచ్చా అండి?\n"
        "[2026-09-28T14:22:19] user: ఇప్పుడు డ్రైవింగ్ లో ఉన్నాను repu cheyandi"
    )
    res = detect_user_intent(
        gathered_context={},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=25.0,
    )
    assert res == "Callback Requested"


def test_heuristic_grievance():
    """Test grievance keywords return Grievance."""
    transcript = (
        "[2026-09-28T14:22:16] assistant: మాట్లాడవచ్చా అండి?\n"
        "[2026-09-28T14:22:19] user: మాకు పెద్ద సమస్య ఉంది complaint ఇవ్వాలి"
    )
    res = detect_user_intent(
        gathered_context={},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=40.0,
    )
    assert res == "Grievance"


@pytest.mark.asyncio
async def test_detect_user_intent_async_manual_override():
    """Test that manual override in gathered_context is strictly respected."""
    res = await detect_user_intent_async(
        gathered_context={"user_intent": "Interested", "user_intent_manual": True},
        transcript_text="user: vaddhu",
        disposition="user_hangup",
        duration=15.0,
    )
    assert res == "Interested"


@pytest.mark.asyncio
async def test_detect_user_intent_async_no_user_speech_run_126652():
    """Test run 126652 scenario: 11 seconds, only assistant spoke, user hangup -> Did Not Speak."""
    transcript = "[2026-09-28T14:23:28] assistant: నమస్కారం అండి... తిరుమల తిరుపతి దేవస్థానం తరఫున మీ యాత్ర అనుభవం గురించి ఒక చిన్న అభిప్రాయం తెలుసుకోవడానికి మీకు కాల్ చేశాను."
    res = await detect_user_intent_async(
        gathered_context={"call_disposition": "user_hangup", "mapped_call_disposition": "user_hangup"},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=11.0,
        organization_id=1,
    )
    assert res == "Did Not Speak"


@pytest.mark.asyncio
async def test_detect_user_intent_async_hello_only_run_126651():
    """Test run 126651 scenario: 17 seconds, user said hello -> Neutral."""
    transcript = (
        "[2026-09-28T14:20:10] assistant: నమస్కారం అండి...\n"
        "[2026-09-28T14:20:12] user: హలో"
    )
    res = await detect_user_intent_async(
        gathered_context={"call_disposition": "user_hangup", "mapped_call_disposition": "user_hangup"},
        transcript_text=transcript,
        disposition="user_hangup",
        duration=17.0,
        organization_id=1,
    )
    assert res == "Neutral"


@pytest.mark.asyncio
async def test_llm_intent_analysis_mocked():
    """Test that _analyze_intent_with_llm parses choices and returns clean intent."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Interested",
                    "reasoning_content": None,
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        with patch("api.services.configuration.ai_model_configuration.get_organization_ai_model_configuration_v2") as mock_cfg:
            mock_v2 = MagicMock()
            mock_v2.mode = "byok"
            mock_v2.byok.mode = "realtime"
            mock_v2.byok.realtime.llm.provider = "sarvam"
            mock_v2.byok.realtime.llm.model = "sarvam-105b-conversations"
            mock_v2.byok.realtime.llm.api_key = ["sk_test_key_123"]
            mock_v2.byok.realtime.llm.endpoint = None
            mock_v2.byok.realtime.llm.base_url = None
            mock_cfg.return_value = mock_v2

            transcript = (
                "[2026-09-28] assistant: Would you like to schedule a demo?\n"
                "[2026-09-28] user: Yes please, tomorrow afternoon works best."
            )
            intent = await _analyze_intent_with_llm(
                transcript_text=transcript,
                organization_id=1,
            )
            assert intent == "Interested"


@pytest.mark.asyncio
async def test_detect_user_intent_async_full_dialogue_with_llm():
    """Test detect_user_intent_async with full dialogue correctly invokes AI analysis."""
    transcript = (
        "[2026-09-28T08:51:01] assistant: నమస్కారం అండి... తిరుమల యాత్ర గురించి అభిప్రాయం చెప్పగలరా?\n"
        "[2026-09-28T08:51:06] user: చెప్పండి.\n"
        "[2026-09-28T08:51:10] assistant: దర్శనం ఎలా ఉంది?\n"
        "[2026-09-28T08:51:14] user: పర్లేదండి బాగుంది."
    )
    with patch("api.utils.transcript._analyze_intent_with_llm", new=AsyncMock(return_value="Neutral")):
        res = await detect_user_intent_async(
            gathered_context={},
            transcript_text=transcript,
            disposition="user_hangup",
            duration=35.0,
            organization_id=1,
        )
        assert res == "Neutral"
