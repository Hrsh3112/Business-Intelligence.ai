"""C2-internal models — master plan §5.5. Ours alone; no external component
depends on these, so they can change freely without cross-team coordination.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from api.models.shared import CompanyInput, EnrichedReport, Persona, RevenueBand, SectorId


class ParseWarningCode(str, Enum):
    """Warning-code vocabulary, defined now so Phase 2 (parsing) and Phase 3
    (frontend) agree without a second conversation (Phase0-Plan T0.3)."""

    UNKNOWN_METRIC = "UNKNOWN_METRIC"  # column couldn't resolve to a canonical metric_id
    UNIT_SCALE_SUSPECT = "UNIT_SCALE_SUSPECT"  # distributional fraction/percent check tripped
    OUT_OF_RANGE = "OUT_OF_RANGE"  # value outside valid_min/valid_max
    SHORT_SERIES = "SHORT_SERIES"  # below the trend floor but above the hard block
    INTERPOLATED_POINTS = "INTERPOLATED_POINTS"  # C2 gap-filled one or more periods
    SECTOR_MISMATCH = "SECTOR_MISMATCH"  # metric exists but not for the submitted sector
    AMBIGUOUS_MAPPING = "AMBIGUOUS_MAPPING"  # multiple aliases matched; user confirmation needed
    # Generic CompanyInput body-shape failure (Phase1-Plan T1.5) — distinct
    # from the domain-specific codes above, which all come from Phase 2's
    # CSV/form parsing pipeline, not from raw JSON schema validation.
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"

    # --- Phase 2 additions (Phase2-Plan T2.1/T2.2/T2.4) ---
    DATE_TRUNCATED = "DATE_TRUNCATED"  # a full date was truncated to its period (e.g. 2026-01-15 -> 2026-01)
    TWO_DIGIT_YEAR_FUTURE = "TWO_DIGIT_YEAR_FUTURE"  # "assume 2000s" landed >1 year in the future
    AMBIGUOUS_NUMBER_FORMAT = "AMBIGUOUS_NUMBER_FORMAT"  # column mixes American/European separators
    MIXED_GRANULARITY = "MIXED_GRANULARITY"  # one metric's periods don't share a single granularity
    AMBIGUOUS_SHAPE = "AMBIGUOUS_SHAPE"  # neither wide nor transposed shape detection heuristic won
    SERIES_TRIMMED = "SERIES_TRIMMED"  # a 4+ period gap caused a trim to the most recent contiguous block
    INTERPOLATION_HEAVY = "INTERPOLATION_HEAVY"  # interpolated_ratio > 0.3 even though no single gap trimmed
    CONSTANT_SERIES = "CONSTANT_SERIES"  # every value in the series is identical
    SPARSE_SERIES = "SPARSE_SERIES"  # more than half the values are null
    DUPLICATE_PERIOD = "DUPLICATE_PERIOD"  # same period appeared twice for one metric; last one kept
    REFUSAL_LIKELY = "REFUSAL_LIKELY"  # every surviving metric is below its trend floor — C1 will refuse


class MappingProposal(BaseModel):
    """One resolved column from an uploaded file."""

    source_label: str  # header as written by the user
    resolved_metric_id: Optional[str] = None  # None if unresolvable
    match_type: Literal["exact", "alias", "normalized", "unresolved"]
    unit_warning: Optional[str] = None  # e.g. fraction/percent suspicion
    # Populated only for an ambiguous match (Phase2-Plan T2.3: "all candidates
    # returned, user decides in /validate"). Empty otherwise.
    candidates: list[str] = []
    sample_values: list[float] = []


class ParseWarning(BaseModel):
    code: ParseWarningCode
    metric_id: Optional[str] = None
    message: str


class ParseResult(BaseModel):
    company_input: Optional[CompanyInput] = None
    proposals: list[MappingProposal] = []
    warnings: list[ParseWarning] = []
    blocking_errors: list[str] = []


class RawCell(BaseModel):
    """One (period, source_label, raw_value) triple — the long-form
    representation both CSV shapes (wide/transposed) and the manual form
    converge into, so everything downstream works on one structure
    (Phase2-Plan §2, T2.2)."""

    period: str  # not yet parsed/normalized — parsing/primitives.py does that later
    source_label: str  # header/label exactly as the user wrote it
    raw_value: str  # not yet parsed — parsing/primitives.py does that later


class RawTable(BaseModel):
    cells: list[RawCell]
    detected_shape: Literal["wide", "transposed", "form"]
    warnings: list[ParseWarning] = []


class InferredMetadata(BaseModel):
    granularity: Optional[str] = None
    periods: int = 0
    shape: Optional[Literal["wide", "transposed", "form"]] = None
    revenue_band: Optional[str] = None


class ValidateResponse(BaseModel):
    """POST /validate's response shape (Phase2-Plan T2.6). Distinct from
    ParseResult — it never carries a company_input (validate stops before
    building one) and adds `inferred`/`ready`, which ParseResult has no use
    for elsewhere."""

    proposals: list[MappingProposal] = []
    warnings: list[ParseWarning] = []
    blocking_errors: list[str] = []
    inferred: InferredMetadata = InferredMetadata()
    ready: bool = False


class FormMetadata(BaseModel):
    """Company-level metadata accompanying a file upload or manual entry
    (Phase2-Plan T2.5/T2.6). Distinct from CompanyMetadata (models/shared.py):
    this is what the USER supplies; CompanyMetadata is what C2 derives from it
    (e.g. revenue_band overridden from annual_revenue when present)."""

    company_name: str
    sector_id: SectorId
    employee_count: int
    region: str
    founded_year: Optional[int] = None
    annual_revenue: Optional[float] = None
    revenue_band: Optional[RevenueBand] = None  # trusted only if annual_revenue is absent
    raw_text_context: Optional[str] = None
    # --- Provenance (Stage 4). Both optional: a submission that declares
    # nothing still gets a manifest, just with the source left unknown rather
    # than guessed. ---
    persona: Persona = Persona.EXECUTIVE
    source_system: Optional[str] = Field(default=None, max_length=120)
    # Per-metric override, e.g. {"churn_rate": "CRM export (daily)"}. This is
    # how one upload can honestly carry two systems at two cadences without
    # pretending we hold a live connector to either.
    metric_sources: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def _require_revenue_signal(self) -> "FormMetadata":
        if self.annual_revenue is None and self.revenue_band is None:
            raise ValueError("Either annual_revenue or revenue_band must be provided.")
        return self


class ErrorCode(str, Enum):
    """Error-code vocabulary for ApiResponse.error (Phase1-Plan T1.5). C2-owned
    and always self-assigned — never parsed from an external component's
    output — so unlike EnrichmentMetadata.degraded_reason this is safe to
    type as an enum rather than a bare string.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    # Every column the user submitted was either unrecognised or excluded by
    # the validation layer, so nothing usable remains to analyse. Distinct
    # from VALIDATION_ERROR (the request itself was malformed) and from a C1
    # refusal (C1 saw the data and declined): here C1 is never called, because
    # sending metrics: [] just produces a misleading "no metrics submitted"
    # when the user did submit data — C2 discarded it. The per-column reasons
    # travel alongside this code in ApiResponse.warnings.
    NO_USABLE_METRICS = "NO_USABLE_METRICS"
    C1_TIMEOUT = "C1_TIMEOUT"
    C1_FAILED = "C1_FAILED"
    # Reserved, not currently triggered: get_c1()/get_c3() degrade a missing
    # real module to the mock with a warning log rather than raising, so
    # nothing in Phase 1 surfaces this to the client yet.
    C1_UNAVAILABLE = "C1_UNAVAILABLE"
    C3_TIMEOUT = "C3_TIMEOUT"
    C3_FAILED = "C3_FAILED"
    C3_CONTRACT_VIOLATION = "C3_CONTRACT_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class Timings(BaseModel):
    """Wall-clock time C2's orchestrator spent per stage — distinct from each
    stage's own self-reported processing_time_ms (ReportMetadata /
    EnrichmentMetadata), which measures only that component's internal
    computation, not thread-pool or dispatch overhead."""

    c1_ms: Optional[int] = None
    c3_ms: Optional[int] = None  # null when C3 was never called (refusal short-circuit)
    total_ms: int


class MetricSource(BaseModel):
    """Provenance for one submitted metric (Stage 4 — critique P0 #2 / Req 2).

    WHY THIS LIVES ON C2's ENVELOPE: the frontend only ever receives the
    EnrichedReport, so today it can see nothing about the CompanyInput that
    produced it. C2 holds that input. Deriving the manifest here means the
    lineage, grain and freshness reach the UI without a single change to C1's
    or C3's schemas.

    WHAT IS REAL vs DECLARED — the distinction matters if a judge asks:
      * grain, as_of_period, period range, point counts, interpolated counts
        and confidence are all COMPUTED from the data actually submitted.
      * source_system is DECLARED by the user (or inferred from the uploaded
        filename). `source_basis` records which, so the label is never passed
        off as something the system verified.
    """

    metric_id: str
    display_name: Optional[str] = None
    source_system: Optional[str] = None
    source_basis: Literal["declared", "upload_filename", "unknown"] = "unknown"
    grain: str  # per-metric granularity — authoritative over the envelope's
    as_of_period: Optional[str] = None  # latest period actually present
    first_period: Optional[str] = None
    points: int = 0
    interpolated_points: int = 0  # how much of the series C2 gap-filled
    confidence: float = 1.0


class FeedbackVerdict(str, Enum):
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"


class FeedbackCorrection(str, Enum):
    """The specific corrections an analyst can make, from the four the critique
    names: "this was noise, suppress it", "more severe than the score
    suggests", and the root-cause correction workflow. Enumerated rather than
    free text so the log is aggregatable later — a pile of prose comments is
    not a feedback signal anyone can act on."""

    WAS_NOISE = "was_noise"
    SEVERITY_UNDERSTATED = "severity_understated"
    SEVERITY_OVERSTATED = "severity_overstated"
    WRONG_ROOT_CAUSE = "wrong_root_cause"


class FeedbackRequest(BaseModel):
    """What a user submits about a report they were just shown.

    Scope honesty: this records a verdict, it does not retrain anything. The
    endpoint appends to a file. Nothing in the pipeline reads it back yet, and
    no claim to the contrary belongs in the UI or the deck — the Living
    Knowledge Base loop is roadmap, and this is its first hop.
    """

    job_id: str
    target: Literal["report", "narrative", "anomaly"] = "report"
    anomaly_id: Optional[str] = None  # required in spirit when target="anomaly"
    verdict: FeedbackVerdict
    correction: Optional[FeedbackCorrection] = None
    # Capped: this is written to disk unauthenticated, so an uncapped field is
    # a free disk-fill. 2000 chars is far more than anyone types in a demo.
    comment: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _anomaly_target_needs_an_id(self) -> "FeedbackRequest":
        if self.target == "anomaly" and not self.anomaly_id:
            raise ValueError("anomaly_id is required when target is 'anomaly'")
        return self


class FeedbackResponse(BaseModel):
    """Deliberately not an ApiResponse: feedback is not a pipeline run, and
    reusing that envelope would imply a job_id/status/result it does not have."""

    recorded: bool
    message: str


class CostEstimate(BaseModel):
    """What the one LLM call cost, as far as we can honestly say.

    C2-owned and on C2's envelope on purpose. The token count and model name
    come from C3's EnrichmentMetadata, but the *price* is ours to derive — and
    we already carry one unsigned addition to a shared model
    (EnrichmentMetadata.degraded_reason, Deviation #1). A second one would be
    worse manners than keeping our own derivation on our own envelope.

    `estimated_usd` is None whenever we cannot stand behind a figure — an
    unpriced model, or no LLM call at all. It is never 0.0 as a stand-in for
    unknown. `basis` records how the figure was reached so it can be defended.
    """

    llm_model: Optional[str] = None
    tokens_used: Optional[int] = None
    estimated_usd: Optional[float] = None  # ESTIMATE, derived — not measured spend
    basis: Optional[str] = None


class ApiResponse(BaseModel):
    """Envelope. Identical shape whether sync or polled — so we can switch
    without touching the frontend."""

    job_id: str
    status: Literal["complete", "running", "failed", "refused"]
    result: Optional[EnrichedReport] = None
    warnings: list[ParseWarning] = []
    error: Optional[ErrorCode] = None
    timings: Optional[Timings] = None
    cost: Optional[CostEstimate] = None
    # Empty when the pipeline never ran (no input to describe), never null-as-
    # unknown — an empty list and a missing field mean different things here.
    source_manifest: list[MetricSource] = []
    # Echoed back so the rendering layer and the static demo snapshots agree on
    # who this report was assembled for. Defaults to EXECUTIVE on POST /analyze,
    # which carries no form metadata to declare one.
    persona: Persona = Persona.EXECUTIVE
