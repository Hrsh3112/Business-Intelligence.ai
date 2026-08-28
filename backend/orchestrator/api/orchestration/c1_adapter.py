"""C1 (ml_engine) Adapter seam.

Translates between C2's Pydantic model universe (api.models.shared)
and ml_engine's Pydantic model universe (ml_engine.models.*).
"""

import logging
from typing import Any, Optional

from api.models.shared import (
    AnomalyReport as C2AnomalyReport,
    CompanyInput as C2CompanyInput,
    RefusalReason as C2RefusalReason,
)

logger = logging.getLogger(__name__)


class C1AdapterError(Exception):
    """Base exception for C1 adapter errors."""


class C1InputAdapterError(C1AdapterError):
    """Raised when C2 CompanyInput cannot be adapted for ml_engine."""


class C1OutputAdapterError(C1AdapterError):
    """Raised when ml_engine output cannot be adapted into C2 AnomalyReport."""


_REFUSAL_REASON_MAP = {
    "insufficient_data": C2RefusalReason.INSUFFICIENT_PERIODS.value,
    "low_confidence": C2RefusalReason.LOW_DATA_CONFIDENCE.value,
    "contradictory_evidence": C2RefusalReason.CONTRADICTORY_EVIDENCE.value,
    "no_metrics_submitted": C2RefusalReason.NO_METRICS_SUBMITTED.value,
    "low_data_confidence": C2RefusalReason.LOW_DATA_CONFIDENCE.value,
    "insufficient_periods": C2RefusalReason.INSUFFICIENT_PERIODS.value,
}


def adapt_company_input_for_c1(c2_input: Any) -> Any:
    """Adapt C2 CompanyInput into an ml_engine CompanyInput instance.

    If the input is already an ml_engine CompanyInput or dict-compatible object,
    validates and returns it. If ml_engine is not importable, passes through.
    """
    if not isinstance(c2_input, C2CompanyInput):
        # Already an ml_engine object or mock object
        return c2_input

    if not c2_input.metrics:
        raise C1InputAdapterError("CompanyInput must contain at least one metric to send to ml_engine")

    try:
        from ml_engine.models.input_schema import CompanyInput as MLCompanyInput
    except ImportError:
        logger.debug("ml_engine not importable; passing C2 CompanyInput through as-is")
        return c2_input

    try:
        dumped = c2_input.model_dump(mode="json", by_alias=True)
        return MLCompanyInput.model_validate(dumped)
    except Exception as exc:
        logger.exception("Failed to adapt CompanyInput for ml_engine")
        raise C1InputAdapterError(f"Failed to adapt CompanyInput for ml_engine: {exc}") from exc


def adapt_c1_output(raw: Any, *, original_c2_input: Optional[C2CompanyInput] = None) -> C2AnomalyReport:
    """Adapt ml_engine output into a canonical C2 AnomalyReport instance."""
    if isinstance(raw, C2AnomalyReport):
        return raw

    if hasattr(raw, "model_dump"):
        data = raw.model_dump(mode="json", by_alias=True)
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        raise C1OutputAdapterError(f"ml_engine returned an unrecognised type: {type(raw)!r}")

    # Handle refusal fields and enum translation if refusal is present
    if data.get("refusal"):
        refusal_data = data["refusal"]
        raw_reason = refusal_data.get("reason")
        if raw_reason:
            mapped_reason = _REFUSAL_REASON_MAP.get(str(raw_reason), str(raw_reason))
            if raw_reason == "insufficient_data" and original_c2_input and not original_c2_input.metrics:
                mapped_reason = C2RefusalReason.NO_METRICS_SUBMITTED.value
            refusal_data["reason"] = mapped_reason

        # Map diagnostic_suggestion to suggested_resolution if needed
        if "diagnostic_suggestion" in refusal_data and "suggested_resolution" not in refusal_data:
            refusal_data["suggested_resolution"] = refusal_data["diagnostic_suggestion"]

    try:
        return C2AnomalyReport.model_validate(data)
    except Exception as exc:
        logger.exception("Failed to adapt ml_engine output to C2 AnomalyReport")
        raise C1OutputAdapterError(f"ml_engine output failed schema validation: {exc}") from exc
