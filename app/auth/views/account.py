import secrets
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.constants import LOCAL_PROVIDER
from app.auth.models import APIKey, APIKeyAccessLevel, Provider, User
from app.auth.providers.views import providers as list_of_sso_providers
from app.auth.serializers import TokenDataSerializer
from app.auth.utils import (
    create_token,
    current_user,
    verify_and_get_password_hash,
)
from app.common.db import get_async_session
from app.common.exceptions import ValidationError
from app.common.templates import templates
from app.common.utils import flash
from app.email.send import send_verification_email
from app.settings import settings

router = APIRouter(tags=["Account"], include_in_schema=False)


@router.get(
    "/account", name="auth.account_settings", summary="View user account settings"
)
async def account_settings_view(request: Request):
    """
    Redirect to profile settings page.
    """
    return RedirectResponse(
        url=request.url_for("auth.account_settings_profile"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/account/profile",
    name="auth.account_settings_profile",
    summary="View profile settings",
)
async def account_settings_profile_view(
    request: Request,
    user: User = Depends(current_user),
):
    """
    Display the user's profile settings page.
    """
    return templates.TemplateResponse(
        request,
        "auth/templates/account_settings_profile.html",
        {
            "pending_email": user.pending_email,
        },
    )


@router.get(
    "/account/providers",
    name="auth.account_settings_providers",
    summary="View provider settings",
)
async def account_settings_providers_view(
    request: Request,
    user: User = Depends(current_user),
):
    """
    Display the user's provider settings page.
    """
    return templates.TemplateResponse(
        request,
        "auth/templates/account_settings_providers.html",
        {
            "list_of_sso_providers": list_of_sso_providers,
        },
    )


@router.get(
    "/account/api-keys",
    name="auth.account_settings_api_keys",
    summary="View API key settings",
)
async def account_settings_api_keys_view(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Display the user's API key settings page.
    """
    # Get all active API keys
    query = select(APIKey).where(APIKey.user_id == user.id, APIKey.is_active)
    result = await session.execute(query)
    api_keys = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "auth/templates/account_settings_api_keys.html",
        {
            "api_keys": api_keys,
        },
    )


@router.get(
    "/account/delete",
    name="auth.account_settings_delete",
    summary="View delete account page",
)
async def account_settings_delete_view(
    request: Request,
    user: User = Depends(current_user),
):
    """
    Display the delete account page.
    """
    return templates.TemplateResponse(
        request,
        "auth/templates/account_settings_delete.html",
    )


@router.post(
    "/account/display-name",
    name="auth.update_display_name.post",
    summary="Update display name",
)
async def update_display_name(
    request: Request,
    display_name: str = Form(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update the user's display name.
    """
    query = select(User).filter(User.id == user.id)
    result = await session.execute(query)
    db_user = result.scalar_one()

    try:
        db_user.display_name = display_name
    except ValidationError as e:
        flash(request, str(e), "error")
        return RedirectResponse(
            url=request.url_for("auth.account_settings_profile"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Error updating display name")
        flash(request, "Failed to update display name", "error")
        return RedirectResponse(
            url=request.url_for("auth.account_settings_profile"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=request.url_for("auth.account_settings_profile"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/change-email", name="auth.change_email", summary="Change email form")
async def change_email_view(request: Request, user: User = Depends(current_user)):
    """
    Display the change email form.
    """
    return templates.TemplateResponse(request, "auth/templates/change_email.html")


@router.get(
    "/change-email/cancel",
    name="auth.change_email_cancel",
    summary="Cancel email change",
)
async def change_email_cancel(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Cancel the email change process.
    """

    user_query = select(User).filter(User.id == user.id)
    user_result = await session.execute(user_query)
    db_user = user_result.scalar_one()
    db_user.pending_email = None
    await session.commit()

    flash(request, "Email change has been cancelled", "info")
    return RedirectResponse(
        url=request.url_for("auth.account_settings_profile"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/change-email", name="auth.change_email.post", summary="Process email change"
)
async def change_email(
    request: Request,
    new_email: str = Form(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Initiate email change process. Sends verification email to new address.
    """
    new_email = new_email.strip().lower()
    if new_email == user.email:
        flash(request, "No change, email is the same", "info")
        return RedirectResponse(
            url=request.url_for("auth.change_email"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Confirm its a valid email
    try:
        _, new_email = validate_email(new_email)
    except ValueError:
        flash(request, "Invalid email address", "error")
        return RedirectResponse(
            url=request.url_for("auth.change_email"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check if email is used by any other users in the user or providers table
    user_query = select(User).filter(User.email == new_email, User.id != user.id)
    user_result = await session.execute(user_query)
    provider_query = select(Provider).filter(
        Provider.email == new_email, User.id != user.id
    )
    provider_result = await session.execute(provider_query)

    if user_result.first() or provider_result.first():
        flash(request, "Email is already in use", "error")
        return RedirectResponse(
            url=request.url_for("auth.change_email"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check if its already a verified email the user has
    user_providers_query = select(Provider).filter(
        Provider.user_id == user.id, Provider.email == new_email
    )
    user_providers_result = await session.execute(user_providers_query)
    user_providers = user_providers_result.scalars().all()
    if user_providers:
        if all(provider.is_verified for provider in user_providers):
            # All providers with this email are already verified
            # Update the users email and return
            user_query = select(User).filter(User.id == user.id)
            user_result = await session.execute(user_query)
            db_user = user_result.scalar_one()
            db_user.email = new_email
            await session.commit()
            return RedirectResponse(
                url=request.url_for("auth.account_settings_providers"),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        else:
            flash(request, "Must verify the pending provider request", "error")
            return RedirectResponse(
                url=request.url_for("auth.change_email"),
                status_code=status.HTTP_303_SEE_OTHER,
            )

    # Email is good to use, but needs to be verified
    # Update users pending email
    user_query = select(User).filter(User.id == user.id)
    user_result = await session.execute(user_query)
    db_user = user_result.scalar_one()
    db_user.pending_email = new_email
    await session.commit()

    # Create a token for the new email
    validation_token = await create_token(
        TokenDataSerializer(
            user_id=user.id,
            email=user.email,
            new_email=new_email,
            token_type="validation",
        )
    )
    await send_verification_email(
        new_email, validation_token, from_change_email=user.email
    )
    flash(
        request,
        "A verification email has been sent to the new email address",
        "success",
    )
    return RedirectResponse(
        url=request.url_for("auth.account_settings_profile"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/providers/local/connect",
    name="auth.connect_local",
    summary="Connect local provider",
)
async def connect_local_view(request: Request, user: User = Depends(current_user)):
    """
    Display the connect local provider page.
    """
    return templates.TemplateResponse(
        "auth/templates/connect_local.html",
        {"request": request, "user": user},
    )


@router.post(
    "/providers/local/connect",
    name="auth.connect_local.post",
    summary="Connect local provider",
)
async def connect_local(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """
    Connect local provider to existing account.
    """
    try:
        if password != confirm_password:
            raise ValidationError("Passwords do not match")

        # Add local provider
        provider = Provider(
            name=LOCAL_PROVIDER,
            email=user.email,
            user_id=user.id,
            is_verified=True,  # Already verified through existing provider
        )
        session.add(provider)

        # Set password for local auth
        # Need to get the user object in this session to update the password
        query = select(User).filter(User.id == user.id)
        result = await session.execute(query)
        db_user = result.scalar_one()
        db_user.password = await verify_and_get_password_hash(password)

        await session.commit()

    except Exception as e:
        if isinstance(e, ValidationError):
            flash(request, str(e), "error")
        else:
            logger.exception(f"Error connecting {LOCAL_PROVIDER} provider")
            flash(request, f"Failed to connect a {LOCAL_PROVIDER} provider", "error")

        await session.rollback()
        return RedirectResponse(
            url=request.url_for("auth.connect_local"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    flash(request, f"{LOCAL_PROVIDER.title()} provider connected", "success")
    return RedirectResponse(
        url=request.url_for("auth.account_settings_providers"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/providers/{provider}/disconnect",
    name="auth.disconnect_provider.post",
    summary="Disconnect an authentication provider",
)
async def disconnect_provider(
    provider: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Disconnect an authentication provider from the user's account.
    Ensures at least one provider remains connected.
    """
    if len(user.providers) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disconnect your only authentication provider.",
        )

    # Find and delete the provider
    query = (
        select(Provider)
        .filter(Provider.user_id == user.id)
        .filter(Provider.name == provider)
        .options(selectinload(Provider.user))
    )
    result = await session.execute(query)
    provider_to_remove = result.scalar_one_or_none()

    if not provider_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found"
        )

    if provider_to_remove.name == LOCAL_PROVIDER:
        # Clear the password since its only for the local provider
        # Need to use the user object through the provider row as the passed
        # in user object is in a different session
        provider_to_remove.user.password = None

    await session.delete(provider_to_remove)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Error disconnecting provider")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while disconnecting provider.",
        )

    return RedirectResponse(
        url=request.url_for("auth.account_settings_providers"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/api-keys", name="api_key.create.post")
async def create_api_key(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
    name: str = Form(...),
    access_level: APIKeyAccessLevel = Form(...),
):
    """Create a new API key."""
    try:
        # Generate a random API key
        api_key = secrets.token_urlsafe(32)

        # Create new API key record
        db_api_key = APIKey(
            key=api_key, name=name, user_id=user.id, access_level=access_level
        )
        session.add(db_api_key)
        await session.commit()

    except Exception as e:
        if isinstance(e, ValidationError):
            flash(request, str(e), level="error")
        else:
            flash(request, "An error occurred", level="error")
            logger.exception("Error creating api-key")
    else:
        flash(
            request,
            "API key created successfully",
            level="success",
            format="new_api_key",
            api_key=api_key,
        )

    return RedirectResponse(
        url=request.url_for("auth.account_settings_api_keys"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/api-keys/{key_id}/revoke", name="api_key.revoke.post")
async def revoke_api_key(
    request: Request,
    key_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Revoke an API key."""
    # First verify the key belongs to the user
    query = select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    result = await session.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Update the key to be inactive
    api_key.is_active = False
    await session.commit()

    return RedirectResponse(
        url=request.url_for("auth.account_settings_api_keys"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/delete", name="auth.delete_account.post", summary="Delete user account")
async def delete_account(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Permanently delete a user's account and all associated data.
    """
    try:
        # Delete the user (which will cascade delete providers, snippets, and api_keys)
        user_query = select(User).filter(User.id == user.id)
        result = await session.execute(user_query)
        user_to_delete = result.scalar_one_or_none()

        if not user_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # If user is admin, check if they are the only admin
        if user_to_delete.is_admin:
            admin_count_query = select(User).filter(User.is_admin)
            admin_result = await session.execute(admin_count_query)
            admin_users = admin_result.scalars().all()
            if len(admin_users) <= 1:
                flash(request, "Cannot delete the only admin account", "error")
                return RedirectResponse(
                    url=request.url_for("auth.account_settings"),
                    status_code=status.HTTP_303_SEE_OTHER,
                )

        await session.delete(user_to_delete)
        await session.commit()

        # Clear session cookie and redirect to home
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.COOKIE_NAME)
        return response

    except Exception:
        logger.exception("Error deleting account")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
