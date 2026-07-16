import sqlite3

from fastapi import APIRouter, Depends, Response, status
from redis.exceptions import RedisError

from app.api.dependencies import get_cache, get_database
from app.db.redis.links import LinkCache
from app.db.sql.crud import SQLClient
from app.schemas.links import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse, operation_id="health_liveness")
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
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
