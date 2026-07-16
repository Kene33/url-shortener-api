from fastapi import Request

from app.core.config import Settings
from app.db.redis.links import LinkCache
from app.db.sql.crud import SQLClient
from app.services.links import LinkService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> SQLClient:
    return request.app.state.database


def get_cache(request: Request) -> LinkCache:
    return request.app.state.cache


def get_link_service(request: Request) -> LinkService:
    return request.app.state.link_service
