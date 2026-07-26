"""ARI (Asterisk) transport factory."""

import os
from fastapi import WebSocket
from loguru import logger
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from api.db import db_client
from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.audio_mixer import build_audio_out_mixer
from api.services.pipecat.transport_params import realtime_param_overrides
from api.services.telephony.factory import load_credentials_for_transport

from .serializers import AsteriskFrameSerializer
from .strategies import ARIBridgeSwapStrategy, ARIHangupStrategy


async def create_transport(
    websocket: WebSocket,
    workflow_run_id: int,
    audio_config: AudioConfig,
    organization_id: int,
    *,
    ambient_noise_config: dict | None = None,
    telephony_configuration_id: int | None = None,
    is_realtime: bool = False,
    channel_id: str,
):
    # Dynamically resolve the provider type from the DB configuration
    provider_name = "ari"
    if telephony_configuration_id is not None:
        try:
            cfg_id = int(telephony_configuration_id)
            row = await db_client.get_telephony_configuration_for_org(cfg_id, organization_id)
            if row:
                provider_name = row.provider
        except Exception as e:
            logger.warning(f"Failed to lookup provider for config {telephony_configuration_id}: {e}")
    else:
        try:
            row = await db_client.get_default_telephony_configuration(organization_id)
            if row:
                provider_name = row.provider
        except Exception as e:
            logger.warning(f"Failed to lookup default provider: {e}")

    logger.info(f"[run {workflow_run_id}] Loading transport credentials for provider: {provider_name}")
    config = await load_credentials_for_transport(
        organization_id, telephony_configuration_id, expected_provider=provider_name
    )

    if provider_name == "ari":
        ari_endpoint = config.get("ari_endpoint")
        app_name = config.get("app_name")
        app_password = config.get("app_password")
    else:
        # For self-hosted Asterisk integration (e.g. vobiz_sip, twilio_sip),
        # Asterisk connection credentials come from environment variables.
        ari_endpoint = os.environ.get("ASTERISK_ARI_ENDPOINT", "http://asterisk-ari-proxy:8088")
        app_name = os.environ.get("ASTERISK_ARI_APP_NAME", "dograh")
        app_password = os.environ.get("ASTERISK_ARI_PASSWORD", "Reddy@7989")

    if not ari_endpoint or not app_name or not app_password:
        raise ValueError(
            f"Incomplete ARI configuration for organization {organization_id}. "
            f"Required: ari_endpoint, app_name, app_password"
        )

    serializer = AsteriskFrameSerializer(
        channel_id=channel_id,
        ari_endpoint=ari_endpoint,
        app_name=app_name,
        app_password=app_password,
        transfer_strategy=ARIBridgeSwapStrategy(),
        hangup_strategy=ARIHangupStrategy(),
        params=AsteriskFrameSerializer.InputParams(
            asterisk_sample_rate=audio_config.transport_in_sample_rate,
            sample_rate=audio_config.pipeline_sample_rate,
        ),
    )

    mixer = await build_audio_out_mixer(
        audio_config.transport_out_sample_rate, ambient_noise_config
    )

    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=audio_config.transport_in_sample_rate,
            audio_out_sample_rate=audio_config.transport_out_sample_rate,
            audio_out_mixer=mixer,
            serializer=serializer,
            **realtime_param_overrides(is_realtime),
        ),
    )
