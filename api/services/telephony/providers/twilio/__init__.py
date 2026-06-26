"""Twilio telephony provider package."""

from typing import Any, Dict

from api.services.telephony.registry import (
    ProviderSpec,
    ProviderUIField,
    ProviderUIMetadata,
    register,
)

from .config import (
    TwilioConfigurationRequest,
    TwilioConfigurationResponse,
    TwilioSIPConfigurationRequest,
    TwilioSIPConfigurationResponse,
)
from .provider import TwilioProvider
from .transport import create_transport
from api.services.telephony.providers.sip_trunk_provider import SIPTrunkProvider
from api.services.telephony.providers.ari.transport import create_transport as create_ari_transport


def _config_loader(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "twilio",
        "account_sid": value.get("account_sid"),
        "auth_token": value.get("auth_token"),
        "from_numbers": value.get("from_numbers", []),
        "amd_enabled": value.get("amd_enabled", False),
    }


_UI_METADATA = ProviderUIMetadata(
    display_name="Twilio (REST API)",
    docs_url="https://docs.dograh.com/integrations/telephony/twilio",
    fields=[
        ProviderUIField(
            name="account_sid",
            label="Account SID",
            type="text",
            sensitive=True,
            description="Twilio Account SID (starts with AC)",
        ),
        ProviderUIField(
            name="auth_token",
            label="Auth Token",
            type="password",
            sensitive=True,
            description="Twilio Auth Token",
        ),
        ProviderUIField(
            name="from_numbers",
            label="Phone Numbers",
            type="string-array",
            description="E.164-formatted Twilio phone numbers used for outbound calls",
        ),
        ProviderUIField(
            name="amd_enabled",
            label="Answering Machine Detection",
            type="boolean",
            description=(
                "Detect whether outbound calls are answered by a person or "
                "machine. Twilio may bill AMD as an additional per-call feature."
            ),
        ),
    ],
)


SPEC = ProviderSpec(
    name="twilio",
    provider_cls=TwilioProvider,
    config_loader=_config_loader,
    transport_factory=create_transport,
    transport_sample_rate=8000,
    config_request_cls=TwilioConfigurationRequest,
    ui_metadata=_UI_METADATA,
    config_response_cls=TwilioConfigurationResponse,
    account_id_credential_field="account_sid",
)

register(SPEC)


# ---------------------------------------------------------------------------
# Twilio SIP Trunk Provider Specification
# ---------------------------------------------------------------------------

class TwilioSIPProvider(SIPTrunkProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, provider_name="twilio_sip")


def _config_loader_sip(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "twilio_sip",
        "config_id": value.get("id"),
        "sip_domain": value.get("sip_domain"),
        "username": value.get("username"),
        "password": value.get("password"),
        "caller_id_num": value.get("caller_id_num"),
        "caller_id_name": value.get("caller_id_name"),
        "from_numbers": value.get("from_numbers", []),
    }


_UI_METADATA_SIP = ProviderUIMetadata(
    display_name="Twilio (SIP Trunk)",
    docs_url="https://docs.dograh.com/integrations/telephony/twilio",
    fields=[
        ProviderUIField(
            name="sip_domain",
            label="SIP Domain / Gateway",
            type="text",
            required=True,
            description="Twilio SIP termination URI (e.g., your-trunk.pstn.twilio.com)",
        ),
        ProviderUIField(
            name="username",
            label="SIP Username",
            type="text",
            required=True,
            description="Twilio SIP Trunk credential username",
        ),
        ProviderUIField(
            name="password",
            label="SIP Password",
            type="password",
            sensitive=True,
            required=True,
            description="Twilio SIP Trunk credential password",
        ),
        ProviderUIField(
            name="caller_id_num",
            label="Default Caller ID Number",
            type="text",
            required=True,
            description="Default outbound E.164 caller ID (with + prefix)",
        ),
        ProviderUIField(
            name="caller_id_name",
            label="Default Caller ID Name",
            type="text",
            required=False,
            description="Default outbound caller ID display name",
        ),
        # from_numbers is intentionally excluded from the UI form.
        # Phone numbers are managed via the dedicated phone-numbers page,
        # not inside the credentials edit dialog.
    ],
)


SPEC_SIP = ProviderSpec(
    name="twilio_sip",
    provider_cls=TwilioSIPProvider,
    config_loader=_config_loader_sip,
    transport_factory=create_ari_transport,
    transport_sample_rate=8000,
    config_request_cls=TwilioSIPConfigurationRequest,
    ui_metadata=_UI_METADATA_SIP,
    config_response_cls=TwilioSIPConfigurationResponse,
)

register(SPEC_SIP)


__all__ = [
    "SPEC",
    "SPEC_SIP",
    "TwilioConfigurationRequest",
    "TwilioConfigurationResponse",
    "TwilioSIPConfigurationRequest",
    "TwilioSIPConfigurationResponse",
    "TwilioProvider",
    "TwilioSIPProvider",
    "create_transport",
]

