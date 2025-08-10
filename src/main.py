import uvicorn
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.db.sql.links_db import SQLClient

app = FastAPI(title="API")
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:4000"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

async def on_startup():
    sql = SQLClient()
    await sql.create_database()

if __name__ == "__main__":
    asyncio.run(on_startup())
    uvicorn.run("main:app", reload=True, host="127.0.0.1", port=4000)