from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jwt.exceptions import InvalidTokenError
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.constants import LOCAL_PROVIDER
from app.auth.models import Provider, User
from app.auth.providers.views import providers as list_of_sso_providers
from app.auth.serializers import (
    TokenDataSerializer,
    UserSerializer,
    UserSignUpSerializer,
)
from app.auth.utils import (
    add_user,
    authenticate_user,
    create_token,
    get_token_payload,
    optional_current_user,
    verify_and_get_password_hash,
)
from app.common.db import get_async_session
from app.common.exceptions import (
    AuthDuplicateError,
    FailedRegistrationError,
    UserNotVerifiedError,
    ValidationError,
)
from app.common.templates import templates
from app.common.utils import flash
from app.email.send import send_password_reset_email
from app.settings import settings

router = APIRouter(tags=["Auth"], include_in_schema=False)


@router.get("/logout", name="auth.logout", summary="Logout a user")
@router.post("/logout", name="auth.logout.post", summary="Logout a user")
async def logout(request: Request):
    """
    Logout a user.
    """
    try:
        response = RedirectResponse(
            url=request.url_for("index"), status_code=status.HTTP_303_SEE_OTHER
        )
        response.delete_cookie(settings.COOKIE_NAME)
        return response
    except Exception:
        logger.exception("Error logging user out")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.get("/login", name="auth.login", summary="Login as a user")
async def login_view(
    request: Request,
    user: Optional[User] = Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    if user:
        return RedirectResponse(
            url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER
        )

    # Check if there are any users
    user_count = await session.execute(select(func.count(User.id)))
    user_count = user_count.scalar()
    if user_count == 0:
        # Redirect to register if no users exist
        flash(request, "Please register the first user account", "info")
        return RedirectResponse(
            url=request.url_for("auth.register"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request,
        "auth/templates/login.html",
        {
            "list_of_sso_providers": list_of_sso_providers,
            "registration_disabled": settings.DISABLE_REGISTRATION,
        },
    )


@router.post("/login", name="auth.login.post", summary="Login as a user")
async def local_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Logs in a user using the local provider
    """

    try:
        user = await authenticate_user(
            session, email=email, password=password, provider=LOCAL_PROVIDER
        )
        if not user:
            flash(request, "Invalid email or password", "error")
            return RedirectResponse(
                url=request.url_for("auth.login"),
                status_code=status.HTTP_303_SEE_OTHER,
            )

        access_token = await create_token(
            TokenDataSerializer(
                user_id=user.id,
                email=user.email,
                provider_name=LOCAL_PROVIDER,
                token_type="access",
            ),
        )
        response = RedirectResponse(
            url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER
        )
        response.set_cookie(settings.COOKIE_NAME, access_token)
        return response

    except UserNotVerifiedError:
        # Is caught and handled in the global app exception handler
        raise

    except ValidationError as e:
        flash(request, str(e), "error")
        return RedirectResponse(
            url=request.url_for("auth.login"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except Exception:
        logger.exception("Error logging user in")
        flash(request, "Failed to log in", "error")
        return RedirectResponse(
            url=request.url_for("auth.login"),
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/register", name="auth.register", summary="Register a user")
async def register_view(
    request: Request,
    user: Optional[User] = Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    if user:
        return RedirectResponse(
            url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER
        )

    # Check if there are any users
    user_count = await session.execute(select(func.count(User.id)))
    user_count = user_count.scalar()

    # Allow registration if this is the first user or if registration is not disabled
    if user_count > 0 and settings.DISABLE_REGISTRATION:
        flash(request, "Registration is currently disabled", "error")
        return RedirectResponse(
            url=request.url_for("auth.login"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        "auth/templates/register.html",
        {
            "request": request,
            "list_of_sso_providers": list_of_sso_providers,
            "is_first_user": user_count == 0,
        },
    )


@router.post(
    "/register",
    name="auth.register.post",
    response_model=UserSerializer,
    summary="Register a user",
)
async def local_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Registers a user.
    """

    try:
        # Check if this is the first user
        query = select(User)
        result = await session.execute(query)
        is_first_user = result.first() is None

        # Block registration if disabled (except for first user)
        if not is_first_user and settings.DISABLE_REGISTRATION:
            flash(request, "Registration is currently disabled", "error")
            return RedirectResponse(
                url=request.url_for("auth.login"),
                status_code=status.HTTP_303_SEE_OTHER,
            )

        user_signup = UserSignUpSerializer(
            email=email, password=password, confirm_password=confirm_password
        )
        _ = await add_user(
            session,
            user_signup,
            LOCAL_PROVIDER,
            user_signup.email.split("@")[0],
        )

        # Make first user an admin
        if is_first_user:
            flash(
                request,
                "Registration successful! You may now log into the admin account",
                "success",
            )
        else:
            flash(
                request,
                "Registration successful! Please check your email to verify your account.",
                "success",
            )
        return RedirectResponse(
            url=request.url_for("auth.login"), status_code=status.HTTP_303_SEE_OTHER
        )

    except (FailedRegistrationError, AuthDuplicateError, ValidationError) as e:
        flash(request, str(e), "error")
        return RedirectResponse(
            url=request.url_for("auth.register"), status_code=status.HTTP_303_SEE_OTHER
        )

    except Exception:
        await session.rollback()
        logger.exception("Error creating user")
        flash(request, "An unexpected error occurred", "error")
        return RedirectResponse(
            url=request.url_for("auth.register"), status_code=status.HTTP_303_SEE_OTHER
        )


@router.get(
    "/forgot-password", name="auth.forgot_password", summary="Forgot password form"
)
async def forgot_password_view(
    request: Request, user: Optional[User] = Depends(optional_current_user)
):
    """Display the forgot password form."""
    if user:
        return RedirectResponse(
            url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER
        )

    return templates.TemplateResponse(
        request,
        "auth/templates/forgot_password.html",
    )


@router.post(
    "/forgot-password",
    name="auth.forgot_password.post",
    summary="Process forgot password",
)
async def forgot_password(
    request: Request,
    email: str = Form(...),
    user: Optional[User] = Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Process forgot password request and send reset email."""
    if user:
        return RedirectResponse(
            url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER
        )

    email = email.lower().strip()
    # Find the local provider for this email
    query = (
        select(Provider)
        .filter(Provider.email == email, Provider.name == LOCAL_PROVIDER)
        .options(selectinload(Provider.user))
    )
    result = await session.execute(query)
    provider = result.scalar_one_or_none()

    if not provider or not provider.user:
        # Don't reveal if email exists
        flash(
            request,
            "If your email is registered, you will receive password reset instructions",
            "success",
        )
        return RedirectResponse(
            url=request.url_for("auth.forgot_password"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Generate reset token
    reset_token = await create_token(
        TokenDataSerializer(
            user_id=provider.user.id,
            email=provider.email,
            provider_name=provider.name,
            token_type="reset",
        ),
        expires_delta=timedelta(seconds=settings.PASSWORD_RESET_LINK_EXPIRATION),
    )

    # Send reset email
    try:
        await send_password_reset_email(email, reset_token)
    except Exception:
        logger.exception("Error sending password reset email")
        flash(request, "Failed to send password reset email", "error")
        return RedirectResponse(
            url=request.url_for("auth.forgot_password"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    flash(
        request,
        "If your email is registered, you will receive password reset instructions",
        "success",
    )
    return RedirectResponse(
        url=request.url_for("auth.login"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/reset-password/{token}", name="auth.reset_password", summary="Reset password form"
)
async def reset_password_view(request: Request, token: str):
    """Display the reset password form."""
    try:
        await get_token_payload(token, "reset")
    except InvalidTokenError:
        flash(request, "Invalid or expired reset link. Please try again.", "error")
        return RedirectResponse(
            url=request.url_for("auth.forgot_password"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        "auth/templates/reset_password.html",
        {"request": request, "token": token},
    )


@router.post(
    "/reset-password/{token}",
    name="auth.reset_password.post",
    summary="Process password reset",
)
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """Process password reset request."""
    if password != confirm_password:
        flash(request, "Passwords do not match", "error")
        return RedirectResponse(
            url=request.url_for("auth.reset_password", token=token),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        token_data = await get_token_payload(token, "reset")
    except InvalidTokenError:
        flash(request, "Invalid or expired reset link. Please try again.", "error")
        return RedirectResponse(
            url=request.url_for("auth.forgot_password"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Update the user's password
    query = select(User).filter(User.id == token_data.user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        flash(request, "Invalid reset link. Please try again.", "error")
        return RedirectResponse(
            url=request.url_for("auth.forgot_password"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user.password = await verify_and_get_password_hash(password)
    try:
        await session.commit()
    except Exception:
        logger.exception("Error resetting password")
        flash(request, "Failed to reset password", "error")
        return RedirectResponse(
            url=request.url_for("auth.reset_password", token=token),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    flash(request, "Password has been reset successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.login"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
