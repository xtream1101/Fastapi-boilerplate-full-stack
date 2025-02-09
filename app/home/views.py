from fastapi import APIRouter

router = APIRouter(tags=["Home"], include_in_schema=False)
