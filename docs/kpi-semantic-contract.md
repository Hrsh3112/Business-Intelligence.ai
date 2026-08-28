# KPI Semantic Contract & Metric Dictionary

This document is the machine-readable and human-readable source of truth for all KPI definitions, calculation methods, valid ranges, optimization directions, and sector baselines used by the system.

---

## Sector: TECH_SAAS

| Metric ID | Display Name | Unit | Valid Range | Direction | Category | Baseline Weight |
|---|---|---|---|---|---|---|
| `monthly_recurring_revenue_growth` | MRR Growth Rate | % | -100 to 200 | Higher is better | Growth | 0.25 |
| `churn_rate` | Monthly Churn Rate | % | 0 to 100 | Lower is better | Retention | 0.20 |
| `customer_acquisition_cost` | Customer Acquisition Cost | USD | 0 to 1,000,000 | Lower is better | Acquisition | 0.15 |
| `lifetime_value` | Customer Lifetime Value | USD | 0 to 10,000,000 | Higher is better | Unit Economics | 0.15 |
| `net_revenue_retention` | Net Revenue Retention | % | 0 to 300 | Higher is better | Retention | 0.15 |
| `burn_rate` | Monthly Burn Rate | USD | 0 to 100,000,000 | Lower is better | Financial Health | 0.05 |
| `gross_margin` | Gross Margin | % | -100 to 100 | Higher is better | Profitability | 0.05 |

---

## Sector: RETAIL

| Metric ID | Display Name | Unit | Valid Range | Direction | Category | Baseline Weight |
|---|---|---|---|---|---|---|
| `gross_margin` | Gross Margin | % | -100 to 100 | Higher is better | Profitability | 0.20 |
| `inventory_turnover` | Inventory Turnover | Ratio | 0 to 100 | Higher is better | Operations | 0.20 |
| `average_order_value` | Average Order Value | USD | 0 to 100,000 | Higher is better | Revenue | 0.15 |
| `revenue_per_sqft` | Revenue per Sq Ft | USD | 0 to 10,000 | Higher is better | Productivity | 0.15 |
| `same_store_sales_growth` | Same Store Sales Growth | % | -100 to 200 | Higher is better | Growth | 0.15 |
| `sell_through_rate` | Sell-Through Rate | % | 0 to 100 | Higher is better | Operations | 0.10 |
| `return_rate` | Product Return Rate | % | 0 to 100 | Lower is better | Customer Sat | 0.05 |

---

## Severity Classification

Anomaly severity is scored on a continuous scale from 0.0 to 100.0.

| Band | Score Range | Operational Implication |
|---|---|---|
| **INFO** | 0.0 - 24.9 | Logged for trend tracking; no immediate action. |
| **WARNING** | 25.0 - 49.9 | Weekly review; monitor trajectory. |
| **CRITICAL** | 50.0 - 74.9 | Cross-functional review; operational adjustments required. |
| **SEVERE** | 75.0 - 100.0 | Executive escalation; immediate intervention. |

---

## Baseline Calibration

Synthetic baselines are generated per `(sector_id, revenue_band)` combination using parameterised distributions. The system supports the following revenue bands:

| Band ID | Annual Revenue Range |
|---|---|
| `UNDER_1M` | < $1M |
| `ONE_TO_10M` | $1M - $10M |
| `TEN_TO_50M` | $10M - $50M |
| `FIFTY_TO_100M` | $50M - $100M |
| `OVER_100M` | > $100M |

Baseline parameters are configured in `backend/core/ml_engine/config/sectors/`.

---

## Refusal Conditions

The system explicitly refuses to analyse when:

| Reason | Trigger | User Action |
|---|---|---|
| `insufficient_periods` | No metric has >= 6 time-series periods | Submit at least 6 months of data for any metric |
| `low_data_confidence` | All submitted metrics have `confidence < threshold` | Submit from a cleaner data source |
| `no_metrics_submitted` | Zero columns resolved to a recognised metric ID | Review mapping at the column-confirmation step |
| `contradictory_evidence` | Submitted metrics give irreconcilable signals | Check submitted values for consistency |

---

## Data Lineage

```
Raw CSV file (user upload)
  -> C2 ingest: shape detection, header normalisation
  -> C2 parser: period alias resolution, metric ID mapping
  -> CompanyInput.metrics[].values (TimeSeriesPoint list)
  -> C1 synthetic baseline lookup (sector YAML config)
  -> C1 feature extraction (slope, curvature, volatility)
  -> C1 z-score = (observed - baseline_mean) / baseline_std
  -> AnomalyReport.anomalies[].deviation.z_score
  -> C3 prescription target = AnomalyReport.anomalies[].deviation.expected_value
  -> EnrichedReport.prescriptions[].prescribed_adjustments[].target_value
```
