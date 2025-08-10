import redis.asyncio as redis 
import os

class RedisClient:
    def __init__(self, host = "localhost", port = 6379, db = 0) -> None:

        self.pool = redis.ConnectionPool(host=host, port=port, db=db)
        self.client = redis.Redis(connection_pool=self.pool, decode_responses=True)

    async def add_shortlink(self, key: str, value: str) -> dict:
        added_link = await self.client.set(key, value)
        if added_link:
            return {"ok": True, "key": key, "value": value}
        return {"ok": False, "key": key, "message": f"Link {key} already exists."}
    
    async def get_value_by_key(self, key: str) -> dict:
        value = await self.client.get(key)
        value = value.decode('utf-8') if value else None
        if value:
            return {"ok": True, "key": key, "value": value}
        return {"ok": False, "key": key, "message": f"Link {key} not found."}
    
    async def delete_link(self, key: str) -> dict:
        deleted_link = await self.client.delete(key)
        if deleted_link == 1:
            return {"ok": True, "key": key, "message": f"Link {key} deleted."}
        return {"ok": False, "key": key, "message": f"Link {key} not found."}
