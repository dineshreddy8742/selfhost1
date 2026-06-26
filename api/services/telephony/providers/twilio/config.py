"""Twilio telephony configuration schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TwilioConfigurationRequest(BaseModel):
    """Request schema for Twilio configuration."""

    provider: Literal["twilio"] = Field(default="twilio")
    account_sid: str = Field(..., description="Twilio Account SID")
    auth_token: str = Field(..., description="Twilio Auth Token")
    # Phone numbers are managed via the dedicated phone-numbers endpoints; the
    # legacy /telephony-config POST shim still accepts them inline.
    from_numbers: List[str] = Field(
        default_factory=list, description="List of Twilio phone numbers"
    )
    amd_enabled: bool = Field(
        default=False,
        description=(
            "Detect whether outbound calls are answered by a person or machine. "
            "Twilio may bill AMD as an additional per-call feature."
        ),
    )


class TwilioConfigurationResponse(BaseModel):
    """Response schema for Twilio configuration with masked sensitive fields."""

    provider: Literal["twilio"] = Field(default="twilio")
    account_sid: str  # Masked (e.g., "****************def0")
    auth_token: str  # Masked (e.g., "****************abc1")
    from_numbers: List[str]
    amd_enabled: bool = False


class TwilioSIPConfigurationRequest(BaseModel):
    """Request schema for Twilio SIP Trunk configuration."""

    provider: Literal["twilio_sip"] = Field(default="twilio_sip")
    sip_domain: str = Field(..., description="Twilio SIP termination URI (e.g., your-trunk.pstn.twilio.com)")
    username: str = Field(..., description="SIP Trunk Username")
    password: str = Field(..., description="SIP Trunk Password")
    caller_id_num: str = Field(..., description="Default Outbound Caller ID (E.164 with + prefix)")
    caller_id_name: Optional[str] = Field(default=None, description="Default Outbound Caller ID Display Name")
    from_numbers: List[str] = Field(
        default_factory=list,
        description="List of phone numbers bound to this SIP Trunk",
    )


class TwilioSIPConfigurationResponse(BaseModel):
    """Response schema for Twilio SIP Trunk configuration with masked sensitive fields."""

    provider: Literal["twilio_sip"] = Field(default="twilio_sip")
    sip_domain: str
    username: str  # Masked
    password: str  # Masked
    caller_id_num: str
    caller_id_name: Optional[str] = None
    from_numbers: List[str]

