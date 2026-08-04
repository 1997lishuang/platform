from __future__ import annotations

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - exercised only when api deps are absent
    FastAPI = None  # type: ignore[assignment]
    uvicorn = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from boq_pricing.config import load_settings


def create_app():
    if FastAPI is None:
        raise RuntimeError(
            "API dependencies are not installed. Install with: pip install -e .[api]"
        ) from _IMPORT_ERROR

    from boq_pricing.api.routes import auth, bid_generation, bid_strategy, health, item_mappings, market_quotes, model_call_logs, platform_configs, pricing, rules, users

    settings = load_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(bid_strategy.router, prefix="/api")
    app.include_router(bid_generation.router, prefix="/api")
    app.include_router(rules.router, prefix="/api")
    app.include_router(item_mappings.router, prefix="/api")
    app.include_router(market_quotes.router, prefix="/api")
    app.include_router(model_call_logs.router, prefix="/api")
    app.include_router(platform_configs.router, prefix="/api")
    app.include_router(pricing.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    return app


app = create_app() if FastAPI is not None else None


def run() -> None:
    if uvicorn is None:
        raise RuntimeError("API dependencies are not installed. Install with: pip install -e .[api]")
    uvicorn.run("boq_pricing.api.main:create_app", host="127.0.0.1", port=8000, factory=True)


if __name__ == "__main__":
    run()
