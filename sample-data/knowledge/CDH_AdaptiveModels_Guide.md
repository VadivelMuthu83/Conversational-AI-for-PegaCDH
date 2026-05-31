# Pega CDH — Adaptive Decision Manager (ADM): Complete Reference Guide

## Overview

Adaptive Decision Manager (ADM) is Pega CDH's built-in machine learning engine. It automatically builds, trains, and maintains predictive models for each Action × Channel combination without requiring data scientists or external ML pipelines.

ADM models produce a **Propensity score** — a probability between 0 and 1 — representing how likely a specific customer is to positively respond to a specific action on a specific channel. This propensity flows directly into the arbitration priority formula.

---

## How ADM Models Work

### Model Per Action × Channel

ADM creates a separate model for every unique Action × Channel combination.

```
Gold_Card_Offer × Web       → Model_001 (AUC: 0.74)
Gold_Card_Offer × Email     → Model_002 (AUC: 0.69)
Gold_Card_Offer × Mobile    → Model_003 (AUC: 0.71)
Personal_Loan × Web         → Model_004 (AUC: 0.82)
Personal_Loan × CallCentre  → Model_005 (AUC: 0.77)
```

This granularity captures the fact that a customer's response behaviour differs by channel. A customer who ignores web offers may respond well to a call centre conversation.

### Online Learning (Continuous Training)

ADM uses **online learning** — every interaction outcome immediately updates the model. There is no separate training batch job.

```
Customer sees Gold Card Offer on Web
    → Outcome: Accepted
    → Model_001 updates immediately
    → Next customer query uses updated model
```

This means ADM models improve continuously as more interactions accumulate.

### Propensity Calculation

For each customer-action-channel combination, ADM:
1. Extracts predictor values for this customer
2. Applies the trained model weights
3. Returns a propensity score [0.0, 1.0]
4. Score is fed to arbitration priority formula

---

## Model Types

ADM supports two model types. The appropriate type is selected automatically based on data volume, or can be configured manually.

### Naive Bayes (Default)
- **Algorithm:** Probabilistic classifier using Bayes theorem
- **Best for:** Early stage with < 500 responses
- **Training speed:** Instant — updates with each interaction
- **Interpretability:** High — predictor contributions are transparent
- **AUC range typically achieved:** 0.55 – 0.70

### Gradient Boosting (Recommended for production)
- **Algorithm:** Ensemble of decision trees (similar to XGBoost)
- **Best for:** Mature models with > 1,000 positive responses
- **Training speed:** Periodic batch retraining (configurable: hourly/daily)
- **Interpretability:** Medium — SHAP values available via Explainability Extract
- **AUC range typically achieved:** 0.65 – 0.85

**Configuration path:** CDH > Adaptive Models > Model Configuration > Model Type

---

## Predictors

Predictors are the input features used by ADM models. They are drawn from the customer's **context** — the data available at decision time.

### Predictor Categories

| Category | Examples | Notes |
|----------|----------|-------|
| Demographic | Age, Gender, Region, Tenure | Slow-changing, high availability |
| Product Holdings | AccountType, ProductCount, CardLimit | Available from CRM |
| Behavioural | WebVisits30d, EmailOpens, AppLogins | From Interaction History |
| Financial | Balance, CreditScore, DTIRatio | Sensitive — check compliance |
| Interaction | DaysSinceLastContact, LastChannel | Derived from IH |
| Calculated | RFM scores, Propensity segments | Computed by CDH |

### Predictor Lifecycle

Predictors go through a lifecycle within each model:

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| Active | Contributing positively to model | None |
| Inactive | Not improving model accuracy | Review — may remove |
| Negative | Actively hurting model accuracy | Remove or investigate |
| Symbolic | Categorical predictor with too many values | Reduce cardinality |
| Absent | Predictor missing for this customer | Check data feed |

### Configuring Predictors

**Configuration path:** CDH > Adaptive Models > [Model Name] > Predictors

Best practice — predictor selection:
1. Start with 15–25 predictors per model
2. Include a mix of demographic, behavioural, and financial predictors
3. Remove predictors with > 30% missing values
4. Remove predictors with near-zero variance
5. Review active predictor count after 500 responses — aim for 8–15 active

### Forbidden Predictors (Compliance)

Never use these as direct predictors due to regulatory risk:
- Race, ethnicity, national origin
- Religion
- Gender (jurisdiction-dependent — check local regulations)
- Disability status
- Political affiliation
- Postcode/ZIP as a proxy for race (indirect discrimination risk)

**Action:** Run the Explainability Extract monthly to audit predictor usage. Flag any sensitive predictors to compliance team immediately.

---

## Model Performance Metrics

### AUC (Area Under ROC Curve)

AUC is the primary ADM model quality metric. It measures how well the model distinguishes positive responders from negative responders.

| AUC Range | Rating | Interpretation | Action |
|-----------|--------|----------------|--------|
| 0.90 – 1.00 | Exceptional | Possible overfitting | Investigate |
| 0.80 – 0.90 | Excellent | High confidence predictions | Promote to production |
| 0.70 – 0.80 | Good | Reliable predictions | Monitor quarterly |
| 0.60 – 0.70 | Fair | Acceptable for low-volume actions | Review predictors |
| 0.50 – 0.60 | Poor | Little better than random | Retrain immediately |
| < 0.50 | Failing | Worse than random | Disable model |

### Response Count Thresholds

ADM model reliability depends on having sufficient training data.

| Response Count | Model Reliability | Recommended Action |
|---------------|-------------------|-------------------|
| < 100 | Very low | Use Naive Bayes, do not use for high-value decisions |
| 100 – 500 | Low | Naive Bayes, monitor weekly |
| 500 – 2,000 | Medium | Switch to Gradient Boosting |
| 2,000 – 10,000 | High | Gradient Boosting, stable predictions |
| > 10,000 | Very High | Fully mature model |

### Positivity Rate

Positivity = Positive Responses / Total Responses

Very low positivity (< 0.5%) means the model rarely sees positive outcomes — making it hard to learn what drives acceptance. Address by:
- Checking whether the action is genuinely being presented
- Reviewing whether the definition of a positive outcome is correct
- Considering whether the action should be broadened

---

## ADM Snapshot

The ADM Snapshot is an export of all model state at a point in time. It contains one row per model with current performance metrics.

### Key Snapshot Fields

| Field | Description | Use |
|-------|-------------|-----|
| ModelID | Unique model identifier | Join key |
| ModelName | Human-readable name (Action_Channel) | Display |
| AUC | Current AUC score | Primary quality metric |
| ResponseCount | Total training responses | Maturity indicator |
| PositiveResponses | Count of positive outcomes | Conversion count |
| NegativeResponses | Count of negative outcomes | Rejection count |
| Positivity | Accept rate | Baseline performance |
| ActivePredictors | Count of active predictors | Complexity indicator |
| SnapshotTime | When snapshot was taken | Trend analysis |
| Status | Active / Inactive / Champion / Challenger | Operational status |

### Taking a Snapshot

```
CDH > Adaptive Models > Export > Export Snapshot
Format: JSON or CSV
Frequency: Daily recommended for trend analysis
```

### Reading the Snapshot — Red Flags

Investigate immediately if you see:
- AUC < 0.60 on any active model
- ResponseCount < 200 on a model deployed > 30 days
- AUC dropped > 0.05 since last snapshot (model drift)
- ActivePredictors = 0 (model has no predictive features)
- Positivity = 0 (no positive outcomes recorded — data pipeline issue)

---

## Model Health Assessment Procedure

### Weekly Health Check (15 minutes)

1. Export ADM snapshot
2. Sort by AUC ascending
3. Identify all models with AUC < 0.65
4. Check ResponseCount for low-AUC models
5. Review top-5 and bottom-5 models
6. Log any models needing intervention

### Monthly Deep Review (2 hours)

1. Compare current snapshot to snapshot from 30 days ago
2. Calculate AUC delta for each model
3. Flag models with AUC drift > 0.05
4. Review predictor counts — any model losing active predictors?
5. Check for data pipeline issues (sudden drops in ResponseCount growth)
6. Run Explainability Extract to audit predictor usage for compliance

---

## Retraining and Model Refresh

### When to Retrain

| Trigger | Threshold | Action |
|---------|-----------|--------|
| AUC decline | > 0.05 drop over 30 days | Force retrain |
| Data drift | Predictor distribution shift detected | Retrain + check data pipeline |
| New predictors added | Any addition | Allow 500 responses before evaluating |
| Business model change | New product, new channel | Create new model |
| Seasonal effect | Quarterly | Schedule retrain |

### How to Force Retrain

```
CDH > Adaptive Models > [Model Name] > Actions > Reset Model
```

Warning: Resetting a model loses all accumulated learning. Use only when:
- Model AUC is below 0.55 and has > 1,000 responses (poor learning)
- Data pipeline error caused corrupt training data
- Major business change makes historical data irrelevant

### Scheduled Retraining

For Gradient Boosting models, configure periodic full retraining:
```
CDH > Adaptive Models > [Model Name] > Training Schedule
Recommended: Daily retraining for active models
             Weekly retraining for low-volume models
```

---

## Champion / Challenger for ADM Models

Running a Champion/Challenger test on ADM models allows you to safely evaluate a new model configuration before full deployment.

### Setup Procedure

1. Navigate to CDH > Adaptive Models > [Model Name] > Champion/Challenger
2. Configure Champion: current production model (100% traffic initially)
3. Configure Challenger: new model variant
4. Set traffic split: start with 10% Challenger
5. Monitor for minimum 1,000 interactions per group
6. Compare AUC and accept rate

### Promotion Decision

Promote Challenger to Champion when:
- Challenger AUC > Champion AUC by at least 0.02
- Statistical significance achieved (p < 0.05)
- No regression in downstream metrics (customer satisfaction, revenue)
- Minimum observation period: 14 days

---

## ADM and Interaction History Integration

ADM models are trained on outcomes stored in Interaction History. The data flow is:

```
Customer Interaction
    ↓
CDH Decision (Propensity from ADM + Arbitration)
    ↓
Interaction History Record Created (Outcome = "Impression")
    ↓
Customer Responds (Accept/Reject/Ignore)
    ↓
IH Record Updated (Outcome = "Accepted" / "Rejected")
    ↓
ADM Model Updated (online learning)
    ↓
Next Propensity Prediction Improved
```

### Data Pipeline Requirements

For ADM to train correctly:
- IH must capture the `pxDecisionTime` timestamp accurately
- Outcome must be updated within 24 hours of the interaction
- `SubjectID` / `CustomerID` must be consistent across sessions
- Action names must be consistent with ADM model names (case-sensitive)

---

## Adaptive Gradient Configuration

For advanced tuning of Gradient Boosting models:

| Parameter | Default | Lower Value Effect | Higher Value Effect |
|-----------|---------|-------------------|---------------------|
| Learning Rate | 0.1 | More stable, slower learning | Faster learning, risk of overfitting |
| Tree Depth | 6 | Simpler models, less overfitting | More complex, higher AUC potential |
| Min Samples Leaf | 20 | Overfit risk | Underfit risk |
| Subsample | 0.8 | Less variance | More variance |

**Configuration path:** CDH > Adaptive Models > Advanced Configuration

Recommendation: Do not change these defaults without statistical justification and A/B testing.

---

## Troubleshooting ADM Models

| Problem | Symptom | Cause | Fix |
|---------|---------|-------|-----|
| Model not improving | AUC flat at 0.5–0.55 for 30 days | No signal in predictors | Review and replace predictors |
| High AUC but low accept rate | AUC > 0.8, accept < 1% | Model overfitting or positivity too low | Check data pipeline, review positivity |
| Propensity always near 0.5 | No discrimination | Predictors not reaching model | Check data flow mapping |
| Sudden AUC drop | AUC falls > 0.1 in one week | Data pipeline change or model drift | Compare predictor distributions before/after |
| Model shows 0 responses | ResponseCount = 0 | IH not writing outcomes | Check IH data flow and outcome mapping |
| Champion/Challenger not splitting | All traffic to one group | Split configuration error | Verify split percentages sum to 100% |

---

## ADM Best Practices Summary

1. **One model per Action × Channel** — never share a model across channels
2. **Minimum 500 responses before trusting AUC** — below this, AUC fluctuates too much
3. **Monitor weekly** — AUC drift can be subtle and catches strategies off guard
4. **Review predictors monthly** — inactive predictors slow model computation
5. **Never use sensitive attributes** — race, gender, religion as direct or proxy predictors
6. **Champion/Challenger for every major change** — never switch production models without a test
7. **Align IH outcome timing** — delayed outcome capture degrades model quality
8. **Set Gradient Boosting for mature models** — switch from Naive Bayes at 500+ positive responses
9. **Document every model reset** — resets lose accumulated learning; audit trail is essential
10. **Use Explainability Extract** — verify predictor importance aligns with business intuition
