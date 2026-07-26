from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from loguru import logger

from api.constants import GOOGLE_CLIENT_ID
from api.db import db_client
from api.db.models import UserModel
from api.enums import OrganizationConfigurationKey, PostHogEvent
from api.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    SignupRequest,
    UserResponse,
)
from api.services.auth.depends import create_user_configuration_with_mps_key, get_user
from api.services.configuration.ai_model_configuration import (
    convert_legacy_ai_model_configuration_to_v2,
)
from api.services.posthog_client import capture_event
from api.utils.auth import create_jwt_token, hash_password, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    # Check if email is already taken
    existing_user = await db_client.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Hash password and create user
    hashed = hash_password(request.password)
    user = await db_client.create_user_with_email(
        email=request.email,
        password_hash=hashed,
        name=request.name,
    )

    # Create organization for the user
    org_provider_id = f"org_{user.provider_id}"
    organization, _ = await db_client.get_or_create_organization_by_provider_id(
        org_provider_id=org_provider_id, user_id=user.id
    )

    # Link user to organization
    await db_client.add_user_to_organization(user.id, organization.id)
    await db_client.update_user_selected_organization(user.id, organization.id)

    # Create default service configuration
    try:
        mps_config = await create_user_configuration_with_mps_key(
            user.id, organization.id, user.provider_id
        )
        if mps_config:
            await db_client.update_user_configuration(user.id, mps_config)
            model_config_v2 = convert_legacy_ai_model_configuration_to_v2(mps_config)
            await db_client.upsert_configuration(
                organization.id,
                OrganizationConfigurationKey.MODEL_CONFIGURATION_V2.value,
                model_config_v2.model_dump(mode="json", exclude_none=True),
            )
    except Exception:
        logger.warning(
            "Failed to create default configuration for OSS user", exc_info=True
        )

    # Create JWT token
    token = create_jwt_token(user.id, request.email)

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_UP,
        properties={
            "organization_id": organization.id,
            "auth_provider": "local",
        },
    )

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=request.name,
            organization_id=organization.id,
            provider_id=user.provider_id,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    # Look up user by email
    user = await db_client.get_user_by_email(request.email)
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create JWT token
    token = create_jwt_token(user.id, user.email)

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_IN,
        properties={
            "organization_id": user.selected_organization_id,
            "auth_provider": "local",
        },
    )

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            organization_id=user.selected_organization_id,
            provider_id=user.provider_id,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: UserModel = Depends(get_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        organization_id=user.selected_organization_id,
        provider_id=user.provider_id,
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(request: GoogleLoginRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=400, detail="Google login is not configured"
        )

    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            request.credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        email = idinfo.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        name = idinfo.get("name")
    except ValueError as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    # Check if a user with this email already exists
    user = await db_client.get_user_by_email(email)
    
    if not user:
        # Create a new user (empty password hash indicates Google SSO)
        user = await db_client.create_user_with_email(
            email=email,
            password_hash="",
            name=name,
        )
        
        # Create organization for the user
        org_provider_id = f"org_{user.provider_id}"
        organization, _ = await db_client.get_or_create_organization_by_provider_id(
            org_provider_id=org_provider_id, user_id=user.id
        )

        # Link user to organization
        await db_client.add_user_to_organization(user.id, organization.id)
        await db_client.update_user_selected_organization(user.id, organization.id)

        # Create default service configuration
        try:
            mps_config = await create_user_configuration_with_mps_key(
                user.id, organization.id, user.provider_id
            )
            if mps_config:
                await db_client.update_user_configuration(user.id, mps_config)
                model_config_v2 = convert_legacy_ai_model_configuration_to_v2(mps_config)
                await db_client.upsert_configuration(
                    organization.id,
                    OrganizationConfigurationKey.MODEL_CONFIGURATION_V2.value,
                    model_config_v2.model_dump(mode="json", exclude_none=True),
                )
        except Exception:
            logger.warning(
                "Failed to create default configuration for Google SSO user", exc_info=True
            )
        org_id = organization.id
    else:
        org_id = user.selected_organization_id
        if not org_id:
            # Recreate/retrieve organization if missing
            org_provider_id = f"org_{user.provider_id}"
            organization, _ = await db_client.get_or_create_organization_by_provider_id(
                org_provider_id=org_provider_id, user_id=user.id
            )
            await db_client.add_user_to_organization(user.id, organization.id)
            await db_client.update_user_selected_organization(user.id, organization.id)
            org_id = organization.id

        # UserModel has no name column — nothing to update here

    # Create JWT token
    token = create_jwt_token(user.id, email)

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_IN,
        properties={
            "organization_id": org_id,
            "auth_provider": "google",
        },
    )

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            organization_id=org_id,
            provider_id=user.provider_id,
        ),
    )
