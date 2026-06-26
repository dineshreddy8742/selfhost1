import os
import json
from typing import Any, Dict, Optional
import aiohttp
from fastapi import HTTPException
from loguru import logger

from api.services.telephony.base import CallInitiationResult
from api.services.telephony.providers.ari.provider import ARIProvider

class SIPTrunkProvider(ARIProvider):
    """
    Subclass of ARIProvider that routes calls dynamically via an Asterisk Local channel.
    Injects SIP Trunk configurations (credentials, domain, CLI) at call time using channel variables.
    """

    def __init__(self, config: Dict[str, Any], provider_name: str):
        # Asterisk ARI connection configurations for the local self-hosted stack
        ari_endpoint = os.environ.get("ASTERISK_ARI_ENDPOINT", "http://asterisk-ari-proxy:8088")
        app_name = os.environ.get("ASTERISK_ARI_APP_NAME", "dograh")
        app_password = os.environ.get("ASTERISK_ARI_PASSWORD", "Reddy@7989")

        super().__init__({
            "ari_endpoint": ari_endpoint,
            "app_name": app_name,
            "app_password": app_password,
            "from_numbers": config.get("from_numbers", [])
        })

        self.provider_name = provider_name
        self.config_id = config.get("config_id")
        self.sip_domain = config.get("sip_domain")
        self.username = config.get("username")
        self.caller_id_num = config.get("caller_id_num")
        self.caller_id_name = config.get("caller_id_name", "")

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        from_number: Optional[str] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        """
        Initiate call by creating a Local channel in Asterisk.
        Asterisk executes the outbound dialplan context and resolves routing.
        """
        if not self.validate_config():
            raise ValueError(f"Asterisk ARI connection not properly configured for provider {self.provider_name}")

        endpoint = f"{self.base_url}/channels"

        # clean numbers
        to_clean = to_number.strip()
        
        # Route to default outbound context in Asterisk (extensions.conf)
        local_endpoint = f"Local/{to_clean}@default"

        app_args = ",".join(
            filter(
                None,
                [
                    f"workflow_run_id={workflow_run_id}",
                    f"workflow_id={kwargs.get('workflow_id', '')}",
                    f"user_id={kwargs.get('user_id', '')}",
                ],
            )
        )

        params = {
            "endpoint": local_endpoint,
            "app": self.app_name,
            "appArgs": app_args,
            "callerId": from_number or self.caller_id_num
        }

        # Send trunk details as channel variables so extensions.conf can read them
        body = {
            "variables": {
                "TRUNK_ID": str(self.config_id),
                "CALLER_ID_NUM": self.caller_id_num,
                "CALLER_ID_NAME": self.caller_id_name or "",
                "SIP_DOMAIN": self.sip_domain
            }
        }

        logger.info(
            f"[{self.provider_name.upper()} SIP] Placing call to {to_clean} via local Asterisk "
            f"using Trunk ID: {self.config_id}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                params=params,
                json=body,
                auth=self._get_auth(),
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    logger.error(
                        f"[{self.provider_name.upper()} SIP] Channel creation failed: "
                        f"HTTP {response.status} - {response_text}"
                    )
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Failed to create Asterisk channel for SIP dial: {response_text}",
                    )

                response_data = json.loads(response_text)
                channel_id = response_data.get("id", "")

                logger.info(f"[{self.provider_name.upper()} SIP] Asterisk channel created: {channel_id}")

                return CallInitiationResult(
                    call_id=channel_id,
                    status=response_data.get("state", "created"),
                    caller_number=from_number or self.caller_id_num,
                    provider_metadata={
                        "call_id": channel_id,
                        "channel_name": response_data.get("name", ""),
                    },
                    raw_response=response_data,
                )
