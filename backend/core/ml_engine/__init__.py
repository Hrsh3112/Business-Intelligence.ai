"""businessintelligence.ai ML & Synthetic Data Engine package.

Primary Entrypoint:
    analyze_company(input_data: CompanyInput) -> AnomalyReport
"""

from .pipeline import analyze_company
from .models.input_schema import (
    CompanyInput,
    CompanyMetadata,
    MetricInput,
    PeriodType,
    ReportingPeriod,
    RevenueBand,
    SectorId,
    TimeSeriesPoint,
)
from .models.output_schema import (
    AnomalyItem,
    AnomalyReport,
    CompanyProfileSummary,
    DeviationDetails,
    DeviationDirection,
    HighlightItem,
    RefusalDetails,
    RefusalReason,
    ReportMetadata,
    SeverityLabel,
    TrendDetails,
    TrendDirection,
    TrendPoint,
)
from .config.loader import (
    get_all_canonical_metrics,
    get_metric_definition,
    list_supported_sectors,
    load_sector_config,
    load_thresholds,
)

__version__ = "0.1.0"

__all__ = [
    "analyze_company",
    "CompanyInput",
    "CompanyMetadata",
    "MetricInput",
    "PeriodType",
    "ReportingPeriod",
    "RevenueBand",
    "SectorId",
    "TimeSeriesPoint",
    "AnomalyItem",
    "AnomalyReport",
    "CompanyProfileSummary",
    "DeviationDetails",
    "DeviationDirection",
    "HighlightItem",
    "RefusalDetails",
    "RefusalReason",
    "ReportMetadata",
    "SeverityLabel",
    "TrendDetails",
    "TrendDirection",
    "TrendPoint",
    "load_sector_config",
    "load_thresholds",
    "list_supported_sectors",
    "get_metric_definition",
    "get_all_canonical_metrics",
]
