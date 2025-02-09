from fastapi import APIRouter

from .account import router as account_router
from .admin import router as admin_router
from .auth import router as auth_router
from .verification import router as verification_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(account_router)
router.include_router(admin_router)
router.include_router(verification_router)
