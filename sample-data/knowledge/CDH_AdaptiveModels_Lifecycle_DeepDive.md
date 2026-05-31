# CDH Adaptive Models — Complete Lifecycle and Configuration Deep Dive

## Article Purpose
Covers ADM model creation, predictor configuration, performance monitoring,
retraining triggers, champion/challenger mechanics, and the full data flow
from IH outcome to updated propensity. Includes concrete thresholds, SQL
queries, and decision trees for every model management decision.

---

## ADM Model Creation — Step by Step

### When to Create a New Model

Create a new ADM model whenever:
- A new NBA action is added to the strategy
- An existing action is deployed on a new channel
- A business unit split requires separate model governance
- Compliance requires isolated model tracking per product category

### Creation Procedure

```
CDH > Adaptive Models > New > Adaptive Model

Step 1 — Identity
  Model Name: [ActionName]_[Channel]
  Example: GoldCard_Web, PersonalLoan_Email
  Description: [Business description, owner, date created]

Step 2 — Context
  Issue: [e.g. Growth]
  Group: [e.g. CreditCards]
  Action: [exact action name — case sensitive]
  Channel: [Web | Email | Mobile | CallCentre | SMS | Push]

Step 3 — Model Type
  Initial type: Naive Bayes
  (Switch to Gradient Boost once ResponseCount > 500)

Step 4 — Outcome Definition
  Positive outcome: Outcome IN ('Accepted', 'Converted')
  Outcome field: pxOutcome (maps to IH Outcome field)

Step 5 — Predictors
  (Add predictors — see Predictor Configuration section)

Step 6 — Performance Settings
  Minimum response threshold: 200
  Propensity floor: 0.001
  Propensity ceiling: 0.999
```

---

## Predictor Configuration Deep Dive

### Predictor Types

#### Type 1 — Symbolic (Categorical)
Used for text/category fields. ADM calculates separate weights per category value.

```
Predictor: Customer.Region
Type: Symbolic
Values: North, South, East, West, Scotland, Wales
ADM learns: Customers in Scotland accept Credit Cards at higher rate
```

Risk: High-cardinality symbolic predictors (many unique values) degrade model
performance. Limit symbolic predictors to ≤ 50 unique values. For postcodes
(thousands of values), use a derived binned field instead.

#### Type 2 — Numeric (Continuous)
Used for numeric fields. ADM automatically bins into ranges.

```
Predictor: Customer.CreditScore
Type: Numeric
ADM creates bins: [300-550] [550-650] [650-720] [720-800] [800+]
ADM learns: Higher CreditScore → higher acceptance propensity
```

ADM dynamically adjusts bin boundaries as more data accumulates.

#### Type 3 — Derived (Calculated at runtime)
Calculated by CDH before being passed to ADM. Not stored on customer profile.

```
Derived Predictor: DaysSinceLastProductPurchase
Calculation: TODAY - Customer.LastPurchaseDate
Type: Numeric
Use: Recent purchasers may be less receptive; or more receptive if cross-sell
```

### Recommended Predictor Set by Category

#### Demographic Predictors (stable, always useful)
```
Customer.Age                    → Numeric
Customer.Gender                 → Symbolic (check compliance)
Customer.Region                 → Symbolic
Customer.TenureMonths           → Numeric
Customer.EmploymentStatus       → Symbolic (Employed/Self-employed/Retired/Other)
Customer.MaritalStatus          → Symbolic (where legally permissible)
```

#### Financial Predictors (high signal for credit products)
```
Customer.CreditScore            → Numeric
Customer.AnnualIncome           → Numeric
Customer.MonthlyBalance         → Numeric
Customer.TotalCreditLimit       → Numeric
Customer.CurrentDebt            → Numeric
Customer.DebtToIncomeRatio      → Numeric (derived: Debt/Income)
Customer.MissedPayments12Mo     → Numeric
```

#### Product Holdings (strong cross-sell signals)
```
Customer.HoldsCreditCard        → Symbolic (Yes/No)
Customer.HoldsCurrentAccount    → Symbolic
Customer.HoldsMortgage          → Symbolic
Customer.NumberOfProducts       → Numeric
Customer.PrimaryProductType     → Symbolic
```

#### Behavioural Predictors (from Interaction History aggregates)
```
IH.WebVisits30Days              → Numeric (visits in last 30 days)
IH.EmailOpens30Days             → Numeric
IH.AppLogins30Days              → Numeric
IH.LastChannelUsed              → Symbolic
IH.DaysSinceLastInteraction     → Numeric (derived)
IH.AcceptRate90Days             → Numeric (customer's own historical accept rate)
IH.ImpressionsLastMonth         → Numeric
```

#### Calculated / Derived Signals (high value when available)
```
Customer.RFM_Recency            → Numeric (days since last purchase)
Customer.RFM_Frequency          → Numeric (transactions last 90 days)
Customer.RFM_Monetary           → Numeric (spend last 90 days)
Customer.CLVScore               → Numeric (Customer Lifetime Value model score)
Customer.ChurnProbability       → Numeric (churn model score)
Customer.LifeEventFlag          → Symbolic (NewBaby/NewHome/Retirement/NewJob)
```

### Predictor Performance Monitoring

After 500+ responses, review predictor status in ADM Snapshot:

```
Active:   Predictor is being used and contributing positively to AUC
Inactive: Predictor is not helping — consider removing
Negative: Predictor is reducing AUC — REMOVE immediately
Absent:   Data not reaching model — check data flow mapping
Symbolic: Too many unique values — reduce cardinality
```

#### Deciding When to Remove a Predictor

Remove predictor when:
- Status = Negative for two consecutive monthly reviews
- Status = Inactive AND it is slowing model computation
- Status = Absent for > 14 days (data pipeline broken)
- Predictor is sensitive attribute not approved by compliance
- Missing value rate > 50% (predictor not available for half of customers)

---

## Model Type Transition: Naive Bayes to Gradient Boost

### Why This Matters

Naive Bayes is fast to update and works with minimal data. Gradient Boost is
more accurate but requires periodic batch retraining and more data.

### Transition Decision Tree

```
ResponseCount < 200
  → Stay on Naive Bayes; model not yet reliable

ResponseCount 200–500
  → Naive Bayes; begin evaluating AUC weekly

ResponseCount > 500 AND AUC(NaiveBayes) < 0.65
  → Switch to Gradient Boost; batch retrain weekly

ResponseCount > 500 AND AUC(NaiveBayes) > 0.65
  → Stay on Naive Bayes if acceptable; switch if want higher ceiling

ResponseCount > 2,000
  → Always use Gradient Boost for mature model
```

### Transition Procedure

```
CDH > Adaptive Models > [Model Name] > Configuration > Model Type
Change: Naive Bayes → Gradient Boost
Note: Transition creates a new model; historical Naive Bayes weights discarded
      Gradient Boost retrains from historical IH data immediately
      Expect 24–48h before Gradient Boost AUC stabilises
```

### Gradient Boost Retraining Schedule

```
CDH > Adaptive Models > [Model Name] > Training Schedule
Recommended settings:
  Training frequency: Daily (for models with > 100 new responses/day)
  Training frequency: Weekly (for models with < 100 new responses/day)
  Training window: Last 180 days of IH data
  Minimum responses required: 500
  Training time: Off-peak hours (2am–5am)
```

---

## AUC Deep Dive — What It Measures and Why It Matters

### AUC Definition

AUC (Area Under ROC Curve) measures the model's ability to rank customers
correctly — placing likely acceptors above likely rejectors.

```
AUC = 0.50 → Random ranking (coin flip)
AUC = 0.70 → Model ranks correctly 70% of the time
AUC = 0.80 → Model ranks correctly 80% of the time
AUC = 1.00 → Perfect ranking (never achieved in practice)
```

### What AUC Does NOT Measure

AUC does NOT measure:
- Calibration (whether propensity = 0.4 means 40% acceptance)
- Overall acceptance rate
- Revenue generated
- Model fairness

AUC only measures RANKING quality. A model can have AUC = 0.85 and still
have poorly calibrated propensity scores.

### AUC Thresholds for Action

| AUC | Threshold | Required Action | Timeline |
|-----|-----------|----------------|---------|
| > 0.85 | Exceptional | Verify not overfitting; check on held-out data | Immediate check |
| 0.75–0.85 | Excellent | No action; monitor monthly | Monthly |
| 0.65–0.75 | Good | Monitor; consider adding predictors | Quarterly |
| 0.60–0.65 | Fair | Add predictors; increase data volume | Monthly review |
| 0.55–0.60 | Poor | Reset model OR add predictors immediately | Within 2 weeks |
| < 0.55 | Failing | Reset model; review data pipeline | Immediate |

### AUC Variance — When Thresholds Shift

For models with fewer than 1,000 responses, AUC fluctuates significantly.
Apply these adjusted thresholds:

| Response Count | Reliable AUC Range | Note |
|---|---|---|
| < 200 | ±0.15 variance | AUC unreliable; ignore threshold |
| 200–500 | ±0.08 variance | Use 0.55 as "poor" threshold |
| 500–2,000 | ±0.04 variance | Standard thresholds apply |
| > 2,000 | ±0.02 variance | High confidence in AUC readings |

---

## Model Drift Detection

### Definition
Model drift occurs when the relationship between predictor values and customer
behaviour changes over time, causing previously accurate predictions to become
less reliable.

### Causes of Model Drift
1. **Covariate drift:** Customer population characteristics change
   (e.g. new customer acquisition segment changes income distribution)
2. **Concept drift:** Customer behaviour changes (e.g. economic conditions
   change propensity to accept credit products)
3. **Data drift:** A predictor data feed changes (e.g. CRM field redefined)

### Detecting Drift

Monthly drift check — compare current snapshot to 90-day-ago snapshot:

```sql
-- Model drift detection query
SELECT
    a.ModelName,
    a.AUC AS CurrentAUC,
    b.AUC AS AUC_90DaysAgo,
    a.AUC - b.AUC AS AUC_Delta,
    a.Positivity AS CurrentPositivity,
    b.Positivity AS Positivity_90DaysAgo,
    a.Positivity - b.Positivity AS Positivity_Delta,
    CASE
        WHEN a.AUC - b.AUC < -0.05 THEN 'DRIFT_ALERT'
        WHEN a.AUC - b.AUC < -0.03 THEN 'DRIFT_WARNING'
        ELSE 'STABLE'
    END AS DriftStatus
FROM ADMSnapshot a
JOIN ADMSnapshot b ON a.ModelName = b.ModelName
WHERE a.SnapshotDate = [latest_date]
  AND b.SnapshotDate = [90_days_ago_date]
ORDER BY AUC_Delta ASC;
```

### Response to Drift

| Drift Type | AUC Drop | Response |
|-----------|---------|---------|
| Minor | 0.02–0.03 | Monitor more frequently (weekly) |
| Moderate | 0.03–0.05 | Add new predictors; increase training window |
| Major | > 0.05 | Force retrain; investigate data pipeline |
| Severe | > 0.10 in 2 weeks | Emergency: disable model, use fixed propensity |

---

## Champion / Challenger — Complete Mechanics

### Setup

```
CDH > Adaptive Models > [Model Name] > Champion/Challenger

Champion: Current production model
  Traffic: 90%
  
Challenger: New model variant being tested
  Traffic: 10%
  Configuration: [different predictor set / model type / training window]
```

### How Traffic Split Works

CDH assigns each customer to Champion or Challenger group at session start:
- Assignment is hash-based on CustomerID → deterministic per customer
- A customer always sees Champion OR Challenger (not mixed)
- Group assignment stored in `ExperimentGroup` field in IH

### Measuring Champion vs Challenger

```sql
SELECT
    ExperimentGroup,
    COUNT(*) AS Impressions,
    SUM(CASE WHEN ActualLabel = 1 THEN 1 ELSE 0 END) AS Accepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS AcceptRate,
    AVG(Propensity) AS AvgPropensity,
    AVG(CASE WHEN ActualLabel = 1 THEN ConversionValue ELSE 0 END)
        AS AvgRevenuePerCustomer
FROM ActualsDataset
WHERE ModelName = 'GoldCard_Web'
    AND DecisionDate >= DATEADD(day, -30, GETDATE())
GROUP BY ExperimentGroup;
```

Expected output:
```
ExperimentGroup | Impressions | Accepts | AcceptRate | AvgPropensity | Revenue
Champion        | 9,012       | 742     | 8.23%      | 0.38          | £6.12
Challenger      | 1,001       | 92      | 9.19%      | 0.41          | £7.34
```

Challenger wins: +0.96% absolute accept rate, +£1.22 revenue per customer.

### Promotion Decision Criteria

Promote Challenger to Champion when ALL of these are met:

```
1. Minimum exposure: Both groups have ≥ 1,000 impressions
2. Minimum duration: At least 14 days have elapsed
3. Accept rate improvement: Challenger AcceptRate > Champion AcceptRate
4. Statistical significance: p-value < 0.05 (two-proportion z-test)
5. Revenue improvement: Challenger Revenue/Customer ≥ Champion (no regression)
6. No adverse outcomes: No increase in complaint rate or cancellations
```

### Promotion Procedure

```
CDH > Adaptive Models > [Model Name] > Champion/Challenger
Click: "Promote Challenger to Champion"
Confirmation: All traffic shifts to Challenger model
Archive: Champion model preserved for 90 days (can roll back)
```

### When NOT to Promote

Do not promote if:
- Challenger shows higher AUC but LOWER accept rate (ranking ≠ conversion)
- Duration < 14 days (weekend/weekday effects not captured)
- Sample < 1,000 per group (high variance; result may be noise)
- External factor (e.g. bank holiday) confounds results

---

## Model Performance SQL Reference

### Daily ADM Health Query

```sql
-- Run daily to monitor all active models
SELECT
    ModelName,
    Channel,
    AUC,
    ResponseCount,
    PositiveResponses,
    NegativeResponses,
    CAST(PositiveResponses AS FLOAT) / NULLIF(ResponseCount, 0) AS Positivity,
    ActivePredictors,
    SnapshotTime,
    CASE
        WHEN AUC < 0.60 THEN '🔴 CRITICAL'
        WHEN AUC < 0.70 THEN '🟡 REVIEW'
        ELSE '🟢 OK'
    END AS HealthStatus,
    CASE
        WHEN ResponseCount < 200 THEN '⚠ LOW DATA'
        WHEN ResponseCount < 500 THEN '📈 GROWING'
        ELSE '✅ MATURE'
    END AS MaturityStatus
FROM ADMSnapshot
WHERE SnapshotDate = [today]
ORDER BY AUC ASC;
```

### Model Trend Query (30-day rolling)

```sql
SELECT
    ModelName,
    SnapshotDate,
    AUC,
    ResponseCount,
    Positivity,
    AUC - LAG(AUC, 7) OVER (PARTITION BY ModelName ORDER BY SnapshotDate)
        AS AUC_WeekOnWeek
FROM ADMSnapshot
WHERE SnapshotDate >= DATEADD(day, -30, GETDATE())
ORDER BY ModelName, SnapshotDate;
```

### Low-Performing Model Alert Query

```sql
SELECT
    ModelName,
    Channel,
    AUC,
    ResponseCount,
    Positivity,
    DATEDIFF(day, ModelCreatedDate, GETDATE()) AS ModelAgeDays
FROM ADMSnapshot
WHERE SnapshotDate = [today]
  AND (
    AUC < 0.60
    OR (ResponseCount < 200 AND ModelAgeDays > 30)
    OR Positivity = 0
    OR ActivePredictors = 0
  )
ORDER BY AUC ASC;
```
