import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv("services/api/.env.local")

import uvicorn
from services.api.kiara_api.main import create_app

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app = create_app()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        loop="asyncio",
    )
