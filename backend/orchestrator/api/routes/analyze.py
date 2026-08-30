"""POST /analyze (Phase1-Plan T1.5) and POST /analyze/upload (Phase2-Plan T2.7).

Architectural boundary, do not breach: run_pipeline() takes a CompanyInput and
nothing else. POST /analyze stays exactly as it is — that's what keeps
Phase 1's 77 tests green and keeps the parser swappable. /analyze/upload only
parses, then calls the same unchanged run_pipeline().
"""

import json
import os
import uuid
from typing import Optional
from collections import defaultdict

from pydantic import ValidationError
from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.config.auth import resolve_persona
from api.models.internal import ApiResponse, ErrorCode, FormMetadata, ParseWarning, ParseWarningCode
from api.models.response_filter import redact_for_persona
from api.models.shared import CompanyInput, DataPoint, EnrichedReport, Granularity, Persona
from api.orchestration.pipeline import run_pipeline
from api.parsing.builder import build_company_input
from api.parsing.ingest import IngestError, ingest_csv
from api.parsing.lineage import build_source_manifest

router = APIRouter()


def downsample_daily_to_monthly(daily_points: list[dict]) -> list[dict]:
    """Reconcile daily-grain time series points into monthly averages."""
    buckets = defaultdict(list)
    for p in daily_points:
        month_key = str(p["period"])[:7]  # "YYYY-MM"
        buckets[month_key].append(float(p["value"]))
    return [{"period": k, "value": round(sum(v) / len(v), 2)} for k, v in sorted(buckets.items())]


@router.post("/analyze", response_model=ApiResponse)
async def analyze(
    company_input: CompanyInput,
    persona: str = Depends(resolve_persona),
) -> ApiResponse:
    company_input.persona = Persona(persona)

    reconciled_warnings: list[ParseWarning] = []
    downsampled_metrics: list[str] = []
    for metric in company_input.metrics:
        if getattr(metric, "grain", None) == "daily" or any(len(p.period) > 7 for p in metric.values):
            raw_pts = [{"period": p.period, "value": p.value} for p in metric.values]
            downsampled = downsample_daily_to_monthly(raw_pts)
            metric.values = [DataPoint(period=dp["period"], value=dp["value"]) for dp in downsampled]
            metric.grain = "monthly"
            metric.granularity = Granularity.MONTHLY
            src = getattr(metric, "source_system", None) or metric.metric_id
            downsampled_metrics.append(f"{src} ({metric.metric_id})" if getattr(metric, "source_system", None) else metric.metric_id)

    if downsampled_metrics:
        src_summary = ", ".join(downsampled_metrics)
        reconciled_warnings.append(
            ParseWarning(
                code=ParseWarningCode.MIXED_GRANULARITY,
                message=f"Daily series for {src_summary} was downsampled to monthly grain (values averaged) to align with monthly data before analysis.",
            )
        )

    response = await run_pipeline(company_input)
    manifest = build_source_manifest(company_input)
    response = response.model_copy(
        update={
            "source_manifest": manifest,
            "persona": Persona(persona),
            "warnings": reconciled_warnings + response.warnings,
        }
    )

    if response.result:
        dumped = response.result.model_dump(mode="json", by_alias=True)
        redacted = redact_for_persona(dumped, persona)
        response = response.model_copy(update={"result": EnrichedReport.model_validate(redacted)})

    return response


def _failed_before_pipeline(message: str) -> ApiResponse:
    return ApiResponse(
        job_id=str(uuid.uuid4()),
        status="failed",
        error=ErrorCode.VALIDATION_ERROR,
        warnings=[ParseWarning(code=ParseWarningCode.SCHEMA_VALIDATION_ERROR, message=message)],
    )


@router.post("/analyze/upload", response_model=ApiResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    mapping_overrides: Optional[str] = Form(None),
    persona: str = Depends(resolve_persona),
) -> ApiResponse:
    try:
        form_metadata = FormMetadata.model_validate_json(metadata)
        form_metadata.persona = Persona(persona)
    except ValidationError as exc:
        return _failed_before_pipeline(f"Invalid company metadata: {exc}")

    overrides: dict[str, str] = {}
    if mapping_overrides:
        try:
            overrides = json.loads(mapping_overrides)
        except json.JSONDecodeError as exc:
            return _failed_before_pipeline(f"mapping_overrides was not valid JSON: {exc}")

    file_bytes = await file.read()
    try:
        raw_table = ingest_csv(file_bytes, file.filename or "upload.csv")
    except IngestError as exc:
        return _failed_before_pipeline(str(exc))

    result = build_company_input(raw_table, form_metadata, overrides)

    def _blocked(error: ErrorCode) -> ApiResponse:
        return ApiResponse(
            job_id=str(uuid.uuid4()),
            status="failed",
            error=error,
            warnings=result.warnings
            + [ParseWarning(code=ParseWarningCode.SCHEMA_VALIDATION_ERROR, message=e) for e in result.blocking_errors],
        )

    if result.company_input is None or not result.company_input.metrics:
        return _blocked(ErrorCode.NO_USABLE_METRICS)

    if result.blocking_errors:
        return _blocked(ErrorCode.VALIDATION_ERROR)

    # Check for daily downsampling if needed
    reconciled_warnings: list[ParseWarning] = []
    downsampled_metrics: list[str] = []
    for metric in result.company_input.metrics:
        if getattr(metric, "grain", None) == "daily" or any(len(p.period) > 7 for p in metric.values):
            raw_pts = [{"period": p.period, "value": p.value} for p in metric.values]
            downsampled = downsample_daily_to_monthly(raw_pts)
            metric.values = [DataPoint(period=dp["period"], value=dp["value"]) for dp in downsampled]
            metric.grain = "monthly"
            metric.granularity = Granularity.MONTHLY
            src = getattr(metric, "source_system", None) or (form_metadata.metric_sources or {}).get(metric.metric_id) or form_metadata.source_system or metric.metric_id
            downsampled_metrics.append(f"{src} ({metric.metric_id})" if src != metric.metric_id else metric.metric_id)

    if downsampled_metrics:
        src_summary = ", ".join(downsampled_metrics)
        reconciled_warnings.append(
            ParseWarning(
                code=ParseWarningCode.MIXED_GRANULARITY,
                message=f"Daily series for {src_summary} was downsampled to monthly grain (values averaged) to align with monthly data before analysis.",
            )
        )

    response = await run_pipeline(result.company_input)
    response = response.model_copy(
        update={
            "warnings": result.warnings + reconciled_warnings + response.warnings,
            "source_manifest": build_source_manifest(
                result.company_input, form_metadata, upload_filename=file.filename
            ),
            "persona": Persona(persona),
        }
    )

    if response.result:
        dumped = response.result.model_dump(mode="json", by_alias=True)
        redacted = redact_for_persona(dumped, persona)
        response = response.model_copy(update={"result": EnrichedReport.model_validate(redacted)})

    return response
