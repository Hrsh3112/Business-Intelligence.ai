from typing import List, Tuple, Optional, Dict, Any
from .schemas import AnomalyReport, Anomaly, Prescription, Adjustment

# Rule configuration mapping: (sector_id, metric_id) -> (
#   display_name, action, direction_symbol, rationale,
#   controllable_lever, expected_impact, owner, action_confidence, monitoring_plan
# )
RULE_TABLE: Dict[Tuple[str, str], Tuple[str, str, str, str, str, str, str, str, str]] = {
    # TECH_SAAS sector rules
    ("TECH_SAAS", "monthly_recurring_revenue_growth"): (
        "Monthly Recurring Revenue Growth",
        "INCREASE",
        "+",
        "Accelerate monthly recurring revenue growth to meet synthetic profile benchmarks and drive top-line momentum.",
        "Sales pipeline velocity & marketing spend allocation",
        "Accelerates new customer acquisition and expands subscription revenue momentum.",
        "VP of Sales / Chief Revenue Officer",
        "HIGH",
        "Review pipeline conversion and weekly MRR additions over the next 2 quarters.",
    ),
    ("TECH_SAAS", "churn_rate"): (
        "Churn Rate",
        "DECREASE",
        "-",
        "Reduce customer churn rate to stabilize the recurring revenue base and prevent customer attrition leakage.",
        "Customer onboarding & proactive retention interventions",
        "Each 1pp churn reduction protects ARR base and extends customer lifetime.",
        "VP of Customer Success",
        "HIGH",
        "Track monthly cohort churn rate and account health scores for 3 consecutive periods.",
    ),
    ("TECH_SAAS", "customer_acquisition_cost"): (
        "Customer Acquisition Cost",
        "DECREASE",
        "-",
        "Optimize marketing channels and sales efficiency to bring customer acquisition costs in line with the cohort baseline.",
        "Paid acquisition channel optimization & SDR efficiency",
        "Lowers blended acquisition spend, improving payback period to < 12 months.",
        "Head of Growth Marketing",
        "MEDIUM",
        "Monitor channel-level CAC and lead-to-opportunity ratios monthly.",
    ),
    ("TECH_SAAS", "lifetime_value"): (
        "Lifetime Value",
        "INCREASE",
        "+",
        "Maximize customer lifetime value through targeted expansion revenue, upselling, and retention efforts.",
        "Pricing tier restructuring & cross-sell expansion",
        "Increases average contract value (ACV) and boosts net dollar retention.",
        "Chief Product Officer / VP Product",
        "MEDIUM",
        "Measure quarterly expansion revenue and net retention across existing accounts.",
    ),
    ("TECH_SAAS", "net_revenue_retention"): (
        "Net Revenue Retention",
        "INCREASE",
        "+",
        "Improve net revenue retention by driving customer expansion and mitigating downgrades and churn.",
        "Expansion packaging, add-on modules, and renewal incentives",
        "Achieves compounding growth from installed base even amidst lower top-of-funnel velocity.",
        "Chief Revenue Officer",
        "HIGH",
        "Audit net revenue retention and contraction rates on a monthly cadence.",
    ),
    ("TECH_SAAS", "burn_rate"): (
        "Burn Rate",
        "DECREASE",
        "-",
        "Optimize operating expenses and burn rate to extend cash runway and enhance capital efficiency.",
        "Operating expenditure rationalization & hiring pacing",
        "Extends cash runway by 3-6 months and improves unit economics.",
        "CFO / Finance Team",
        "HIGH",
        "Review OPEX vs budget and runway forecast on a bi-weekly basis.",
    ),
    ("TECH_SAAS", "gross_margin"): (
        "Gross Margin",
        "INCREASE",
        "+",
        "Enhance gross margin by optimizing hosting costs, COGS, and service delivery efficiency.",
        "Infrastructure cost optimization & third-party API spend management",
        "Expands gross profit margin by reducing direct cloud and service delivery costs.",
        "VP of Engineering / VP Infrastructure",
        "HIGH",
        "Track hosting cost per active user and gross margin percentage monthly.",
    ),

    # RETAIL sector rules (all 8 retail metrics)
    ("RETAIL", "gross_margin"): (
        "Gross Margin",
        "INCREASE",
        "+",
        "Optimize pricing strategy, manage COGS, and renegotiate supplier terms to address retail margin compression.",
        "Supplier renegotiation & promotional markdown governance",
        "Recovers margin compression and improves merchandise profitability.",
        "Head of Merchandising / Procurement",
        "HIGH",
        "Monitor weekly category gross margin and vendor rebate realization.",
    ),
    ("RETAIL", "inventory_turnover"): (
        "Inventory Turnover",
        "INCREASE",
        "+",
        "Accelerate inventory turnover velocity to free up working capital and reduce dead-stock holding costs.",
        "Dynamic inventory replenishment & targeted clearance campaigns",
        "Frees up working capital and prevents obsolescence / dead-stock accrual.",
        "Supply Chain / Inventory Director",
        "HIGH",
        "Track weeks of supply and inventory turn ratio bi-weekly.",
    ),
    ("RETAIL", "average_order_value"): (
        "Average Order Value",
        "INCREASE",
        "+",
        "Implement cross-selling, upselling, and bundle promotions to increase basket size and average order value.",
        "Checkout cross-sell recommendations & minimum order value incentives",
        "Increases basket size and shipping economics per transaction.",
        "E-Commerce / Store Operations Lead",
        "MEDIUM",
        "Track daily AOV and multi-item basket percentages.",
    ),
    ("RETAIL", "revenue_per_sqft"): (
        "Revenue per Sq Ft",
        "INCREASE",
        "+",
        "Improve store layout, merchandising efficiency, and footfall conversions to enhance store productivity.",
        "Visual merchandising & store layout re-allocation",
        "Maximizes sales yield from high-footfall floor zones.",
        "Retail Operations Manager",
        "MEDIUM",
        "Review monthly sales per square foot by department and store location.",
    ),
    ("RETAIL", "same_store_sales_growth"): (
        "Same Store Sales Growth",
        "INCREASE",
        "+",
        "Drive same-store sales growth via local store marketing, loyalty program engagement, and optimized assortments.",
        "Local store marketing & loyalty customer re-engagement",
        "Drives comp-store traffic and repeated purchase frequency.",
        "Regional Retail Director",
        "MEDIUM",
        "Monitor weekly comp-store sales growth versus prior-year periods.",
    ),
    ("RETAIL", "sell_through_rate"): (
        "Sell-Through Rate",
        "INCREASE",
        "+",
        "Optimize clearance promotions, markdown cadence, and inventory allocation to improve sell-through efficiency.",
        "Early markdown cadence & promotional product placement",
        "Accelerates inventory sell-through during peak seasonal selling windows.",
        "Category Merchandising Manager",
        "HIGH",
        "Audit weekly sell-through percentages against seasonal targets.",
    ),
    ("RETAIL", "customer_acquisition_cost"): (
        "Customer Acquisition Cost",
        "DECREASE",
        "-",
        "Improve digital marketing efficiency, refine audience targeting, and lower customer acquisition costs.",
        "Digital ad targeting & local influencer partnership efficiency",
        "Improves ROAS and lowers cost per new retail shopper.",
        "Retail Marketing Lead",
        "MEDIUM",
        "Track blended and paid acquisition cost per new buyer monthly.",
    ),
    ("RETAIL", "return_rate"): (
        "Return Rate",
        "DECREASE",
        "-",
        "Address product return leakage by improving product sizing guides, description accuracy, and quality control.",
        "Sizing accuracy guides, quality inspections & product description enhancements",
        "Reduces reverse logistics expenses and protects realized revenue.",
        "QA / Customer Experience Director",
        "HIGH",
        "Track weekly return percentages and category return reason breakdowns.",
    ),
}

def get_priority(severity_label: str) -> str:
    """
    Derives prescription priority from the anomaly severity label:
    - CRITICAL or SEVERE -> HIGH
    - WARNING -> MEDIUM
    - INFO -> LOW
    """
    label = severity_label.upper()
    if label in ("CRITICAL", "SEVERE"):
        return "HIGH"
    elif label == "WARNING":
        return "MEDIUM"
    else:
        return "LOW"

def find_submitted_metric_value(
    anomaly_report: AnomalyReport,
    target_metric_id: str,
    current_anomaly: Anomaly
) -> Tuple[Optional[float], str]:
    """
    Checks whether the target metric was submitted. If found in the anomaly report
    (either as the current anomaly, another anomaly, or in healthy highlights),
    returns its value and 'submitted'. Otherwise returns None and 'not_available'.
    """
    if target_metric_id == current_anomaly.metric_id:
        return current_anomaly.deviation.observed_current, "submitted"

    for anomaly in anomaly_report.anomalies:
        if anomaly.metric_id == target_metric_id:
            return anomaly.deviation.observed_current, "submitted"

    for highlight in anomaly_report.non_anomalous_highlights:
        if highlight.metric_id == target_metric_id:
            if highlight.observed_value is not None:
                return highlight.observed_value, "submitted"

    return None, "not_available"

def format_value(value: float, metric_id: str) -> str:
    """Formats values nicely for the summary text."""
    lower_id = metric_id.lower()
    if any(k in lower_id for k in ("rate", "margin", "growth", "percentile", "retention", "share", "ratio")):
        # If it looks like a percentage (typically between 0 and 1 or 0 and 100)
        return f"{value:.2f}%"
    elif any(k in lower_id for k in ("cost", "revenue", "spend", "burn", "value")):
        return f"${value:,.2f}"
    else:
        return f"{value:.2f}"

def build_prescription(
    anomaly_report: AnomalyReport,
    anomaly: Anomaly,
    unmatched_ids: List[str]
) -> Optional[Prescription]:
    """
    Generates a deterministic prescription for the given anomaly using the rule table.
    Appends anomaly_id to unmatched_ids and returns None if no rule matches.
    """
    sector_id = anomaly_report.sector_id
    metric_id = anomaly.metric_id
    rule_key = (sector_id, metric_id)

    if rule_key not in RULE_TABLE:
        unmatched_ids.append(anomaly.anomaly_id)
        return None

    (
        display_name,
        action,
        direction_symbol,
        rationale,
        controllable_lever,
        expected_impact,
        owner,
        action_confidence,
        monitoring_plan,
    ) = RULE_TABLE[rule_key]

    # Current value guardrail (§6.4)
    current_value, current_value_source = find_submitted_metric_value(
        anomaly_report, metric_id, anomaly
    )

    # Expected value from report (already band-adjusted synthetic baseline)
    target_value = anomaly.deviation.expected_value
    target_basis = "profile_baseline"

    # Compute delta if current value is available
    delta = None
    if current_value is not None:
        delta = target_value - current_value

    priority = get_priority(anomaly.severity_label)

    adjustment = Adjustment(
        target_metric_id=metric_id,
        target_display_name=display_name,
        action=action,
        direction_symbol=direction_symbol,
        current_value=current_value,
        current_value_source=current_value_source,
        target_value=target_value,
        target_basis=target_basis,
        delta=delta,
        priority=priority,
        rationale=rationale,
        controllable_lever=controllable_lever,
        expected_impact=expected_impact,
        owner=owner,
        action_confidence=action_confidence,
        monitoring_plan=monitoring_plan,
    )

    # Format the summary text
    current_str = format_value(current_value, metric_id) if current_value is not None else "N/A"
    target_str = format_value(target_value, metric_id)
    summary_text = (
        f"Corrective adjustment prescribed for {display_name} to move from "
        f"{current_str} to the baseline target of {target_str} (priority: {priority})."
    )

    return Prescription(
        anomaly_id=anomaly.anomaly_id,
        prescribed_adjustments=[adjustment],
        prescription_summary=summary_text
    )
