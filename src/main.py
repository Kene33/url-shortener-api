import uvicorn
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.db.sql.crud import SQLClient

app = FastAPI(title="API")
app.include_router(api_router)

sql_client = SQLClient()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

async def on_startup():
    await sql_client.create_database()

if __name__ == "__main__":
    asyncio.run(on_startup())
    uvicorn.run("main:app", reload=True, host="127.0.0.1", port=8000)