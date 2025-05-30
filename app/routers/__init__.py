from fastapi import APIRouter

from .right_router import router as rights_router
from .news_router import router as news_router
from .analysis_router import router as analysis_router
from .analysis_right_router import router as analysis_right_router

router = APIRouter()
router.include_router(rights_router, prefix="/rights", tags=["Rights"])
router.include_router(news_router, prefix="/news", tags=["News"])
router.include_router(analysis_router, prefix="/analysis", tags=["Analysis"])
#router.include_router(analysis_right_router, prefix="/analysisright", tags=["Analysis_Right"])