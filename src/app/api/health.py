import sqlite3

from fastapi import APIRouter, Depends, Response, status
from redis.exceptions import RedisError

from app.api.dependencies import get_cache, get_database
from app.db.redis.links import LinkCache
from app.db.sql.crud import SQLClient
from app.schemas.links import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Проверить работу процесса",
    description=(
        "Возвращает `200`, если процесс API запущен. Проверка не обращается "
        "к SQLite или Redis."
    ),
    response_description="Процесс API работает",
    operation_id="health_liveness",
)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Проверить готовность сервиса",
    description=(
        "Проверяет обязательную SQLite и необязательный Redis. Недоступный Redis "
        "даёт состояние `degraded` с кодом `200`; недоступная SQLite — "
        "`unavailable` с кодом `503`."
    ),
    response_description="SQLite доступна; Redis может быть доступен или degraded",
    operation_id="health_readiness",
    responses={
        503: {
            "model": ReadinessResponse,
            "description": "Required SQLite storage is unavailable",
        }
    },
)
async def readiness(
    response: Response,
    database: SQLClient = Depends(get_database),
    cache: LinkCache = Depends(get_cache),
) -> ReadinessResponse:
    try:
        await database.ping()
    except sqlite3.Error:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unavailable",
            database="down",
            cache="unknown",
        )

    try:
        await cache.ping()
    except (RedisError, OSError):
        return ReadinessResponse(status="degraded", database="up", cache="down")

    return ReadinessResponse(status="ok", database="up", cache="up")
