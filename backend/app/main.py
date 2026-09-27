from __future__ import annotations

import logging
import time
from functools import lru_cache
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import Settings, get_settings
from .crew import RecruitmentCrewFactory
from .models import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    ApiError,
    CriteriaUpdateRequest,
    ExportFormat,
    HealthResponse,
    JobCreateRequest,
    JobRecord,
    ReviewDecisionRequest,
)
from .services import RecruitmentService
from .storage import SQLiteStore


settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Recruitment Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173", "null"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def log_startup() -> None:
    logger.info(
        "application_startup runtime=%s database=%s storage_dir=%s crewai_storage_dir=%s model_configured=%s crewai_tracing=%s",
        settings.aamad_target_runtime,
        settings.database_url,
        settings.storage_dir,
        settings.crewai_storage_dir,
        bool(settings.openai_api_key),
        settings.crewai_tracing,
    )


@app.middleware("http")
async def log_api_requests(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id", uuid4().hex)
    request.state.correlation_id = correlation_id
    start_time = time.perf_counter()
    logger.info("api_request_started method=%s path=%s correlation_id=%s", request.method, request.url.path, correlation_id)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception(
            "api_request_failed method=%s path=%s duration_ms=%s correlation_id=%s",
            request.method,
            request.url.path,
            duration_ms,
            correlation_id,
        )
        raise
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    response.headers["x-correlation-id"] = correlation_id
    logger.info(
        "api_response_completed method=%s path=%s status_code=%s duration_ms=%s correlation_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        correlation_id,
    )
    return response


@lru_cache
def get_store() -> SQLiteStore:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.crewai_storage_dir.mkdir(parents=True, exist_ok=True)
    return SQLiteStore(settings.sqlite_path)


def get_service() -> RecruitmentService:
    return RecruitmentService(get_settings(), get_store())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", request.headers.get("x-correlation-id", uuid4().hex))
    logger.warning(
        "http_exception method=%s path=%s status_code=%s correlation_id=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        correlation_id,
        exc.detail,
    )
    error = ApiError(
        code=f"http_{exc.status_code}",
        message=str(exc.detail),
        correlation_id=correlation_id,
        retryable=exc.status_code >= 500,
    )
    return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", request.headers.get("x-correlation-id", uuid4().hex))
    logger.exception(
        "unhandled_exception method=%s path=%s correlation_id=%s",
        request.method,
        request.url.path,
        correlation_id,
    )
    error = ApiError(code="internal_server_error", message="Internal server error", correlation_id=correlation_id, retryable=True)
    return JSONResponse(status_code=500, content=error.model_dump(mode="json"))


@app.get("/health", response_model=HealthResponse)
def health(settings: Settings = get_settings()) -> HealthResponse:
    crew_errors = RecruitmentCrewFactory(settings).validate_config()
    database_status = "ok" if get_store().database_path.exists() else "initializing"
    return HealthResponse(
        status="ok" if not crew_errors else "degraded",
        runtime=settings.aamad_target_runtime,
        database=database_status,
        model_configured=bool(settings.openai_api_key),
    )


@app.post("/jobs", response_model=JobRecord, status_code=201)
def create_job(request: JobCreateRequest) -> JobRecord:
    return get_service().create_job(request)


@app.put("/jobs/{job_id}/criteria", response_model=JobRecord)
def update_criteria(job_id: str, request: CriteriaUpdateRequest) -> JobRecord:
    job = get_service().update_criteria(job_id, request.criteria)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/runs", response_model=AnalysisRunResponse, status_code=201)
def start_run(request: AnalysisRunRequest) -> AnalysisRunResponse:
    try:
        run = get_service().run_analysis(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not run:
        raise HTTPException(status_code=404, detail="Job not found")
    return run


@app.get("/runs/{run_id}", response_model=AnalysisRunResponse)
def get_run(run_id: str) -> AnalysisRunResponse:
    run = get_service().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/runs/{run_id}/decisions", response_model=AnalysisRunResponse)
def save_decisions(run_id: str, request: ReviewDecisionRequest) -> AnalysisRunResponse:
    run = get_service().save_decisions(run_id, request)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/runs/{run_id}/export", response_model=None)
def export_run(run_id: str, format: ExportFormat = Query(default=ExportFormat.MARKDOWN)):
    export = get_service().export_run(run_id, format)
    if not export:
        raise HTTPException(status_code=404, detail="Run not found")
    if format == ExportFormat.JSON:
        return JSONResponse(content=export.model_dump(mode="json"))
    return PlainTextResponse(content=export.content, media_type="text/markdown")