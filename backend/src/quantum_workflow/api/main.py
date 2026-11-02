# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""FastAPI application factory module.

Exposes `create_app` and `app_factory` entry points that build and
configure a FastAPI instance, including CORS middleware and route mounting.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quantum_workflow.api.deps import build_pipeline_from_settings
from quantum_workflow.api.routes import make_router
from quantum_workflow.config import Settings


def create_app(pipeline=None, trace_store=None) -> FastAPI:
    """Create and return a configured FastAPI application instance.

    If pipeline / trace_store are not provided, both are built from a
    default Settings instance.

    Args:
        pipeline: A pre-built pipeline; tests may inject a mock.
        trace_store: A pre-built TraceStore; tests may inject a mock.

    Returns:
        A FastAPI instance with CORS middleware and all routes mounted.
    """
    settings = Settings()
    if pipeline is None or trace_store is None:
        pipeline, trace_store = build_pipeline_from_settings(settings)

    app = FastAPI(title="Quantum Workflow Platform", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in v1.1 / production
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(make_router(pipeline, trace_store))
    return app


def app_factory() -> FastAPI:
    """uvicorn factory entry: uvicorn quantum_workflow.api.main:app_factory --factory"""
    return create_app()
