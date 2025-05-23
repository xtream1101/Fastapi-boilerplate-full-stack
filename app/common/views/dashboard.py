from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.utils import current_user
from app.common.db import get_async_session
from app.common.templates import templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse, name="dashboard.index")
async def dashboard_index(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Dashboard overview page."""
    return templates.TemplateResponse(
        request,
        "common/templates/dashboard/index.html",
        {"active_section": "overview"},
    )
