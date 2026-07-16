from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.links import router as links_router
from app.api.me import router as me_router

api_router = APIRouter()

api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(me_router)
api_router.include_router(links_router)
