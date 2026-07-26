from types import SimpleNamespace

import pytest
from pipecat.frames.frames import TranscriptionFrame, TTSTextFrame
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import TransportParams

from api.services.pipecat.realtime_feedback_observer import RealtimeFeedbackObserver


def _frame_pushed(frame, direction, *, source=None):
    return FramePushed(
        source=source or SimpleNamespace(),
        destination=SimpleNamespace(),
        frame=frame,
        direction=direction,
        timestamp=0,
    )


@pytest.mark.asyncio
async def test_observer_streams_upstream_only_transcription_frames():
    messages = []

    async def ws_sender(message):
        messages.append(message)

    observer = RealtimeFeedbackObserver(ws_sender=ws_sender)
    frame = TranscriptionFrame(
        "Hi there",
        user_id="user-1",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    await observer.on_push_frame(_frame_pushed(frame, FrameDirection.UPSTREAM))

    assert messages == [
        {
            "type": "rtf-user-transcription",
            "payload": {
                "text": "Hi there",
                "final": True,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "user_id": "user-1",
            },
        }
    ]


@pytest.mark.asyncio
async def test_observer_ignores_upstream_broadcast_transcription_sibling():
    messages = []

    async def ws_sender(message):
        messages.append(message)

    observer = RealtimeFeedbackObserver(ws_sender=ws_sender)
    frame = TranscriptionFrame(
        "Hi there",
        user_id="user-1",
        timestamp="2026-01-01T00:00:00+00:00",
    )
    frame.broadcast_sibling_id = 1234

    await observer.on_push_frame(_frame_pushed(frame, FrameDirection.UPSTREAM))

    assert messages == []


@pytest.mark.asyncio
async def test_observer_waits_for_tts_text_from_output_transport():
    messages = []

    async def ws_sender(message):
        messages.append(message)

    observer = RealtimeFeedbackObserver(ws_sender=ws_sender)
    frame = TTSTextFrame("Hello", aggregated_by="word")
    frame.pts = 123

    await observer.on_push_frame(_frame_pushed(frame, FrameDirection.DOWNSTREAM))
    assert messages == []

    output_transport = BaseOutputTransport(TransportParams())
    await observer.on_push_frame(
        _frame_pushed(
            frame,
            FrameDirection.DOWNSTREAM,
            source=output_transport,
        )
    )

    assert messages == [
        {
            "type": "rtf-bot-text",
            "payload": {"text": "Hello"},
        }
    ]


@pytest.mark.asyncio
async def test_register_turn_log_handlers():
    from api.services.pipecat.realtime_feedback_observer import register_turn_log_handlers

    class MockLogsBuffer:
        def __init__(self):
            self.events = []
            self.turn_count = 0

        def increment_turn(self):
            self.turn_count += 1

        async def append(self, event):
            self.events.append(event)

    class MockAggregator:
        def __init__(self, realtime_mode=False):
            self._realtime_service_mode = realtime_mode
            self.handlers = {}

        def event_handler(self, event_name):
            def decorator(func):
                self.handlers[event_name] = func
                return func
            return decorator

    # Case 1: Non-realtime mode
    logs_buffer = MockLogsBuffer()
    user_agg = MockAggregator(realtime_mode=False)
    assistant_agg = MockAggregator(realtime_mode=False)

    register_turn_log_handlers(logs_buffer, user_agg, assistant_agg)

    # Trigger on_user_turn_stopped in non-realtime
    message = SimpleNamespace(content="user input", timestamp="time1")
    await user_agg.handlers["on_user_turn_stopped"](user_agg, "strategy", message)

    assert logs_buffer.turn_count == 1
    assert len(logs_buffer.events) == 1
    assert logs_buffer.events[0]["type"] == "rtf-user-transcription"
    assert logs_buffer.events[0]["payload"]["text"] == "user input"

    # Case 2: Realtime mode
    logs_buffer_rt = MockLogsBuffer()
    user_agg_rt = MockAggregator(realtime_mode=True)
    assistant_agg_rt = MockAggregator(realtime_mode=True)

    register_turn_log_handlers(logs_buffer_rt, user_agg_rt, assistant_agg_rt)

    # Trigger on_user_turn_stopped in realtime -> should be ignored (no turn increment/event)
    await user_agg_rt.handlers["on_user_turn_stopped"](user_agg_rt, "strategy", message)
    assert logs_buffer_rt.turn_count == 0
    assert len(logs_buffer_rt.events) == 0

    # Trigger on_user_turn_message_added in realtime -> should be logged
    await user_agg_rt.handlers["on_user_turn_message_added"](user_agg_rt, message)
    assert logs_buffer_rt.turn_count == 1
    assert len(logs_buffer_rt.events) == 1
    assert logs_buffer_rt.events[0]["type"] == "rtf-user-transcription"
    assert logs_buffer_rt.events[0]["payload"]["text"] == "user input"
