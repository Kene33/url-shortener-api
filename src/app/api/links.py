import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.utils.generate import generate_code
from app.db.redis.links import RedisClient
from app.db.sql.crud import SQLClient



router = APIRouter()
redis_client = RedisClient()
sql_client = SQLClient()

@router.post("/api/links/{original_link}", tags=["POST"])
async def create_link(original_link: str) -> dict:
    original_link = original_link.replace('"', '')
    shortcode = await generate_code(4, 8)
    key_exist = await redis_client.get_value_by_key(shortcode)

    while key_exist["ok"]:
        shortcode = await generate_code(4, 8)
        print(f"Shortcode {shortcode} already exists, generating a new one.")
        key_exist = await redis_client.get_value_by_key(shortcode)

    if not original_link.startswith("http://") and not original_link.startswith("https://"): original_link = "https://" + original_link

    await redis_client.add_shortlink(shortcode, original_link)
    await sql_client.add_link(original_link, shortcode)
    print(f"Adding link {original_link} with shortcode {shortcode} to database.")
    
    return {"ok": True, "key": shortcode}

@router.get("/{shortcode}", tags=["GET"])
async def get_link(shortcode: str):
    link = await redis_client.get_value_by_key(shortcode)
    await sql_client.increment_access_count(shortcode)

    if link: return RedirectResponse(url=link["value"], status_code=301)
    return {"error": 404}

@router.delete("/api/links/{shortcode}", tags=["DELETE"])
async def delete_link(shortcode: str):
    redis_link = await redis_client.delete_link(shortcode)
    sql_link = await sql_client.delete_link(shortcode)
    if redis_link["ok"] and sql_link["ok"]:
        return {"ok": True, "key": shortcode, "message": f"Link {shortcode} deleted."}

    return {"ok": False, "key": shortcode, "message": f"Link {shortcode} not found."}

@router.get("/api/links/{shortcode}/stats", tags=["GET"])
async def get_link_stats(shortcode: str):
    link_stats = await sql_client.get_link_stats(shortcode)
    if link_stats["ok"]:
        return {
            "ok": True,
            "id": link_stats["id"],
            "url": link_stats["url"],
            "shortcode": link_stats["shortcode"],
            "createdAt": link_stats["createdAt"],
            "updatedAt": link_stats["updatedAt"],
            "accessCount": link_stats["accessCount"]
        }
    return {"ok": False, "error": link_stats["error"]}