from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from redis import asyncio as aioredis
import logging


logging.basicConfig(level=logging.DEBUG)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    redis = aioredis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis), prefix="stremio-cache")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def register_tv():
    from .parsers.tv.api import router
    app.include_router(router)


def register_eneyida():
    from .parsers.eneyida.api import router
    app.include_router(router)


def register_uakino():
    from .parsers.uakino.api import router
    app.include_router(router)


register_tv()
register_eneyida()
register_uakino()
