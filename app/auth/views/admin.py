import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.constants import LOCAL_PROVIDER
from app.auth.models import Invitation, PasswordReset, User
from app.auth.utils import admin_required, current_user
from app.common.db import get_async_session
from app.common.templates import templates
from app.common.utils import flash
from app.email.send import (
    send_invitation_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from app.settings import settings

router = APIRouter(tags=["Admin"], include_in_schema=False)


@router.post("/admin/users/{user_id}/reset-password", name="auth.admin_reset_password")
@admin_required
async def admin_reset_password(
    request: Request,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Generate a password reset link for a user."""
    if user.id == user_id:
        flash(request, "Cannot reset your own password this way", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Get user with their providers
    query = (
        select(User).filter(User.id == user_id).options(selectinload(User.providers))
    )
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        flash(request, "User not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check if user has a local provider
    has_local_provider = any(p.name == LOCAL_PROVIDER for p in target_user.providers)
    if not has_local_provider:
        flash(request, "User does not have a password-based login", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Invalidate any existing active reset links for this user
    query = select(PasswordReset).filter(
        PasswordReset.user_id == target_user.id,
        PasswordReset.expires_at > datetime.now(timezone.utc),
        PasswordReset.used_at.is_(None),
    )
    result = await session.execute(query)
    existing_resets = result.scalars().all()

    # Mark existing reset links as used
    for reset in existing_resets:
        reset.used_at = datetime.now(timezone.utc)

    # Create new password reset record
    password_reset = PasswordReset(
        user_id=target_user.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=settings.PASSWORD_RESET_LINK_EXPIRATION),
    )
    session.add(password_reset)
    await session.commit()

    # Get the reset URL
    reset_url = str(request.url_for("auth.reset_password", token=password_reset.token))

    flash(
        request,
        "Password reset link created successfully",
        level="success",
        format="admin_password_reset_link",
        reset_url=reset_url,
    )
    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/invite", name="auth.invite_user")
@admin_required
async def invite_user(
    request: Request,
    email: str = Form(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new invitation."""
    if not settings.DISABLE_REGISTRATION:
        flash(request, "Registration is not disabled", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check if user already exists
    query = select(User).filter(User.email == email.lower().strip())
    result = await session.execute(query)
    if result.scalar_one_or_none():
        flash(request, "User with this email already exists", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Check for existing non-expired invitation
    query = select(Invitation).filter(
        Invitation.email == email.lower().strip(),
        Invitation.expires_at > datetime.now(timezone.utc),
        Invitation.used_at.is_(None),
    )
    result = await session.execute(query)
    if result.scalar_one_or_none():
        flash(request, "An active invitation already exists for this email", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Create invitation
    invitation = Invitation(email=email, created_by_id=user.id)
    session.add(invitation)
    await session.commit()

    # Send invitation email if SMTP is configured
    if settings.SMTP_HOST:
        try:
            await send_invitation_email(
                email=invitation.email,
                invitation_link=invitation.get_invitation_link(request),
            )
            invitation.email_sent = True
            await session.commit()
            flash(request, "Invitation sent successfully", "success")
        except Exception as e:
            flash(
                request,
                f"Invitation created but email could not be sent: {str(e)}",
                "warning",
            )
    else:
        flash(
            request,
            "Invitation created. Email sending is not configured - share the invitation link manually.",
            "warning",
        )

    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/invitations/{invitation_id}/resend", name="auth.resend_invitation")
@admin_required
async def resend_invitation(
    request: Request,
    invitation_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Resend an invitation email."""
    if not settings.SMTP_HOST:
        flash(request, "Email sending is not configured", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = select(Invitation).filter(Invitation.id == invitation_id)
    result = await session.execute(query)
    invitation = result.scalar_one_or_none()

    if not invitation:
        flash(request, "Invitation not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if invitation.is_used:
        flash(request, "Invitation has already been used", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if invitation.is_expired:
        flash(request, "Invitation has expired", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        await send_invitation_email(
            email=invitation.email,
            invitation_link=invitation.get_invitation_link(request),
        )
        invitation.email_sent = True
        await session.commit()
        flash(request, "Invitation email resent successfully", "success")
    except Exception as e:
        flash(request, f"Failed to send invitation email: {str(e)}", "error")

    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/debug/send-test-email", name="auth.send_test_email")
@admin_required
async def send_test_email(
    request: Request,
    email_type: str = Form(...),
    test_email: str = Form(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Send a test email of the specified type."""
    if not settings.SMTP_HOST:
        flash(request, "Email sending is not configured", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_email"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        if email_type == "welcome":
            await send_welcome_email(test_email, subject_prefix="[Test] ")
        elif email_type == "verification":
            # Create a dummy validation token
            validation_token = str(uuid.uuid4())
            await send_verification_email(
                test_email, validation_token, subject_prefix="[Test] "
            )
        elif email_type == "password_reset":
            # Create a dummy reset token
            reset_token = str(uuid.uuid4())
            await send_password_reset_email(
                test_email, reset_token, subject_prefix="[Test] "
            )
        elif email_type == "invitation":
            # Create a dummy invitation link
            invitation_link = f"{settings.HOST}/register?invitation={uuid.uuid4()}"
            await send_invitation_email(
                test_email, invitation_link, subject_prefix="[Test] "
            )
        else:
            flash(request, f"Unknown email type: {email_type}", "error")
            return RedirectResponse(
                url=request.url_for("auth.admin_email"),
                status_code=status.HTTP_303_SEE_OTHER,
            )

        flash(request, f"Test {email_type} email sent successfully", "success")
    except Exception as e:
        flash(request, f"Failed to send test email: {str(e)}", "error")

    return RedirectResponse(
        url=request.url_for("auth.admin_email"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/admin", name="auth.admin", summary="Default admin view")
async def admin_view(request: Request):
    """
    Redirect to profile settings page.
    """
    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/admin/users", name="auth.admin_users")
@admin_required
async def admin_users_view(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Admin page for user management."""
    query = (
        select(User)
        .options(selectinload(User.providers))
        .order_by(User.registered_at.desc())
    )
    result = await session.execute(query)
    users = result.scalars().all()

    # Get active invitations if registration is disabled
    invitations = []
    if settings.DISABLE_REGISTRATION:
        query = (
            select(Invitation)
            .order_by(Invitation.created_at.desc())
            .where(
                Invitation.expires_at > datetime.now(timezone.utc),
                Invitation.used_at.is_(None),
            )
        )
        result = await session.execute(query)
        invitations = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "auth/templates/admin_users.html",
        {"users": users, "invitations": invitations},
    )


@router.get("/admin/email", name="auth.admin_email")
@admin_required
async def admin_email_view(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Admin page for user management."""
    return templates.TemplateResponse(
        request,
        "auth/templates/admin_email.html",
        {},
    )


@router.post("/admin/users/{user_id}/ban", name="auth.toggle_user_ban")
@admin_required
async def toggle_user_ban(
    request: Request,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Toggle user ban status."""
    if user.id == user_id:
        flash(request, "Cannot ban yourself", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = select(User).filter(User.id == user_id)
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        flash(request, "User not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if target_user.is_admin:
        flash(request, "Cannot ban admin users", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    target_user.is_banned = not target_user.is_banned
    await session.commit()

    action = "banned" if target_user.is_banned else "unbanned"
    flash(request, f"User {action} successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/invitations/{invitation_id}/delete", name="auth.delete_invitation")
@admin_required
async def delete_invitation(
    request: Request,
    invitation_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete an invitation."""
    query = select(Invitation).filter(Invitation.id == invitation_id)
    result = await session.execute(query)
    invitation = result.scalar_one_or_none()

    if not invitation:
        flash(request, "Invitation not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await session.delete(invitation)
    await session.commit()

    flash(request, "Invitation deleted successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/users/{user_id}/delete", name="auth.delete_user")
@admin_required
async def delete_user(
    request: Request,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a user."""
    if user.id == user_id:
        flash(request, "Cannot delete yourself", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = select(User).filter(User.id == user_id)
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        flash(request, "User not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if target_user.is_admin:
        flash(request, "Cannot delete admin users", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin_users"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await session.delete(target_user)
    await session.commit()

    flash(request, "User deleted successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.admin_users"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
