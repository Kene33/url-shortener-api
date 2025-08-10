import aiosqlite
from datetime import datetime

class SQLClient:
    def __init__(self) -> None:
        self.DATABASE = "src/app/db/sql/links.db"

    
    async def create_database(self) -> None:
        async with aiosqlite.connect(self.DATABASE) as db:
            create_table_query = '''
            CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            shortcode TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessCount INTEGER DEFAULT 0,
            UNIQUE(shortcode)
            );
            '''

            await db.execute(create_table_query)
            await db.commit()

    async def add_link(self, url: str, shortcode: str) -> dict:
        async with aiosqlite.connect(self.DATABASE) as db:
            try:
                await db.execute("""
                INSERT INTO links (url, shortcode)
                VALUES (?, ?)
                """, (url, shortcode))
                await db.commit()
                return {"ok": True}
            except aiosqlite.Error as e:
                print(f"Error adding link: {e}")
                return {"ok": False, "error": str(e)}

    async def get_link(self, shortcode: str) -> dict:
        async with aiosqlite.connect(self.DATABASE) as db:
            try:
                cursor = await db.execute("""
                SELECT url FROM links WHERE shortcode = ?
                """, (shortcode,))
                row = await cursor.fetchone()
                if row:
                    return {"ok": True, "url": row[0]}
                else:
                    return {"ok": False, "error": f"Link {shortcode} not found"}
            except aiosqlite.Error as e:
                print(f"Error with getting link: {e}")
                return {"ok": False, "error": str(e)}

    async def delete_link(self, shortcode: str) -> dict:
        async with aiosqlite.connect(self.DATABASE) as db:
            try:
                cursor = await db.execute("""
                DELETE FROM links WHERE shortcode = ?
                """, (shortcode,))
                await db.commit()

                if cursor.rowcount > 0:
                    return {"ok": True, "message": f"Link {shortcode} deleted."}
                else:
                    return {"ok": False, "message": f"Link {shortcode} not found."}
            except aiosqlite.Error as e:
                print(f"Error deleting link: {e}")
                return {"ok": False, "error": str(e)}
            
    async def increment_access_count(self, shortcode: str) -> dict:
        updatedAt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.DATABASE) as db:
            try:
                cursor = await db.execute("""
                UPDATE links SET accessCount = accessCount + 1 WHERE shortcode = ?
                """, (shortcode,))
                await db.commit()

                if cursor.rowcount > 0:
                    return {"ok": True, "message": f"accessCount for {shortcode} incremented."}
                else:
                    return {"ok": False, "message": f"Link {shortcode} not found."}
            except aiosqlite.Error as e:
                print(f"Error incrementing access count: {e}")
                return {"ok": False, "error": str(e)}
            
    async def get_link_stats(self, shortcode: str) -> dict:
        async with aiosqlite.connect(self.DATABASE) as db:
            try:
                cursor = await db.execute("""
                SELECT id, url, shortcode, createdAt, updatedAt, accessCount FROM links WHERE shortcode = ?
                """, (shortcode,))
                row = await cursor.fetchone()

                if row:
                    return {"ok": True, "id": row[0], "url": row[1], "shortcode": row[2], "createdAt": row[3], "updatedAt": row[4], "accessCount": row[5]}
                else:
                    return {"ok": False, "error": f"Link {shortcode} not found"}
            except aiosqlite.Error as e:
                print(f"Error with getting link stats: {e}")
                return {"ok": False, "error": str(e)}