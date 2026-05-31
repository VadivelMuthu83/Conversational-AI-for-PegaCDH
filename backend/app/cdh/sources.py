"""
CDH Data Source Registry
========================
Defines the 5 canonical Pega CDH data sources, their schemas,
column semantics, and how to parse/interpret them for RAG indexing.

Sources:
  1. Interaction History (IH)          — customer-action engagement events
  2. ADM Snapshot                      — Adaptive Decision Manager model scores
  3. Explainability Extract            — model decision explanations
  4. Actuals Dataset                   — ground-truth outcome labels
  5. Value Finder Output               — segment-level value/engagement scores

Each source gets:
  - Schema definition (columns + data types + descriptions)
  - Parsing hints for FileParser
  - Chunking strategy override
  - Domain-specific metadata tags for retrieval filtering
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ColumnDef:
    name: str
    dtype: str                       # "string" | "float" | "int" | "datetime" | "bool"
    description: str
    is_key: bool = False             # primary / join key
    is_metric: bool = False          # numeric metric to aggregate


@dataclass
class CDHDataSource:
    source_id: str                   # e.g. "interaction_history"
    display_name: str
    description: str
    typical_filename_patterns: List[str]   # glob patterns
    columns: List[ColumnDef]
    chunk_strategy: str = "recursive"      # override per source
    aggregation_hint: str = ""             # how to pre-aggregate before indexing
    join_keys: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def column_map(self) -> Dict[str, ColumnDef]:
        return {c.name.lower(): c for c in self.columns}

    def metric_columns(self) -> List[str]:
        return [c.name for c in self.columns if c.is_metric]

    def key_columns(self) -> List[str]:
        return [c.name for c in self.columns if c.is_key]

    def schema_description(self) -> str:
        lines = [f"Source: {self.display_name}", f"Description: {self.description}", "Columns:"]
        for c in self.columns:
            flag = " [KEY]" if c.is_key else (" [METRIC]" if c.is_metric else "")
            lines.append(f"  {c.name} ({c.dtype}){flag}: {c.description}")
        return "\n".join(lines)


# ─── 1. Interaction History ───────────────────────────────────────────────────

INTERACTION_HISTORY = CDHDataSource(
    source_id="interaction_history",
    display_name="Interaction History (IH)",
    description=(
        "Records every customer interaction with a Next Best Action — including "
        "impressions (shown), positive responses (accepts/clicks), negative responses "
        "(rejects/ignores), and conversions. Core CDH event log."
    ),
    typical_filename_patterns=["*IH*.csv", "*InteractionHistory*.csv", "*IHData*.json",
                               "*interaction_history*.csv", "*ih_export*.csv"],
    columns=[
        ColumnDef("CustomerID",       "string",   "Unique customer identifier", is_key=True),
        ColumnDef("SubjectID",        "string",   "Alias for CustomerID in some exports", is_key=True),
        ColumnDef("pxInteractionID",  "string",   "Unique interaction event ID", is_key=True),
        ColumnDef("ActionName",       "string",   "NBA action name (e.g. CreditCard_Offer)"),
        ColumnDef("ActionGroup",      "string",   "Group/bundle the action belongs to"),
        ColumnDef("Issue",            "string",   "Business issue (e.g. Retention, Growth)"),
        ColumnDef("Group",            "string",   "Issue group"),
        ColumnDef("Channel",          "string",   "Delivery channel (Web, Mobile, Email, Call)"),
        ColumnDef("Direction",        "string",   "Inbound or Outbound"),
        ColumnDef("Outcome",          "string",   "Impression / Clicked / Accepted / Rejected"),
        ColumnDef("OutcomeTime",      "datetime", "Timestamp of the outcome event"),
        ColumnDef("ExperimentGroup",  "string",   "Champion / Challenger / Control group"),
        ColumnDef("Propensity",       "float",    "Model propensity score [0,1]", is_metric=True),
        ColumnDef("Priority",         "float",    "Final arbitrated priority score", is_metric=True),
        ColumnDef("Weight",           "float",    "Action weight used in arbitration", is_metric=True),
        ColumnDef("Value",            "float",    "Business value of the action", is_metric=True),
        ColumnDef("Context",          "string",   "Situation/context rules applied"),
        ColumnDef("Rank",             "int",      "Rank of this action in the bundle", is_metric=True),
        ColumnDef("pxDecisionTime",   "datetime", "Timestamp of the decision"),
        ColumnDef("pyWorkID",         "string",   "Associated case/work object ID"),
    ],
    chunk_strategy="fixed",         # IH is tabular — fixed chunks work better
    aggregation_hint=(
        "Pre-aggregate to Action × Channel × Week level: "
        "count impressions, accepts, rejects; compute accept_rate = accepts/impressions; "
        "average propensity and priority per group. "
        "This reduces millions of rows to thousands of meaningful summary rows."
    ),
    join_keys=["CustomerID", "ActionName", "Channel"],
    tags=["interaction_history", "ih", "engagement", "nba", "outcomes"],
)

# ─── 2. ADM Snapshot ──────────────────────────────────────────────────────────

ADM_SNAPSHOT = CDHDataSource(
    source_id="adm_snapshot",
    display_name="ADM Model Snapshot",
    description=(
        "Adaptive Decision Manager (ADM) model performance snapshot. "
        "Contains AUC, response counts, predictor importance, and model health "
        "for each Action × Channel model in the Pega CDH strategy."
    ),
    typical_filename_patterns=["*ADM*.json", "*adm_snapshot*.json", "*ModelSnapshot*.csv",
                               "*adm_models*.csv", "*ADMModels*.json"],
    columns=[
        ColumnDef("ModelID",          "string",   "Unique ADM model identifier", is_key=True),
        ColumnDef("ModelName",        "string",   "Human-readable model name (Action_Channel)"),
        ColumnDef("ActionName",       "string",   "NBA action the model predicts"),
        ColumnDef("Channel",          "string",   "Channel this model applies to"),
        ColumnDef("Configuration",    "string",   "Pega configuration/issue group"),
        ColumnDef("AUC",              "float",    "Area Under ROC Curve [0.5–1.0]", is_metric=True),
        ColumnDef("Performance",      "float",    "ADM performance metric (0–100)", is_metric=True),
        ColumnDef("ResponseCount",    "int",      "Total responses used for training", is_metric=True),
        ColumnDef("PositiveResponses","int",      "Positive (accept) response count", is_metric=True),
        ColumnDef("NegativeResponses","int",      "Negative (reject) response count", is_metric=True),
        ColumnDef("Positivity",       "float",    "Positive response rate", is_metric=True),
        ColumnDef("SnapshotTime",     "datetime", "When the snapshot was taken"),
        ColumnDef("ModelType",        "string",   "Gradient Boost / Naive Bayes / etc."),
        ColumnDef("PredictorCount",   "int",      "Number of active predictors", is_metric=True),
        ColumnDef("ActivePredictors", "string",   "List of active predictor names"),
        ColumnDef("Status",           "string",   "Active / Inactive / Champion / Challenger"),
        ColumnDef("ContextWeight",    "float",    "Context-level weight applied", is_metric=True),
    ],
    chunk_strategy="fixed",
    aggregation_hint=(
        "Group by ActionName × Channel × SnapshotTime. "
        "Flag models with AUC < 0.6 as underperforming. "
        "Track AUC trend over multiple snapshots."
    ),
    join_keys=["ModelID", "ActionName", "Channel"],
    tags=["adm", "model", "auc", "performance", "adaptive", "predictors"],
)

# ─── 3. Explainability Extract ────────────────────────────────────────────────

EXPLAINABILITY_EXTRACT = CDHDataSource(
    source_id="explainability_extract",
    display_name="Explainability Extract",
    description=(
        "Per-customer, per-action decision explanation from ADM. "
        "Shows which predictors drove each propensity score — used for "
        "fairness auditing, debugging, and regulatory compliance."
    ),
    typical_filename_patterns=["*Explainability*.csv", "*explain*.csv",
                               "*ExplainabilityExtract*.json", "*decision_explain*.csv"],
    columns=[
        ColumnDef("CustomerID",      "string",   "Customer identifier", is_key=True),
        ColumnDef("ActionName",      "string",   "Action being explained", is_key=True),
        ColumnDef("Channel",         "string",   "Channel context"),
        ColumnDef("Propensity",      "float",    "Final propensity score", is_metric=True),
        ColumnDef("PredictorName",   "string",   "Predictor field name"),
        ColumnDef("PredictorValue",  "string",   "Customer's value for this predictor"),
        ColumnDef("PredictorWeight", "float",    "Contribution weight of predictor", is_metric=True),
        ColumnDef("Direction",       "string",   "Positive / Negative contribution"),
        ColumnDef("Rank",            "int",      "Predictor importance rank", is_metric=True),
        ColumnDef("DecisionTime",    "datetime", "When the decision was made"),
        ColumnDef("ModelID",         "string",   "ADM model that made the decision"),
    ],
    chunk_strategy="recursive",
    aggregation_hint=(
        "Aggregate predictor importance across customers: "
        "for each ActionName × PredictorName, compute mean PredictorWeight and frequency. "
        "This reveals which features drive each action globally."
    ),
    join_keys=["CustomerID", "ActionName", "Channel"],
    tags=["explainability", "xai", "predictors", "fairness", "audit"],
)

# ─── 4. Actuals Dataset ───────────────────────────────────────────────────────

ACTUALS_DATASET = CDHDataSource(
    source_id="actuals_dataset",
    display_name="Actuals Dataset",
    description=(
        "Ground-truth outcome labels matched back to IH interactions. "
        "Used to evaluate model accuracy and retrain ADM models. "
        "Links to IH via InteractionID."
    ),
    typical_filename_patterns=["*Actuals*.csv", "*actuals*.csv",
                               "*ActualsDataset*.json", "*ground_truth*.csv"],
    columns=[
        ColumnDef("InteractionID",   "string",   "Links back to IH pxInteractionID", is_key=True),
        ColumnDef("CustomerID",      "string",   "Customer identifier", is_key=True),
        ColumnDef("ActionName",      "string",   "Action taken"),
        ColumnDef("Channel",         "string",   "Channel"),
        ColumnDef("ActualOutcome",   "string",   "True label: Accepted / Rejected / Converted"),
        ColumnDef("OutcomeDate",     "datetime", "Date the actual outcome was recorded"),
        ColumnDef("ConversionValue", "float",    "Revenue/value if converted", is_metric=True),
        ColumnDef("ModelPropensity", "float",    "Propensity score at decision time", is_metric=True),
        ColumnDef("ActualLabel",     "int",      "Binary: 1=positive, 0=negative", is_metric=True),
    ],
    chunk_strategy="fixed",
    aggregation_hint=(
        "Compute lift = actual_accept_rate / baseline_accept_rate per Action × Channel. "
        "Join with IH on InteractionID to link model propensity to actual outcomes."
    ),
    join_keys=["InteractionID", "CustomerID", "ActionName"],
    tags=["actuals", "outcomes", "labels", "conversion", "lift"],
)

# ─── 5. Value Finder ──────────────────────────────────────────────────────────

VALUE_FINDER = CDHDataSource(
    source_id="value_finder",
    display_name="Value Finder Output",
    description=(
        "Segment-level analysis of customer value vs engagement. "
        "Identifies under-served segments (high value, low engagement) "
        "and over-served segments (low value, high engagement). "
        "Output of Pega Value Finder component in CDH."
    ),
    typical_filename_patterns=["*ValueFinder*.csv", "*value_finder*.csv",
                               "*ValueFinder*.json", "*segment_value*.csv"],
    columns=[
        ColumnDef("SegmentID",         "string",  "Customer segment identifier", is_key=True),
        ColumnDef("SegmentName",       "string",  "Readable segment name"),
        ColumnDef("CustomerCount",     "int",     "Customers in segment", is_metric=True),
        ColumnDef("EngagementScore",   "float",   "Current engagement level [0–100]", is_metric=True),
        ColumnDef("ValueScore",        "float",   "Business value score [0–100]", is_metric=True),
        ColumnDef("EngagementGap",     "float",   "Value − Engagement delta", is_metric=True),
        ColumnDef("TopActions",        "string",  "Recommended actions for this segment"),
        ColumnDef("Channel",           "string",  "Recommended channel"),
        ColumnDef("OpportunityValue",  "float",   "Estimated revenue uplift if gap closed", is_metric=True),
        ColumnDef("Quadrant",          "string",  "Underserved/Overserved/Balanced/Lost"),
        ColumnDef("SnapshotDate",      "datetime","Date of the Value Finder run"),
    ],
    chunk_strategy="recursive",
    aggregation_hint=(
        "Sort by EngagementGap descending to find most underserved segments. "
        "Sum OpportunityValue across Underserved quadrant for total revenue opportunity."
    ),
    join_keys=["SegmentID"],
    tags=["value_finder", "segments", "engagement", "opportunity", "underserved"],
)

# ─── Registry ─────────────────────────────────────────────────────────────────

CDH_SOURCES: Dict[str, CDHDataSource] = {
    s.source_id: s for s in [
        INTERACTION_HISTORY,
        ADM_SNAPSHOT,
        EXPLAINABILITY_EXTRACT,
        ACTUALS_DATASET,
        VALUE_FINDER,
    ]
}


def detect_source(filename: str) -> Optional[CDHDataSource]:
    """
    Auto-detect which CDH data source a file belongs to
    based on filename pattern matching.
    """
    import fnmatch
    fname_lower = filename.lower()
    for source in CDH_SOURCES.values():
        for pattern in source.typical_filename_patterns:
            if fnmatch.fnmatch(fname_lower, pattern.lower()):
                return source
    return None


def get_source_schema_context() -> str:
    """
    Build a full schema description string for all CDH sources.
    Injected into the LLM system prompt so it understands the data.
    """
    parts = []
    for source in CDH_SOURCES.values():
        parts.append(source.schema_description())
    return "\n\n".join(parts)
