import aiosqlite

DATABASE = "src/database/posts.db"

async def create_database() -> None:
    async with aiosqlite.connect(DATABASE) as db:
        create_table_query = f'''
        CREATE TABLE IF NOT EXISTS links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        shortcode TEXT,
        createdAt TEXT NOT NULL,
        updatedAt TEXT NOT NULL,
        )
        '''

        await db.execute(create_table_query)
        await db.commit()
