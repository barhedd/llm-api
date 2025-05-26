from fastapi import APIRouter

from .right_router import router as rights_router
from .news_router import router as news_router

router = APIRouter()
router.include_router(rights_router, prefix="/rights", tags=["Rights"])
router.include_router(news_router, prefix="/news", tags=["News"])