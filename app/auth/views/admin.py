import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.utils import admin_required, current_user
from app.common.db import get_async_session
from app.common.templates import templates
from app.common.utils import flash

router = APIRouter(tags=["Admin"], include_in_schema=False)


@router.get("/admin", name="auth.admin")
@admin_required
async def admin_view(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Admin page for user management."""
    query = select(User).order_by(User.registered_at.desc())
    result = await session.execute(query)
    users = result.scalars().all()

    return templates.TemplateResponse(
        request, "auth/templates/admin.html", {"users": users}
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
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = select(User).filter(User.id == user_id)
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        flash(request, "User not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if target_user.is_admin:
        flash(request, "Cannot ban admin users", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    target_user.is_banned = not target_user.is_banned
    await session.commit()

    action = "banned" if target_user.is_banned else "unbanned"
    flash(request, f"User {action} successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.admin"),
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
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = select(User).filter(User.id == user_id)
    result = await session.execute(query)
    target_user = result.scalar_one_or_none()

    if not target_user:
        flash(request, "User not found", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if target_user.is_admin:
        flash(request, "Cannot delete admin users", "error")
        return RedirectResponse(
            url=request.url_for("auth.admin"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await session.delete(target_user)
    await session.commit()

    flash(request, "User deleted successfully", "success")
    return RedirectResponse(
        url=request.url_for("auth.admin"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
