"""Vobiz telephony configuration schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VobizConfigurationRequest(BaseModel):
    """Request schema for Vobiz configuration."""

    provider: Literal["vobiz"] = Field(default="vobiz")
    auth_id: str = Field(..., description="Vobiz Account ID (e.g., MA_SYQRLN1K)")
    auth_token: str = Field(..., description="Vobiz Auth Token")
    application_id: Optional[str] = Field(
        default=None,
        description=(
            "Vobiz Application ID. The application's answer_url is updated "
            "when inbound workflows are attached to numbers on this account. "
            "If omitted, an application is auto-created on save and its id "
            "is stored on the configuration."
        ),
    )
    from_numbers: List[str] = Field(
        default_factory=list,
        description="List of Vobiz phone numbers (E.164 without + prefix)",
    )


class VobizConfigurationResponse(BaseModel):
    """Response schema for Vobiz configuration with masked sensitive fields."""

    provider: Literal["vobiz"] = Field(default="vobiz")
    auth_id: str  # Masked
    auth_token: str  # Masked
    application_id: Optional[str] = None
    from_numbers: List[str]


class VobizSIPConfigurationRequest(BaseModel):
    """Request schema for Vobiz SIP Trunk configuration."""

    provider: Literal["vobiz_sip"] = Field(default="vobiz_sip")
    sip_domain: str = Field(..., description="Vobiz SIP Domain (e.g., 455bdb01.sip.vobiz.ai)")
    username: str = Field(..., description="SIP Trunk Username")
    password: str = Field(..., description="SIP Trunk Password")
    caller_id_num: str = Field(..., description="Default Outbound Caller ID (E.164 with + prefix)")
    caller_id_name: Optional[str] = Field(default=None, description="Default Outbound Caller ID Display Name")
    from_numbers: List[str] = Field(
        default_factory=list,
        description="List of phone numbers bound to this SIP Trunk",
    )


class VobizSIPConfigurationResponse(BaseModel):
    """Response schema for Vobiz SIP Trunk configuration with masked sensitive fields."""

    provider: Literal["vobiz_sip"] = Field(default="vobiz_sip")
    sip_domain: str
    username: str  # Masked
    password: str  # Masked
    caller_id_num: str
    caller_id_name: Optional[str] = None
    from_numbers: List[str]

