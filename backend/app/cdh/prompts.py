"""
CDH Prompts & Document Templates
=================================
Domain-specific system prompts for each analysis type,
and document generation templates for Pega CDH outputs.

The LLM receives:
  1. A CDH-aware ANALYST_SYSTEM prompt (knows all 5 data sources)
  2. Retrieved chunks tagged with cdh_source_id
  3. The user question

Output templates cover:
  - NBA Performance Report
  - ADM Model Health Report
  - Customer Segment Analysis
  - Channel Effectiveness Report
  - Value Finder Opportunity Report
"""
from app.cdh.sources import get_source_schema_context

# ─── Master CDH analyst system prompt ────────────────────────────────────────

CDH_ANALYST_SYSTEM = f"""You are a Pega CDH (Customer Decision Hub) expert analyst AI.

You deeply understand the Pega Next Best Action (NBA) architecture including:
- Adaptive Decision Manager (ADM) — machine learning models per Action × Channel
- Interaction History (IH) — the event log of every customer interaction
- Value Finder — segment-level value vs engagement gap analysis
- Arbitration — how actions compete via Value × Propensity × Weight × Context
- Champion/Challenger testing — comparing strategy variants

━━━ PEGA CDH DATA SOURCES YOU WILL ANALYSE ━━━

{get_source_schema_context()}

━━━ RESPONSE RULES ━━━

1. Always identify which CDH data source each insight comes from
   (e.g. "From ADM Snapshot:", "From IH data:")

2. Use Pega CDH terminology precisely:
   - "Propensity" not "probability" or "score"
   - "NBA action" not "recommendation"
   - "AUC" for model quality (flag < 0.6 as underperforming)
   - "Accept rate" = accepted impressions / total impressions
   - "Arbitration" for the decision engine priority calculation
   - "Engagement policy" for strategy rules

3. For Interaction History analysis, always report:
   - Impressions, Accepts, Rejects, Accept Rate
   - By Action × Channel breakdown where possible

4. For ADM Model analysis, always flag:
   - Models with AUC < 0.6 (underperforming — needs attention)
   - Models with < 200 responses (insufficient data)
   - Champion vs Challenger performance delta

5. Produce structured JSON when reporting metrics:
```json
{{
  "type": "table",
  "title": "descriptive title",
  "columns": ["col1", "col2"],
  "rows": [["val1", "val2"]],
  "files_used": ["filename"],
  "confidence": 0.9
}}
```

6. Always end with "Recommended Actions:" section listing 2-4 concrete next steps.
"""

# ─── Analysis-type specific prompts ───────────────────────────────────────────

NBA_PERFORMANCE_PROMPT = """
Analyse NBA strategy performance from the provided data.
Focus on:
- Top and bottom performing actions by accept rate
- Channel effectiveness comparison
- Propensity score distribution
- Week-over-week trends if time data available
- Actions that are shown frequently but accepted rarely (waste)
- Actions that are rarely shown but highly accepted (underutilised)

Output a performance table ranked by accept rate, then a recommendations section.
"""

ADM_HEALTH_PROMPT = """
Perform an ADM model health assessment.
For each model report:
- AUC score and interpretation (< 0.6 = poor, 0.6-0.7 = fair, > 0.7 = good, > 0.8 = excellent)
- Response count vs minimum threshold (200 responses needed for reliability)
- Active predictor count and top predictors
- Champion vs Challenger delta if applicable
- Trend across snapshots if multiple available

Flag models needing immediate attention with ⚠️.
Output a model health scorecard table.
"""

SEGMENT_ANALYSIS_PROMPT = """
Analyse customer segment performance using Value Finder and IH data.
Identify:
- Underserved segments (high value, low engagement) — top opportunity
- Overserved segments (low value, high engagement) — cost risk
- Segment-level accept rates by channel
- Total revenue opportunity if underserved segments are engaged

Output a 2×2 quadrant summary and ranked opportunity table.
"""

CHANNEL_EFFECTIVENESS_PROMPT = """
Compare NBA effectiveness across channels (Web, Email, Mobile, Call Centre etc).
For each channel report:
- Total impressions and accept rate
- Top 3 performing actions per channel
- Average propensity and priority scores
- Channel-specific ADM model AUC
- Recommended channel for each customer segment

Output a channel comparison table.
"""

EXPLAINABILITY_PROMPT = """
Analyse model explainability and predictor importance.
For each major action identify:
- Top 5 predictors driving propensity (positive contributors)
- Top 5 predictors suppressing propensity (negative contributors)
- Any potential fairness concerns (protected attributes influencing decisions)
- Predictor drift (if multiple snapshots available)

Flag any sensitive predictors (age, gender, ethnicity, location as proxy) with ⚠️.
"""

VALUE_FINDER_PROMPT = """
Analyse Value Finder output to identify revenue opportunities.
Report:
- Total customers in each quadrant (Underserved/Overserved/Balanced/Lost)
- Top 5 underserved segments ranked by opportunity value
- Recommended actions for each underserved segment
- Total revenue opportunity if gaps are closed
- Priority channels per segment

Output a segment opportunity table and executive summary.
"""

# ─── Query → prompt routing ───────────────────────────────────────────────────

QUERY_PROMPT_MAP = {
    # Keywords → specific analysis prompt
    ("auc", "model", "adm", "performance", "health", "predictor", "train"):
        ADM_HEALTH_PROMPT,
    ("segment", "value finder", "underserved", "overserved", "quadrant", "opportunity"):
        SEGMENT_ANALYSIS_PROMPT,
    ("channel", "email", "web", "mobile", "call", "sms", "push"):
        CHANNEL_EFFECTIVENESS_PROMPT,
    ("explainability", "explain", "predictor", "fairness", "audit", "why"):
        EXPLAINABILITY_PROMPT,
    ("value finder", "segment value", "engagement gap", "revenue"):
        VALUE_FINDER_PROMPT,
}

DEFAULT_PROMPT = NBA_PERFORMANCE_PROMPT


def route_analysis_prompt(query: str) -> str:
    """Pick the most relevant analysis prompt based on query keywords."""
    query_lower = query.lower()
    for keywords, prompt in QUERY_PROMPT_MAP.items():
        if any(kw in query_lower for kw in keywords):
            return prompt
    return DEFAULT_PROMPT


# ─── Document generation templates ────────────────────────────────────────────

DOCUMENT_TEMPLATES = {
    "nba_performance_report": {
        "title": "NBA Strategy Performance Report",
        "sections": [
            "Executive Summary",
            "Action Performance by Channel",
            "Weekly Trend Analysis",
            "Underperforming Actions",
            "Underutilised Actions",
            "ADM Model Health Summary",
            "Recommended Actions",
        ],
        "prompt_suffix": (
            "\n\nGenerate a complete formal report with all sections above. "
            "Use ### for section headers. Include a data table in each section. "
            "End with a numbered list of recommended actions prioritised by impact."
        ),
    },
    "adm_health_report": {
        "title": "ADM Model Health Assessment",
        "sections": [
            "Model Portfolio Overview",
            "AUC Performance Scorecard",
            "Models Requiring Attention",
            "Predictor Analysis",
            "Champion/Challenger Results",
            "Remediation Recommendations",
        ],
        "prompt_suffix": (
            "\n\nGenerate a complete ADM health report. "
            "Flag all models with AUC < 0.6 prominently. "
            "Include a full model scorecard table."
        ),
    },
    "segment_opportunity_report": {
        "title": "Customer Segment Opportunity Report",
        "sections": [
            "Segment Overview",
            "Underserved Segments (Priority Opportunities)",
            "Overserved Segments (Cost Risk)",
            "Revenue Opportunity Summary",
            "Recommended Campaign Actions",
        ],
        "prompt_suffix": (
            "\n\nGenerate a complete segment opportunity report. "
            "Quantify revenue opportunity in $ where possible. "
            "Prioritise segments by opportunity value."
        ),
    },
    "channel_effectiveness_report": {
        "title": "Channel Effectiveness Report",
        "sections": [
            "Channel Performance Summary",
            "Action-Channel Matrix",
            "Channel Optimisation Opportunities",
            "Recommendations",
        ],
        "prompt_suffix": (
            "\n\nGenerate a channel effectiveness report. "
            "Compare all channels on accept rate, volume, and propensity. "
            "Recommend channel mix optimisation."
        ),
    },
}


def get_document_prompt(template_key: str, base_question: str) -> str:
    """Build a full document generation prompt from a template."""
    template = DOCUMENT_TEMPLATES.get(template_key)
    if not template:
        return base_question

    sections = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(template["sections"]))
    return (
        f"Generate a detailed '{template['title']}' document.\n"
        f"Required sections:\n{sections}\n\n"
        f"Base question: {base_question}"
        f"{template['prompt_suffix']}"
    )
