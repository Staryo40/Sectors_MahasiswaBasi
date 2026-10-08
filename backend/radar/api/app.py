"""FastAPI service for the existing snapshot contracts.

The service reads exports only. Refreshing, scoring and dry-run delivery remain
explicit CLI operations; HTTP requests never call Sectors or send messages.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jsonschema.exceptions import ValidationError

from radar import config
from radar.export.validation import validate

Source = Literal["out", "fixtures", "sample"]
Horizon = Literal["daily", "weekly"]


def create_app(
    source_directories: dict[str, Path] | None = None,
    frontend_directory: Path | None = None,
) -> FastAPI:
    """Build a service with injectable directories for offline tests."""
    directories = source_directories if source_directories is not None else {
        "out": config.OUT_DIR,
        "fixtures": config.FIXTURES_DIR / "out",
        "sample": config.DATA_DIR / "demo",
    }
    application = FastAPI(
        title="Flow Radar API",
        version="0.1.0",
        description="Read-only, end-of-day market snapshots. " + config.DISCLAIMER,
    )
    origins = config.frontend_origins()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["*"],
            max_age=600,
        )

    def snapshot(source: Source, name: str, schema: str) -> JSONResponse:
        directory = directories.get(source)
        if directory is None:
            raise HTTPException(404, "Snapshot source is not available.")
        directory = directory.resolve()
        target = (directory / name).resolve()
        if not target.is_relative_to(directory):
            raise HTTPException(404, "Snapshot is not available.")
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(404, "Snapshot is not available. Export data first.") from None
        except (OSError, ValueError):
            raise HTTPException(503, "Snapshot could not be read. Re-export data.") from None
        try:
            validate(schema, data)
        except ValidationError:
            raise HTTPException(503, "Snapshot does not match its contract. Re-export data.") from None
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @application.get("/api/health", tags=["Service"])
    def health() -> dict:
        return {
            "status": "ok",
            "sources": [name for name, directory in directories.items()
                        if (directory / "meta.json").is_file()],
        }

    @application.get("/api/snapshots/{source}/meta", tags=["Snapshots"])
    def metadata(source: Source) -> JSONResponse:
        return snapshot(source, "meta.json", "meta")

    @application.get("/api/snapshots/{source}/daily", tags=["Rankings"])
    def daily(source: Source) -> JSONResponse:
        return snapshot(source, "daily.json", "daily")

    @application.get("/api/snapshots/{source}/investor", tags=["Rankings"])
    def investor(source: Source) -> JSONResponse:
        return snapshot(source, "investor.json", "investor")

    @application.get("/api/snapshots/{source}/briefs/{horizon}", tags=["Briefs"])
    def brief(source: Source, horizon: Horizon) -> JSONResponse:
        return snapshot(source, f"brief_{horizon}.json", f"brief_{horizon}")

    @application.get("/api/snapshots/{source}/stocks/{symbol}", tags=["Research"])
    def stock(source: Source, symbol: str) -> JSONResponse:
        normalized = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{1,12}", normalized):
            raise HTTPException(422, "Use an IDX stock symbol without the .JK suffix.")
        return snapshot(source, f"stocks/{normalized}.json", "stock")

    # Hash navigation needs only the index document. API routes stay separate
    # from static assets so a missing API resource cannot become an HTML response.
    frontend = frontend_directory if frontend_directory is not None else config.ROOT / "frontend" / "dist"
    if (frontend / "index.html").is_file():
        if (frontend / "assets").is_dir():
            application.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @application.get("/", include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(frontend / "index.html")

        @application.get("/mark.svg", include_in_schema=False)
        def frontend_icon() -> FileResponse:
            return FileResponse(frontend / "mark.svg")

    return application


app = create_app()
