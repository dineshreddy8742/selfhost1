"""Plivo telephony configuration schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PlivoConfigurationRequest(BaseModel):
    """Request schema for Plivo configuration."""

    provider: Literal["plivo"] = Field(default="plivo")
    auth_id: str = Field(..., description="Plivo Auth ID")
    auth_token: str = Field(..., description="Plivo Auth Token")
    application_id: Optional[str] = Field(
        default=None,
        description=(
            "Plivo Application ID. The application's answer_url is updated "
            "when inbound workflows are attached to numbers on this account. "
            "If omitted, an application is auto-created on save and its id "
            "is stored on the configuration."
        ),
    )
    from_numbers: List[str] = Field(
        default_factory=list, description="List of Plivo phone numbers"
    )


class PlivoConfigurationResponse(BaseModel):
    """Response schema for Plivo configuration with masked sensitive fields."""

    provider: Literal["plivo"] = Field(default="plivo")
    auth_id: str  # Masked
    auth_token: str  # Masked
    application_id: Optional[str] = None
    from_numbers: List[str]


class PlivoSIPConfigurationRequest(BaseModel):
    """Request schema for Plivo SIP Trunk configuration."""

    provider: Literal["plivo_sip"] = Field(default="plivo_sip")
    sip_domain: str = Field(..., description="Plivo SIP Domain (e.g., your-trunk.sip.plivo.com)")
    username: str = Field(..., description="SIP Trunk Username")
    password: str = Field(..., description="SIP Trunk Password")
    caller_id_num: str = Field(..., description="Default Outbound Caller ID (E.164 with + prefix)")
    caller_id_name: Optional[str] = Field(default=None, description="Default Outbound Caller ID Display Name")
    from_numbers: List[str] = Field(
        default_factory=list,
        description="List of phone numbers bound to this SIP Trunk",
    )


class PlivoSIPConfigurationResponse(BaseModel):
    """Response schema for Plivo SIP Trunk configuration with masked sensitive fields."""

    provider: Literal["plivo_sip"] = Field(default="plivo_sip")
    sip_domain: str
    username: str  # Masked
    password: str  # Masked
    caller_id_num: str
    caller_id_name: Optional[str] = None
    from_numbers: List[str]
