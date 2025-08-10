import aiosqlite


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
            updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
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