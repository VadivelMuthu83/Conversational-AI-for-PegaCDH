# Pega CDH — Actuals Dataset: Complete Reference Guide

## Overview

The Actuals Dataset is the ground-truth outcome record that links real customer responses back to the CDH decisions that generated them. It is the foundation for measuring model accuracy, calculating lift, and validating that ADM propensity predictions align with actual customer behaviour.

Without the Actuals Dataset, ADM models cannot be properly evaluated, Impact Analyzer projections cannot be validated, and the business cannot measure the true ROI of its NBA strategy.

---

## What the Actuals Dataset Contains

The Actuals Dataset joins two sources:

1. **CDH Decision Record** — what CDH decided and what propensity it assigned
2. **Real-world Outcome** — what the customer actually did, recorded by downstream systems (CRM, billing, digital analytics)

| Field | Source | Description |
|-------|--------|-------------|
| InteractionID | CDH / IH | Links to IH pxInteractionID — the join key |
| CustomerID | CDH / IH | Customer unique identifier |
| ActionName | CDH | Name of the action that was presented |
| Channel | CDH | Delivery channel |
| ModelPropensity | CDH | ADM propensity score at decision time [0.0–1.0] |
| ArbitrationPriority | CDH | Final priority score used in arbitration |
| OutcomeDate | Downstream | Date the actual outcome was recorded |
| ActualOutcome | Downstream | Text label: Accepted / Rejected / Converted / Ignored |
| ActualLabel | Derived | Binary: 1 = positive response, 0 = negative |
| ConversionValue | Downstream | Revenue generated if converted (£ value) |
| DaysToConvert | Derived | Days between impression and conversion |
| ExperimentGroup | CDH | Champion or Challenger (if applicable) |

---

## How Actuals Data Is Generated

### The Outcome Pipeline

```
CDH presents action to customer
    ↓
IH record created: Outcome = "Impression"
pxInteractionID assigned (unique per interaction)
    ↓
Customer responds (immediately or later)
    ↓
Downstream system records outcome:
  Web analytics: click / no-click
  CRM: application submitted / not submitted
  Billing: product activated / not activated
    ↓
Outcome mapped back to InteractionID
    ↓
IH record updated: Outcome = "Accepted" / "Rejected"
    ↓
Actuals Dataset created by joining:
  IH (CDH side) + CRM/billing (outcome side)
```

### Outcome Definition by Action Type

Each action type requires a different outcome definition:

| Action Type | Positive Outcome | Capture System | Typical Lag |
|------------|-----------------|----------------|-------------|
| Credit Card Offer | Application submitted | CRM | 0–7 days |
| Personal Loan | Application and approval | CRM + Underwriting | 3–14 days |
| Insurance Offer | Policy purchased | CRM / InsuranceSystem | 0–3 days |
| Balance Transfer | Transfer initiated | Billing | 1–5 days |
| Upgrade Offer | Product upgrade completed | CRM | 0–2 days |
| Digital Enrolment | Feature activated | Digital Analytics | 0–1 days |
| Service Improvement | Complaint resolved | CRM | 7–30 days |

**Important:** The outcome definition must be agreed before deployment and remain consistent. Changing the outcome definition part-way through invalidates historical comparisons.

---

## Actuals Dataset Construction

### Method 1 — Real-Time IH Update (Preferred)

CDH is configured to receive outcome events directly. When a customer converts, the downstream system sends an event to CDH which updates the IH record immediately.

```
Customer applies for credit card on website
    ↓
CRM API call to CDH: POST /outcomes
  {
    "interactionId": "IH-20240115-00123456",
    "outcome": "Accepted",
    "conversionValue": 0,
    "outcomeDate": "2024-01-15T14:32:00"
  }
    ↓
CDH updates IH record
ADM model updates propensity immediately
```

**Configuration path:** CDH > Interaction > Outcome Configuration > Real-Time Outcome API

### Method 2 — Batch Outcome Upload

For systems without real-time API capability, outcomes are uploaded in batch.

```
Daily batch file from CRM:
InteractionID,CustomerID,ActualOutcome,OutcomeDate,ConversionValue
IH-2024-001,C001,Accepted,2024-01-15,0
IH-2024-002,C002,Rejected,2024-01-15,0
IH-2024-003,C003,Accepted,2024-01-16,800

Upload path: CDH > Data Management > Outcome Upload
Frequency: Daily (minimum), real-time preferred
```

### Method 3 — IH Export + Downstream Join (Analytics)

For analysis purposes, the Actuals Dataset can be constructed offline:

```sql
-- Join CDH Interaction History with CRM outcome data
SELECT
    ih.pxInteractionID         AS InteractionID,
    ih.SubjectID               AS CustomerID,
    ih.ActionName,
    ih.Channel,
    ih.Propensity              AS ModelPropensity,
    ih.Priority                AS ArbitrationPriority,
    ih.pxDecisionTime          AS DecisionTime,
    ih.ExperimentGroup,
    crm.OutcomeDate,
    crm.OutcomeType            AS ActualOutcome,
    crm.RevenueGenerated       AS ConversionValue,
    CASE WHEN crm.OutcomeType IN ('Accepted','Converted','Activated')
         THEN 1 ELSE 0 END    AS ActualLabel,
    DATEDIFF(crm.OutcomeDate, ih.pxDecisionTime) AS DaysToConvert
FROM InteractionHistory ih
LEFT JOIN CRM_Outcomes crm
    ON ih.pxInteractionID = crm.InteractionID
WHERE ih.pxDecisionTime >= DATEADD(day, -90, GETDATE())
```

---

## Using the Actuals Dataset for Analysis

### 1 — Measuring Model Accuracy (Lift)

**Lift** measures how much better ADM predictions are compared to random selection.

```
Overall accept rate (baseline) = Total accepts / Total impressions

Lift for propensity band:
  Group customers by propensity decile (0–10%, 10–20%, ... 90–100%)
  For each decile: Actual accept rate / Overall accept rate

Perfect model:     Lift = 10.0 in top decile, 0.0 in bottom decile
Good model:        Lift > 3.0 in top decile
Random model:      Lift = 1.0 in all deciles
```

**Lift Chart Example:**

| Propensity Decile | Propensity Range | Impressions | Actual Accepts | Accept Rate | Lift |
|------------------|-----------------|-------------|----------------|-------------|------|
| 10 (top) | 0.80–1.00 | 1,234 | 312 | 25.3% | 5.8 |
| 9 | 0.65–0.80 | 1,456 | 248 | 17.0% | 3.9 |
| 8 | 0.52–0.65 | 1,567 | 189 | 12.1% | 2.8 |
| 7 | 0.42–0.52 | 1,489 | 143 | 9.6% | 2.2 |
| 6 | 0.34–0.42 | 1,512 | 112 | 7.4% | 1.7 |
| 5 | 0.27–0.34 | 1,488 | 86 | 5.8% | 1.3 |
| 4 | 0.21–0.27 | 1,503 | 68 | 4.5% | 1.0 |
| 3 | 0.15–0.21 | 1,478 | 44 | 3.0% | 0.7 |
| 2 | 0.09–0.15 | 1,523 | 28 | 1.8% | 0.4 |
| 1 (bottom) | 0.00–0.09 | 1,450 | 15 | 1.0% | 0.2 |

Overall accept rate: 4.35%. Top decile lift of 5.8 is excellent — this model is working well.

### 2 — Calculating Revenue Attribution

```
Total revenue attributed to CDH NBA strategy:
  SUM(ConversionValue) WHERE ActualLabel = 1

Revenue per accepted action:
  AVG(ConversionValue) WHERE ActualLabel = 1

Revenue per impression:
  SUM(ConversionValue) / COUNT(DISTINCT InteractionID)
```

### 3 — Validating ADM Propensity Calibration

A well-calibrated model means that customers with propensity = 0.4 actually accept at a 40% rate.

**Calibration Check:**

| Propensity Band | Predicted Rate | Actual Rate | Calibration Error |
|----------------|---------------|-------------|-------------------|
| 0.00–0.10 | 5.0% | 2.3% | Over-predicted (poor) |
| 0.10–0.20 | 15.0% | 12.1% | Slightly over |
| 0.20–0.30 | 25.0% | 24.8% | ✅ Well calibrated |
| 0.30–0.40 | 35.0% | 34.2% | ✅ Well calibrated |
| 0.40–0.50 | 45.0% | 43.7% | ✅ Well calibrated |
| 0.50+ | 55.0% | 61.2% | Under-predicted |

Models with poor calibration in low-propensity bands may be rejecting customers who would actually convert — consider adjusting propensity thresholds.

### 4 — Champion / Challenger Evaluation

Use Actuals Dataset to compare Champion vs Challenger experimental groups:

```sql
SELECT
    ExperimentGroup,
    COUNT(*) AS Impressions,
    SUM(ActualLabel) AS Accepts,
    AVG(ActualLabel) AS AcceptRate,
    AVG(ModelPropensity) AS AvgPropensity,
    SUM(ConversionValue) AS TotalRevenue,
    AVG(ConversionValue) AS RevenuePerAccept
FROM ActualsDataset
WHERE ExperimentGroup IN ('Champion', 'Challenger')
    AND DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY ExperimentGroup
```

---

## Actuals Dataset Quality Issues

### Issue 1 — Outcome Lag

**Problem:** Customers who accepted today may not show in the Actuals Dataset for several days (e.g. credit card applications take 3–7 days to process).

**Impact:** Recent impressions appear to have 0% accept rate — understating model performance.

**Fix:** Apply a lag correction. For any analysis, exclude impressions from the last N days where N = typical conversion lag for that action type.

### Issue 2 — Unmatched Interactions

**Problem:** IH records exist but no matching CRM outcome record found (NULL join).

**Cause:** 
- Customer abandoned mid-process
- Technical failure in outcome capture
- CustomerID mismatch between CDH and CRM

**Fix:** 
- Treat unmatched records as rejected (ActualLabel = 0) for conservative analysis
- Investigate match rate — target > 98% match rate for direct digital channels

**Match Rate Monitoring:**
```
Match rate = COUNT(matched) / COUNT(all IH impressions)
Alert if: Match rate < 95% for any channel
```

### Issue 3 — Duplicate Outcomes

**Problem:** Same InteractionID appears multiple times in Actuals Dataset with different outcomes.

**Cause:** CRM sends outcome event multiple times (retry logic), or customer's status changes (accepted then cancelled).

**Fix:** Define a deduplication rule. Standard approach: use the **most positive** outcome (Accepted > Rejected > Ignored) and the **latest** outcome date.

### Issue 4 — Outcome Definition Drift

**Problem:** What counts as "Accepted" changes over time (e.g. previously required product activation, now requires only application submission).

**Fix:** Maintain an outcome definition log with effective dates. Segment Actuals Dataset analysis by definition period.

---

## Actuals Dataset File Format

### Standard CSV Export Structure

```
InteractionID,CustomerID,ActionName,Channel,DecisionTime,ModelPropensity,ArbitrationPriority,ActualOutcome,ActualLabel,OutcomeDate,ConversionValue,DaysToConvert,ExperimentGroup
IH-2024-001,C0012345,Gold_Card_Offer,Web,2024-01-15 09:32:11,0.421,252.0,Accepted,1,2024-01-15,0,0,Champion
IH-2024-002,C0054321,Personal_Loan,Email,2024-01-15 10:14:32,0.183,115.2,Rejected,0,2024-01-15,0,0,Champion
IH-2024-003,C0098765,Balance_Transfer,Web,2024-01-15 11:01:45,0.612,247.5,Accepted,1,2024-01-17,400,2,Challenger
IH-2024-004,C0011223,Travel_Insurance,Mobile,2024-01-15 11:45:00,0.552,109.8,,,,,Champion
```

Note: Rows 4 has no outcome yet (outcome columns are blank) — still pending.

### File Naming Convention

```
ActualsDataset_YYYYMMDD_[scope].csv

Examples:
ActualsDataset_20240115_Full.csv
ActualsDataset_20240115_Web.csv
ActualsDataset_20240115_Q4Campaign.csv
```

---

## Actuals Dataset in RAG Analysis

When the Actuals Dataset is loaded into the RAG knowledge base, the analyst can answer questions such as:

- "What is the lift of the Gold Card Offer model in the top propensity decile?"
- "Which actions have the highest calibration error — where is propensity most inaccurate?"
- "What is the revenue attribution for the Champion vs Challenger groups in Q1?"
- "Which actions have the highest DaysToConvert — where are we measuring too late?"
- "What percentage of IH impressions have matched outcome records?"

---

## Monthly Actuals Review Checklist

| Check | Metric | Alert Threshold | Action if Breached |
|-------|--------|----------------|-------------------|
| Overall accept rate | Total accepts / impressions | Drop > 15% month-on-month | Investigate top actions |
| Match rate | Matched IH / Total IH | < 95% | Fix outcome pipeline |
| Top decile lift | Accepts in top 10% propensity / baseline | < 2.0 | Review ADM model quality |
| Calibration error | Avg \|predicted - actual\| per band | > 10% | Recalibrate model |
| Conversion lag | Avg DaysToConvert | > 14 days | Update outcome capture pipeline |
| Revenue per impression | Total revenue / impressions | Drop > 20% | Review value configuration |
| Champion vs Challenger delta | Accept rate difference | Challenger loses by > 5% | Abort Challenger test |

---

## Integration with Other CDH Components

| Component | How It Uses Actuals |
|-----------|---------------------|
| ADM Models | Actuals are the training labels — outcome = accept/reject trains propensity |
| Impact Analyzer | Uses historical Actuals accept rates to project future revenue impact |
| Value Finder | Uses Actuals to identify segments with low conversion despite high value |
| Explainability Extract | Cross-references Actuals with predictor values to audit model decisions |
| Decision Management Reports | Reports KPIs (accept rate, revenue) directly from Actuals Dataset |
