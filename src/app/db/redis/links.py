import redis.asyncio as redis 

class RedisClient:
    def __init__(self, host: str = "localhost", port: int = 6379, db: str | int = 0): 
        self.pool = redis.ConnectionPool(host=host, port=port, db=db)
        self.client = redis.Redis(connection_pool=self.pool, decode_responses=True)

    async def add_shortlink(self, key: str, value: str) -> str:
        added_link = await self.client.set(key, value)
        return added_link
    
    async def get_value_by_key(self, key: str) -> str | None:
        value = await self.client.get(key)
        value = value.decode('utf-8') if value else None
        return value
    
    async def delete_link(self, key: str) -> int:
        deleted_link = await self.client.delete(key)
        return deleted_link
