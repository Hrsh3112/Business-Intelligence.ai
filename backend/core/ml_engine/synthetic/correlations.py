"""Cross-metric correlation handling and consistency validation."""

from typing import Dict, List, Optional
from ..config.schema import SectorConfig


class CorrelationEngine:
    """Manages cross-metric correlation matrices and relationship lookups."""

    def __init__(self, sector_config: SectorConfig):
        self.sector_config = sector_config
        self.correlation_matrix: Dict[str, Dict[str, float]] = sector_config.correlation_matrix

    def get_correlation(self, metric_a: str, metric_b: str) -> float:
        """Get correlation coefficient between two metrics (-1.0 to 1.0)."""
        if metric_a == metric_b:
            return 1.0
        if metric_a in self.correlation_matrix and metric_b in self.correlation_matrix[metric_a]:
            return self.correlation_matrix[metric_a][metric_b]
        if metric_b in self.correlation_matrix and metric_a in self.correlation_matrix[metric_b]:
            return self.correlation_matrix[metric_b][metric_a]
        return 0.0

    def get_correlated_metrics(self, metric_id: str, threshold: float = 0.5) -> List[str]:
        """Return all metrics correlated with given metric above the absolute threshold."""
        correlated = []
        if metric_id in self.correlation_matrix:
            for other_id, coeff in self.correlation_matrix[metric_id].items():
                if abs(coeff) >= threshold:
                    correlated.append(other_id)
        # Also check reverse mapping
        for m_id, row in self.correlation_matrix.items():
            if m_id != metric_id and metric_id in row:
                if abs(row[metric_id]) >= threshold and m_id not in correlated:
                    correlated.append(m_id)
        return correlated
