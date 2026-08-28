"""Configuration loader and manager for ml_engine."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from .schema import MetricDefinition, SectorConfig, ThresholdsConfig


CONFIG_DIR = Path(__file__).resolve().parent
SECTORS_DIR = CONFIG_DIR / "sectors"
THRESHOLDS_PATH = CONFIG_DIR / "thresholds.yaml"


@lru_cache(maxsize=1)
def load_thresholds() -> ThresholdsConfig:
    """Load default thresholds configuration."""
    if not THRESHOLDS_PATH.exists():
        return ThresholdsConfig()
    with open(THRESHOLDS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ThresholdsConfig.model_validate(data)


@lru_cache(maxsize=16)
def load_sector_config(sector_id: str) -> SectorConfig:
    """Load sector configuration by sector ID (e.g. 'TECH_SAAS', 'RETAIL')."""
    normalized_id = sector_id.strip().lower()
    yaml_path = SECTORS_DIR / f"{normalized_id}.yaml"
    if not yaml_path.exists():
        raise ValueError(
            f"Sector configuration for '{sector_id}' not found. Available sectors: {list_supported_sectors()}"
        )
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SectorConfig.model_validate(data)


def list_supported_sectors() -> List[str]:
    """List all supported sector IDs based on available YAML configs."""
    if not SECTORS_DIR.exists():
        return []
    return [p.stem.upper() for p in SECTORS_DIR.glob("*.yaml")]


def get_metric_definition(sector_id: str, metric_id: str) -> Optional[MetricDefinition]:
    """Retrieve specific metric definition within a sector."""
    try:
        sector_cfg = load_sector_config(sector_id)
        for metric in sector_cfg.metrics:
            if metric.metric_id == metric_id:
                return metric
        return None
    except ValueError:
        return None


def get_all_canonical_metrics() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Return dictionary of canonical metrics across sectors with units and bounds."""
    catalog = {}
    for sec_id in list_supported_sectors():
        cfg = load_sector_config(sec_id)
        catalog[sec_id] = {
            m.metric_id: {
                "display_name": m.display_name,
                "category": m.category,
                "unit": m.unit.value,
                "valid_min": m.valid_min,
                "valid_max": m.valid_max,
                "direction": m.direction.value,
            }
            for m in cfg.metrics
        }
    return catalog
