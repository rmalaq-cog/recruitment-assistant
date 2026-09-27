from __future__ import annotations

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


app = FastAPI(title="Recruitment Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173", "null"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


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
    correlation_id = request.headers.get("x-correlation-id", uuid4().hex)
    error = ApiError(
        code=f"http_{exc.status_code}",
        message=str(exc.detail),
        correlation_id=correlation_id,
        retryable=exc.status_code >= 500,
    )
    return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode="json"))


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