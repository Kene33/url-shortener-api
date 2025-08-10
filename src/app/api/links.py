from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.utils.generate import generate_code
from app.db.redis.links import RedisClient
from app.db.sql.links_db import SQLClient

router = APIRouter()
redis_client = RedisClient()
sql_client = SQLClient()

@router.post("/api/links/{original_link}", tags=["POST"])
async def create_link(original_link: str) -> dict:
    original_link = original_link.replace('"', '')
    shortcode = await generate_code(4, 8)
    key_exist = await redis_client.get_value_by_key(shortcode)

    while key_exist:
        shortcode = await generate_code(4, 8)

    if not original_link.startswith("http://") and not original_link.startswith("https://"): original_link = "https://" + original_link
    await redis_client.add_shortlink(shortcode, original_link)
    await sql_client.add_link(original_link, shortcode)
    return {"ok": True, "key": shortcode}

@router.get("/{shortcode}", tags=["GET"])
async def get_link(shortcode: str):
    link = await redis_client.get_value_by_key(shortcode)

    if link: return RedirectResponse(url=link, status_code=301)
    return {"error": 404}

@router.delete("/api/links/{shortcode}", tags=["DELETE"])
async def delete_link(shortcode: str):
    deleted_link = await redis_client.delete_link(shortcode)
    if deleted_link == 1: return {"ok": True, "key": shortcode, "message": f"Link {shortcode} deleted."}

    return {"ok": False, "key": shortcode, "message": f"Link {shortcode} not found."}

# later
@router.get("/api/links/{shortcode}/stats", tags=["GET"])
async def get_link_stats(shortcode: int):
    pass