"""Stage 1 — cost estimation. The rules under test are honesty rules: this
number reaches the user, so every branch that cannot stand behind a figure
must return None rather than a plausible-looking zero."""

import asyncio

import pytest

from api.config.pricing import estimate_cost, load_pricing, models
from api.config.settings import settings
from api.orchestration.pipeline import run_pipeline
from api.tests.fixtures.builders import FIXTURE_BUILDERS


@pytest.fixture(autouse=True)
def fast_mocks(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_C1_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C3_SLEEP_S", 0.0)
    monkeypatch.setattr(settings, "MOCK_C3_FAIL_LLM", False)


class TestPricingConfig:
    def test_pricing_file_loads_and_has_the_mock_model(self):
        assert "models" in load_pricing()
        # The mock is what the demo runs on; an unpriced mock means the
        # telemetry chip shows nothing in every local demo.
        assert "mock-llm-v1" in models()

    def test_every_configured_model_has_a_basis_string(self):
        # A cost with no stated basis is indefensible when a judge asks.
        for name, entry in models().items():
            assert entry.get("basis"), f"{name} has a rate but no basis"


class TestEstimateCost:
    def test_known_model_produces_a_figure_and_its_basis(self):
        estimate = estimate_cost("mock-llm-v1", 512)
        assert estimate.estimated_usd is not None
        assert estimate.estimated_usd > 0
        assert "512" in estimate.basis

    def test_arithmetic_is_tokens_over_a_million_times_rate(self):
        rate = models()["mock-llm-v1"]["blended_usd_per_1m"]
        estimate = estimate_cost("mock-llm-v1", 1_000_000)
        assert estimate.estimated_usd == pytest.approx(rate)

    def test_unpriced_model_yields_no_figure_and_says_why(self):
        estimate = estimate_cost("some-model-we-never-configured", 5000)
        assert estimate.estimated_usd is None  # never a guess
        assert "no published rate" in estimate.basis
        assert estimate.tokens_used == 5000  # what we DO know is still reported

    def test_missing_token_count_yields_no_figure(self):
        assert estimate_cost("mock-llm-v1", None).estimated_usd is None

    def test_no_llm_call_yields_no_figure_never_zero(self):
        estimate = estimate_cost(None, None)
        assert estimate.estimated_usd is None
        assert estimate.estimated_usd != 0  # the distinction that matters

    def test_never_raises_on_any_input(self):
        for model, tokens in [(None, 0), ("", 10), ("mock-llm-v1", 0), ("x", None)]:
            estimate_cost(model, tokens)  # must not raise


class TestCostOnTheResponse:
    def test_complete_run_carries_a_cost_estimate(self, monkeypatch):
        monkeypatch.setattr(settings, "MOCK_SCENARIO", "critical")
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        response = asyncio.run(run_pipeline(company_input))
        assert response.cost is not None
        assert response.cost.estimated_usd is not None
        assert response.timings.total_ms >= 0

    def test_refusal_states_positively_that_nothing_was_spent(self, monkeypatch):
        monkeypatch.setattr(settings, "MOCK_SCENARIO", "refusal")
        company_input, _ = FIXTURE_BUILDERS["refusal"]()
        response = asyncio.run(run_pipeline(company_input))
        assert response.status == "refused"
        assert response.cost is not None  # populated, not omitted
        assert response.cost.estimated_usd is None
        assert response.timings.c3_ms is None  # C3 never called

    def test_degraded_llm_failure_claims_no_cost(self, monkeypatch):
        monkeypatch.setattr(settings, "MOCK_SCENARIO", "critical")
        monkeypatch.setattr(settings, "MOCK_C3_FAIL_LLM", True)
        company_input, _ = FIXTURE_BUILDERS["critical"]()
        response = asyncio.run(run_pipeline(company_input))
        assert response.result.metadata.degraded is True
        assert response.cost.estimated_usd is None  # no tokens -> no claim
