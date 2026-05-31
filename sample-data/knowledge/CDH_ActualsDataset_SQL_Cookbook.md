# CDH Actuals Dataset — Construction, Lift Analysis, and SQL Cookbook

## Article Purpose
Complete technical reference for building, validating, and analysing the
Actuals Dataset. Includes SQL queries for every standard analysis, lift
calculation methodology, calibration checks, and pipeline quality procedures.

---

## Building the Actuals Dataset — Three Methods

### Method 1: Real-Time API (Best Practice)

When a customer converts, the downstream system calls CDH immediately:

```http
POST /prweb/api/v1/outcomes
Content-Type: application/json
Authorization: Bearer [token]

{
  "interactionId": "IH-20240115-00123456",
  "subjectId": "C0012345",
  "actionName": "Gold_Card_Offer",
  "outcome": "Accepted",
  "outcomeTime": "2024-01-15T14:32:45Z",
  "conversionValue": 0,
  "customProperties": {
    "applicationId": "APP-2024-99887",
    "productCode": "GOLD-CC-ELITE"
  }
}
```

CDH updates IH immediately. ADM model learns instantly.
Recommended for: Web, Mobile, CallCentre channels.

### Method 2: Daily Batch Upload

For CRM systems without real-time API capability:

```
File format: CSV, UTF-8, no BOM
Delimiter: comma
Filename: Actuals_YYYYMMDD.csv

Required columns:
  InteractionID     — matches IH pxInteractionID exactly
  Outcome           — Accepted | Rejected | Converted | NoResponse
  OutcomeDate       — ISO 8601: YYYY-MM-DDTHH:MM:SSZ
  ConversionValue   — numeric, 0 if no revenue event

Optional columns:
  CustomerID        — for validation against IH
  ApplicationRef    — downstream system reference
  ProductCode       — product activated

Upload path: CDH > Data Management > Outcome Upload > Batch
Schedule: Daily at 3am (after CRM overnight processing)
```

### Method 3: SQL Join for Analytics (Offline)

For analysis and reporting, construct the Actuals Dataset by joining IH
with CRM outcome tables:

```sql
-- STANDARD ACTUALS DATASET CONSTRUCTION
-- Run daily; store result as ActualsDataset_[date]

WITH
IH_Base AS (
    SELECT
        pxInteractionID      AS InteractionID,
        SubjectID            AS CustomerID,
        ActionName,
        Issue,
        [Group],
        Channel,
        Direction,
        Propensity           AS ModelPropensity,
        Priority             AS ArbitrationPriority,
        Weight               AS ActionWeight,
        [Value]              AS ActionValue,
        Rank                 AS ArbitrationRank,
        ExperimentGroup,
        pxDecisionTime       AS DecisionTime,
        Treatment
    FROM InteractionHistory
    WHERE Outcome = 'Impression'          -- Only served interactions
      AND pxDecisionTime >= DATEADD(day, -90, GETDATE())
),

CRM_Outcomes AS (
    SELECT
        InteractionRef        AS InteractionID,
        OutcomeType           AS ActualOutcome,
        OutcomeDate,
        RevenueAmount         AS ConversionValue,
        ApplicationStatus
    FROM CRM.CustomerApplications
    WHERE ProcessedDate >= DATEADD(day, -90, GETDATE())

    UNION ALL

    SELECT
        IH_Reference,
        'Rejected',
        RejectionDate,
        0,
        'Declined'
    FROM CRM.DeclinedApplications
    WHERE RejectionDate >= DATEADD(day, -90, GETDATE())
)

SELECT
    ih.*,
    crm.ActualOutcome,
    crm.OutcomeDate,
    crm.ConversionValue,
    CASE
        WHEN crm.ActualOutcome IN ('Accepted', 'Converted', 'Activated') THEN 1
        WHEN crm.ActualOutcome IN ('Rejected', 'Declined') THEN 0
        WHEN crm.InteractionID IS NULL THEN 0     -- No response = negative
        ELSE 0
    END AS ActualLabel,
    CASE
        WHEN crm.InteractionID IS NOT NULL THEN 1
        ELSE 0
    END AS HasOutcome,
    DATEDIFF(hour, ih.DecisionTime, crm.OutcomeDate) AS HoursToOutcome
FROM IH_Base ih
LEFT JOIN CRM_Outcomes crm ON ih.InteractionID = crm.InteractionID
```

---

## Data Quality Validation Queries

### Query 1: Match Rate by Channel

```sql
-- Target: > 95% match rate per channel
SELECT
    Channel,
    COUNT(*) AS TotalImpressions,
    SUM(HasOutcome) AS MatchedOutcomes,
    CAST(SUM(HasOutcome) AS FLOAT) / COUNT(*) AS MatchRate,
    CASE
        WHEN CAST(SUM(HasOutcome) AS FLOAT) / COUNT(*) >= 0.95 THEN '✅ OK'
        WHEN CAST(SUM(HasOutcome) AS FLOAT) / COUNT(*) >= 0.90 THEN '⚠ Review'
        ELSE '🔴 Fix needed'
    END AS Status
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY Channel
ORDER BY MatchRate ASC;
```

Expected output:
```
Channel      | Total  | Matched | MatchRate | Status
─────────────|────────|─────────|───────────|─────────
Web          | 45,231 | 44,778  | 99.0%     | ✅ OK
Mobile       | 23,118 | 22,886  | 99.0%     | ✅ OK
CallCentre   | 8,231  | 8,188   | 99.5%     | ✅ OK
Email        | 89,445 | 87,256  | 97.6%     | ✅ OK
SMS          | 12,334 | 10,222  | 82.9%     | 🔴 Fix needed
```

SMS match rate of 82.9% indicates the SMS outcome system is not feeding back
correctly. Investigate SMS platform integration.

### Query 2: Outcome Lag Distribution

```sql
-- Check whether outcomes are arriving in a reasonable time window
SELECT
    ActionName,
    Channel,
    AVG(HoursToOutcome) AS AvgHoursToOutcome,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY HoursToOutcome) AS MedianHours,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY HoursToOutcome) AS P95Hours,
    MAX(HoursToOutcome) AS MaxHours
FROM ActualsDataset
WHERE HasOutcome = 1
    AND ActualLabel = 1
    AND DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY ActionName, Channel
ORDER BY AvgHoursToOutcome DESC;
```

### Query 3: Outcome Distribution Check

```sql
-- Flag unusual outcome distributions
SELECT
    ActionName,
    Channel,
    COUNT(*) AS TotalImpressions,
    SUM(CASE WHEN ActualOutcome = 'Accepted' THEN 1 ELSE 0 END) AS Accepted,
    SUM(CASE WHEN ActualOutcome = 'Rejected' THEN 1 ELSE 0 END) AS Rejected,
    SUM(CASE WHEN ActualOutcome IS NULL THEN 1 ELSE 0 END) AS NoOutcome,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS AcceptRate
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY ActionName, Channel
HAVING COUNT(*) > 100
ORDER BY AcceptRate DESC;
```

---

## Lift Analysis — Complete SQL Implementation

### Step 1: Calculate Overall Baseline Accept Rate

```sql
-- Baseline: overall accept rate for all actions combined
SELECT
    COUNT(*) AS TotalImpressions,
    SUM(ActualLabel) AS TotalAccepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS BaselineAcceptRate
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(day, -90, GETDATE())
  AND HasOutcome = 1;
-- Result: BaselineAcceptRate = 0.0435 (4.35%)
```

### Step 2: Lift by Propensity Decile

```sql
-- Calculate lift curve — the key ADM model quality assessment
WITH Deciled AS (
    SELECT
        ActualLabel,
        ModelPropensity,
        NTILE(10) OVER (ORDER BY ModelPropensity DESC) AS PropensityDecile
    FROM ActualsDataset
    WHERE DecisionTime >= DATEADD(day, -90, GETDATE())
      AND HasOutcome = 1
      AND ActionName = 'Gold_Card_Offer'    -- Filter to one action
),
Baseline AS (
    SELECT CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS BaseRate
    FROM ActualsDataset
    WHERE HasOutcome = 1
      AND ActionName = 'Gold_Card_Offer'
)
SELECT
    d.PropensityDecile,
    COUNT(*) AS Impressions,
    SUM(d.ActualLabel) AS Accepts,
    MIN(d.ModelPropensity) AS PropensityRangeMin,
    MAX(d.ModelPropensity) AS PropensityRangeMax,
    AVG(d.ModelPropensity) AS AvgPropensity,
    CAST(SUM(d.ActualLabel) AS FLOAT) / COUNT(*) AS ActualAcceptRate,
    CAST(SUM(d.ActualLabel) AS FLOAT) / COUNT(*) / b.BaseRate AS Lift,
    SUM(SUM(d.ActualLabel)) OVER (ORDER BY d.PropensityDecile)
        / NULLIF(SUM(SUM(d.ActualLabel)) OVER (), 0) AS CumulativeGain
FROM Deciled d, Baseline b
GROUP BY d.PropensityDecile, b.BaseRate
ORDER BY d.PropensityDecile;
```

Expected output (good model, AUC ~0.75):
```
Decile | Count | Accepts | PropRange      | AvgProp | AcceptRate | Lift  | CumGain
───────|──────|─────────|────────────────|─────────|────────────|───────|────────
1      | 1,234 | 321     | 0.68–0.98      | 0.74    | 26.0%      | 5.98  | 16.1%
2      | 1,234 | 247     | 0.52–0.68      | 0.59    | 20.0%      | 4.60  | 28.5%
3      | 1,234 | 186     | 0.42–0.52      | 0.47    | 15.1%      | 3.47  | 37.8%
4      | 1,234 | 143     | 0.33–0.42      | 0.37    | 11.6%      | 2.67  | 45.0%
5      | 1,234 | 109     | 0.26–0.33      | 0.29    | 8.8%       | 2.02  | 50.5%
6      | 1,234 | 83      | 0.21–0.26      | 0.23    | 6.7%       | 1.54  | 54.7%
7      | 1,234 | 61      | 0.16–0.21      | 0.18    | 4.9%       | 1.13  | 57.7%
8      | 1,234 | 38      | 0.11–0.16      | 0.14    | 3.1%       | 0.71  | 59.6%
9      | 1,234 | 22      | 0.06–0.11      | 0.09    | 1.8%       | 0.41  | 60.7%
10     | 1,234 | 12      | 0.00–0.06      | 0.04    | 1.0%       | 0.23  | 61.3%
```

**Reading this table:**
- Top decile (Decile 1) has 5.98× lift — targeting the top 10% by propensity
  gives 6× better results than random targeting
- Cumulative Gain of 60.7% at Decile 9 means: top 90% of propensity captures
  60.7% of all conversions
- Decile 10 (lowest propensity) should almost never be targeted

---

## Model Calibration Analysis

### What Good Calibration Looks Like

A well-calibrated model: predicted propensity ≈ actual accept rate within each band.

```sql
-- Calibration check
SELECT
    FLOOR(ModelPropensity * 10) / 10 AS PropensityBand,
    COUNT(*) AS CustomerCount,
    AVG(ModelPropensity) AS AvgPredictedPropensity,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS ActualAcceptRate,
    AVG(ModelPropensity) - CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*)
        AS CalibrationError,
    CASE
        WHEN ABS(AVG(ModelPropensity) - CAST(SUM(ActualLabel) AS FLOAT)/COUNT(*))
             < 0.05 THEN '✅ Calibrated'
        WHEN ABS(AVG(ModelPropensity) - CAST(SUM(ActualLabel) AS FLOAT)/COUNT(*))
             < 0.10 THEN '⚠ Slight drift'
        ELSE '🔴 Poor calibration'
    END AS CalibrationStatus
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(day, -90, GETDATE())
    AND HasOutcome = 1
    AND ActionName = 'Gold_Card_Offer'
    AND CustomerCount > 50    -- only bands with enough data
GROUP BY FLOOR(ModelPropensity * 10) / 10
ORDER BY PropensityBand;
```

Expected output (well-calibrated model):
```
PropBand | Count | AvgPred | ActualAR | CalibError | Status
─────────|───────|─────────|──────────|────────────|───────────────
0.0–0.1  | 1,243 | 0.05    | 0.032    | +0.018     | ✅ Calibrated
0.1–0.2  | 2,112 | 0.15    | 0.142    | +0.008     | ✅ Calibrated
0.2–0.3  | 3,456 | 0.25    | 0.248    | +0.002     | ✅ Calibrated
0.3–0.4  | 2,891 | 0.35    | 0.359    | -0.009     | ✅ Calibrated
0.4–0.5  | 2,234 | 0.45    | 0.421    | +0.029     | ✅ Calibrated
0.5–0.6  | 1,456 | 0.55    | 0.509    | +0.041     | ✅ Calibrated
0.6–0.7  | 889   | 0.64    | 0.591    | +0.049     | ✅ Calibrated
0.7+     | 445   | 0.76    | 0.712    | +0.048     | ✅ Calibrated
```

---

## Revenue Attribution Queries

### Total Revenue by Action and Channel

```sql
SELECT
    ActionName,
    Channel,
    COUNT(*) AS Impressions,
    SUM(ActualLabel) AS Accepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS AcceptRate,
    SUM(CASE WHEN ActualLabel = 1 THEN ConversionValue ELSE 0 END)
        AS TotalRevenue,
    AVG(CASE WHEN ActualLabel = 1 THEN ConversionValue ELSE 0 END)
        AS RevenuePerImpression,
    AVG(CASE WHEN ActualLabel = 1 AND ConversionValue > 0
             THEN ConversionValue END) AS RevenuePerAccept
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(month, -1, GETDATE())
GROUP BY ActionName, Channel
ORDER BY TotalRevenue DESC;
```

### Revenue Attributable to CDH NBA Strategy

```sql
-- Total revenue that CDH NBA strategy generated this month
SELECT
    SUM(ConversionValue) AS TotalCDHRevenue,
    COUNT(*) AS TotalImpressions,
    SUM(ActualLabel) AS TotalAccepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS OverallAcceptRate,
    SUM(ConversionValue) / COUNT(*) AS RevenuePerImpression,
    SUM(ConversionValue) / NULLIF(SUM(ActualLabel), 0) AS RevenuePerAccept
FROM ActualsDataset
WHERE DecisionTime >= DATEADD(month, -1, GETDATE())
  AND ActualLabel = 1;
```

### Champion vs Challenger Revenue Comparison

```sql
SELECT
    ExperimentGroup,
    COUNT(*) AS Impressions,
    SUM(ActualLabel) AS Accepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS AcceptRate,
    SUM(ConversionValue) AS TotalRevenue,
    SUM(ConversionValue) / COUNT(*) AS RevenuePerImpression,
    AVG(ModelPropensity) AS AvgPropensity,
    -- Statistical test: binomial proportion z-score
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*)
        / SQRT(CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*)
               * (1 - CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*))
               / COUNT(*)) AS ZScore
FROM ActualsDataset
WHERE ExperimentGroup IN ('Champion', 'Challenger')
  AND DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY ExperimentGroup;
```

---

## Outcome Lag Correction

When analysing recent data (last 7–14 days), apply lag correction because
some conversions have not yet been captured:

```sql
-- Lag-corrected accept rate
-- Step 1: Calculate observed accept rate for period with complete data (30+ days ago)
-- Step 2: Compare with same period's accept rate at 7 days (partial) to get correction factor
-- Step 3: Apply correction factor to recent period

WITH CompletePeriod AS (
    SELECT CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS CompleteAR
    FROM ActualsDataset
    WHERE DecisionTime BETWEEN DATEADD(day, -60, GETDATE())
                           AND DATEADD(day, -31, GETDATE())
),
PartialPeriod AS (
    SELECT CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS PartialAR
    FROM ActualsDataset
    WHERE DecisionTime BETWEEN DATEADD(day, -60, GETDATE())
                           AND DATEADD(day, -31, GETDATE())
      AND DATEDIFF(day, DecisionTime, OutcomeDate) <= 7  -- Only 7-day outcomes
)
SELECT
    recent.ActionName,
    recent.Channel,
    recent.ObservedAcceptRate,
    recent.ObservedAcceptRate * (cp.CompleteAR / pp.PartialAR)
        AS LagCorrectedAcceptRate
FROM (
    SELECT ActionName, Channel,
           CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS ObservedAcceptRate
    FROM ActualsDataset
    WHERE DecisionTime >= DATEADD(day, -7, GETDATE())
    GROUP BY ActionName, Channel
) recent
CROSS JOIN CompletePeriod cp
CROSS JOIN PartialPeriod pp;
```

---

## Actuals Dataset Monthly Review — Full Checklist

```
1. DATA QUALITY
   □ Match rate > 95% per channel? [run Query 1]
   □ Outcome lag < 24h for real-time channels?
   □ No duplicate InteractionIDs?
   □ Propensity values in [0.001, 1.0]?
   □ ConversionValue >= 0 for all records?

2. MODEL PERFORMANCE
   □ Top decile lift > 3.0 for each action? [run lift analysis]
   □ Calibration error < 10% per band? [run calibration query]
   □ AUC consistent with ADM Snapshot values?

3. BUSINESS PERFORMANCE
   □ Accept rate change < ±15% vs previous month?
   □ Revenue per impression maintained or improved?
   □ No single action > 40% of total revenue?

4. CHAMPION/CHALLENGER
   □ Any C/C tests with > 1,000 impressions per group?
   □ C/C tests with > 14 days duration?
   □ Promotion decision documented for any concluded tests?

5. FAIRNESS
   □ Accept rate disparity < 20% across demographic groups?
   □ No demographic group with lift < 0.8 (underserved by ADM)?
```
