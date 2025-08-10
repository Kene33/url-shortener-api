import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from src.app.db.sql.crud import SQLClient

TEST_LINKS = [
    ("https://google.com", "goog1"),
    ("https://github.com", "ghub2"),
    ("https://github.com/Kene33", "ghubK33"),
    ("https://docs.python.org", "pyth4"),
    ("https://example.com", "exmp5"),
    ("https://reddit.com", "redd8"),
    ("https://facebook.com", "face10"),
    ("https://linkedin.com", "link11"),
    ("https://youtube.com", "yout12"),
    ("https://instagram.com", "insta13"),
    ("https://npmjs.com", "npm15"),
    ("https://docker.com", "dock16"),
    ("https://kubernetes.io", "kube17"),
    ("https://cloud.google.com", "gcp20"),
    ("https://apple.com", "appl21"),
    ("https://microsoft.com", "msft22"),
    ("https://mozilla.org", "moz23"),
    ("https://wikipedia.org", "wiki24"),
    ("https://forbes.com", "forb40"),
]

async def seed():
    sql_client = SQLClient("src/app/db/sql/links_test.db")
    await sql_client.create_database()
    for url, shortcode in TEST_LINKS:
        #shortcode = await generate_code(4, 8)
        await sql_client.add_link(url, shortcode)
    print("Test data inserted.")

if __name__ == "__main__":
    asyncio.run(seed())