import os
import glob
import asyncio
import aiohttp
from sqlalchemy import select
from loguru import logger

from api.db.base_client import db_client
from api.db.models import TelephonyConfigurationModel

ASTERISK_CONFIG_DIR = os.environ.get("ASTERISK_CONFIG_DIR", "/etc/asterisk")
ASTERISK_ARI_PROXY_URL = os.environ.get("ASTERISK_ARI_PROXY_URL", "http://asterisk-ari-proxy:8088")

def _write_file_sync(file_path: str, content: str):
    with open(file_path, "w") as f:
        f.write(content)

def _delete_file_sync(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)

async def reload_asterisk_pjsip() -> bool:
    """Send reload command to Asterisk ARI Proxy."""
    url = f"{ASTERISK_ARI_PROXY_URL}/reload"
    logger.info(f"Triggering Asterisk PJSIP reload via: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status in (200, 204):
                    logger.info("Asterisk PJSIP reload successful.")
                    return True
                else:
                    body = await response.text()
                    logger.error(f"Asterisk reload returned status {response.status}: {body}")
    except Exception as e:
        logger.error(f"Failed to connect to Asterisk ARI proxy at {url}: {e}")
    return False

async def write_pjsip_trunk_config(config_id: int, provider: str, credentials: dict) -> bool:
    """Write PJSIP trunk configuration file for Asterisk."""
    if not os.path.exists(ASTERISK_CONFIG_DIR):
        logger.warning(f"Asterisk config dir '{ASTERISK_CONFIG_DIR}' not found. Cannot write PJSIP config.")
        return False

    pjsip_d = os.path.join(ASTERISK_CONFIG_DIR, "pjsip.d")
    os.makedirs(pjsip_d, exist_ok=True)

    sip_domain = credentials.get("sip_domain")
    username = credentials.get("username")
    password = credentials.get("password")

    if not sip_domain or not username or not password:
        logger.warning(f"Config {config_id} is missing sip_domain, username, or password. Cannot write PJSIP config.")
        return False

    config_content = f"""; Dynamic PJSIP configuration for {provider} Trunk {config_id}
[reg_{config_id}]
type=registration
transport=transport-udp
outbound_auth=auth_{config_id}
server_uri=sip:{sip_domain}
client_uri=sip:{username}@{sip_domain}
retry_interval=60

[auth_{config_id}]
type=auth
auth_type=userpass
username={username}
password={password}

[endpoint_{config_id}]
type=endpoint
transport=transport-udp
context=from-external
disallow=all
allow=ulaw
outbound_auth=auth_{config_id}
aors=aor_{config_id}
direct_media=no

[aor_{config_id}]
type=aor
contact=sip:{sip_domain}
"""
    file_path = os.path.join(pjsip_d, f"trunk_{config_id}.conf")
    try:
        await asyncio.to_thread(_write_file_sync, file_path, config_content)
        logger.info(f"Wrote Asterisk PJSIP config for trunk {config_id} to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write Asterisk PJSIP config for trunk {config_id}: {e}")
        return False

async def delete_pjsip_trunk_config(config_id: int) -> bool:
    """Delete PJSIP trunk configuration file for Asterisk."""
    if not os.path.exists(ASTERISK_CONFIG_DIR):
        return False

    file_path = os.path.join(ASTERISK_CONFIG_DIR, "pjsip.d", f"trunk_{config_id}.conf")
    try:
        await asyncio.to_thread(_delete_file_sync, file_path)
        logger.info(f"Deleted Asterisk PJSIP config for trunk {config_id} at {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete Asterisk PJSIP config for trunk {config_id}: {e}")
        return False

async def sync_sip_trunks() -> None:
    """Sync all active SIP trunk configs from database to Asterisk pjsip.d files."""
    if not os.path.exists(ASTERISK_CONFIG_DIR):
        logger.warning(f"Asterisk config directory '{ASTERISK_CONFIG_DIR}' not found. Dynamic SIP configurations disabled.")
        return

    pjsip_d = os.path.join(ASTERISK_CONFIG_DIR, "pjsip.d")
    os.makedirs(pjsip_d, exist_ok=True)

    logger.info("Synchronizing active database SIP trunks with Asterisk configurations...")

    try:
        async with db_client.async_session() as session:
            result = await session.execute(
                select(TelephonyConfigurationModel).where(
                    TelephonyConfigurationModel.provider.in_(["vobiz_sip", "twilio_sip"])
                )
            )
            rows = result.scalars().all()

        active_trunk_ids = set()
        write_success = False

        for row in rows:
            active_trunk_ids.add(row.id)
            success = await write_pjsip_trunk_config(row.id, row.provider, row.credentials)
            if success:
                write_success = True

        # Clean up stale configs
        existing_files = glob.glob(os.path.join(pjsip_d, "trunk_*.conf"))
        deleted_any = False
        for file_path in existing_files:
            file_name = os.path.basename(file_path)
            # Extract ID from trunk_{id}.conf
            try:
                trunk_id_str = file_name.replace("trunk_", "").replace(".conf", "")
                trunk_id = int(trunk_id_str)
                if trunk_id not in active_trunk_ids:
                    await asyncio.to_thread(_delete_file_sync, file_path)
                    logger.info(f"Cleaned up stale PJSIP config file: {file_path}")
                    deleted_any = True
            except ValueError:
                pass

        if write_success or deleted_any:
            await reload_asterisk_pjsip()

    except Exception as e:
        logger.error(f"Error during SIP trunk synchronization: {e}")
