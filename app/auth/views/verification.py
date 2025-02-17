from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jwt.exceptions import InvalidTokenError
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.constants import LOCAL_PROVIDER
from app.auth.models import Provider, User
from app.auth.serializers import TokenDataSerializer
from app.auth.utils import create_token, get_token_payload, optional_current_user
from app.common.db import get_async_session
from app.common.templates import templates
from app.common.utils import flash
from app.email.send import send_verification_email

router = APIRouter(tags=["Email Verification"], include_in_schema=False)


@router.get("/verify", name="auth.verify_email", summary="Verify a user's email")
async def verify_email(
    request: Request, token: str, session: AsyncSession = Depends(get_async_session)
):
    """
    Verify a user's email.
    """

    try:
        token_data = await get_token_payload(token, "validation")
    except InvalidTokenError as e:
        flash(request, str(e), "error")
        return RedirectResponse(
            request.url_for("auth.login"), status_code=status.HTTP_303_SEE_OTHER
        )

    if token_data.provider_name is not None:
        # Validating a provider email
        provider_query = select(Provider).filter(
            Provider.name == token_data.provider_name,
            Provider.email == token_data.email,
        )
        result = await session.execute(provider_query)
        provider = result.scalar_one()
        provider.is_verified = True

    elif token_data.new_email is not None:
        new_email = token_data.new_email.lower().strip()
        # Validating a user email
        user_query = select(User).filter(
            User.id == token_data.user_id, User.pending_email == new_email
        )
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()
        if not user:
            flash(request, "Invalid email verification link", "error")
            return RedirectResponse(
                request.url_for("auth.account_settings_profile"),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        user.email = new_email
        user.pending_email = None

        # Check if there is a local provider that needs to get updated as well
        local_provider_query = select(Provider).filter(
            Provider.user_id == user.id, Provider.name == LOCAL_PROVIDER
        )
        result = await session.execute(local_provider_query)
        local_provider = result.scalar_one_or_none()
        if local_provider:
            local_provider.email = new_email

    try:
        await session.commit()
    except Exception:
        logger.exception("Error verifying email")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    flash(request, "Email has been verified", "success")
    return RedirectResponse(
        request.url_for("auth.account_settings_providers"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/verify/send",
    name="auth.send_verify_email.post",
    summary="Re-send a user's verification email",
)
async def resend_verification_email(
    request: Request,
    email: str = Form(...),
    provider_name: str = Form(...),
    user: User = Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    # Always say the email has been sent, even if nothing was sent
    flash(request, "Verification email has been sent", "success")
    redirect_url = "auth.account_settings_providers" if user else "auth.login"

    # First check if email is in our system and its already verified
    provider_query = select(Provider).filter(
        Provider.email == email,
        Provider.name == provider_name,
        Provider.is_verified,
    )
    result = await session.execute(provider_query)
    provider = result.scalar_one_or_none()

    if provider:
        return RedirectResponse(
            request.url_for(redirect_url), status_code=status.HTTP_303_SEE_OTHER
        )

    # Good to send the email verification
    validation_token = await create_token(
        TokenDataSerializer(
            email=email,
            provider_name=provider_name,
            token_type="validation",
        )
    )
    await send_verification_email(email, validation_token)
    return RedirectResponse(
        request.url_for(redirect_url), status_code=status.HTTP_303_SEE_OTHER
    )


@router.get(
    "/resend-verification",
    name="auth.resend_verification",
    summary="Resend verification email",
)
async def resend_verification_view(
    request: Request,
    provider: str,
    email: str,
    user: User = Depends(optional_current_user),
):
    """
    Display the resend verification email page.
    """
    return templates.TemplateResponse(
        "auth/templates/resend_verification.html",
        {"request": request, "provider": provider, "email": email},
    )
