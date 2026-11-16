"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.session import engine
from app.exceptions import register_exception_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("Starting %s (env=%s, debug=%s)", settings.APP_NAME, settings.APP_ENV, settings.DEBUG)

    # Startup check: make sure the database is reachable before serving traffic.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
    except Exception:
        logger.exception("Database connection check failed at startup")

    yield

    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Rate limiting (slowapi)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    async def rate_limit_handler(request, exc: RateLimitExceeded):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )

    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # CORS. Note: wildcard origins ("*") are incompatible with credentialed
    # requests per the CORS spec, so credentials are only allowed once
    # CORS_ORIGINS is locked down to an explicit origin list.
    cors_origins = settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers (must be after CORS/rate-limit middleware setup)
    register_exception_handlers(app)

    # Routers
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
