from fastapi import APIRouter
from app.api.links import router as links_router

api_router = APIRouter()

api_router.include_router(links_router)