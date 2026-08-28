"""Classification of severity scores into exclusive severity bands."""

from ..config.schema import ThresholdsConfig
from ..models.output_schema import SeverityLabel


class SeverityClassifier:
    """Classifies numerical severity scores (0-100) into exclusive severity bands."""

    def __init__(self, thresholds: ThresholdsConfig):
        self.cutoffs = thresholds.classification_cutoffs
        self.warning_cutoff = self.cutoffs.get("warning", 25.0)
        self.critical_cutoff = self.cutoffs.get("critical", 50.0)
        self.severe_cutoff = self.cutoffs.get("severe", 75.0)

    def classify(self, score: float) -> SeverityLabel:
        """Map score to SeverityLabel.

        Bands:
        - score < 25.0 -> INFO
        - 25.0 <= score < 50.0 -> WARNING
        - 50.0 <= score < 75.0 -> CRITICAL
        - score >= 75.0 -> SEVERE
        """
        if score >= self.severe_cutoff:
            return SeverityLabel.SEVERE
        elif score >= self.critical_cutoff:
            return SeverityLabel.CRITICAL
        elif score >= self.warning_cutoff:
            return SeverityLabel.WARNING
        else:
            return SeverityLabel.INFO
