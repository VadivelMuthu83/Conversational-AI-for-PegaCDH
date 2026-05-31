# CDH Data Flow Architecture and Integration Guide

## Article Purpose
Describes all data flows into and out of Pega CDH, integration
patterns for CRM/billing/analytics, and the complete data pipeline
from customer interaction to ADM model update.

---

## Complete CDH Data Flow Diagram

```
UPSTREAM DATA SOURCES
═══════════════════════════════════════════════════════════════════
CRM System           → Customer profile (age, income, products, status)
Billing/Core Banking → Balance, payment history, credit data
Web Analytics        → Page views, session signals, click behaviour
Mobile App           → App usage, feature adoption, push preferences
Call Centre Platform → Call reason, call history, agent context
Credit Bureau        → Credit score, external debt, defaults
Marketing Platform   → Campaign history, opt-outs, channel preferences
Fraud System         → Risk flags, blocked customers
Churn Model          → Predicted churn probability scores
CLV Model            → Customer lifetime value scores
═══════════════════════════════════════════════════════════════════
                              ↓
                    ┌─────────────────┐
                    │   PEGA CDH      │
                    │   CORE ENGINE   │
                    │                 │
                    │  ┌───────────┐  │
                    │  │ Engagement│  │
                    │  │  Policy   │  │
                    │  └─────┬─────┘  │
                    │        ↓        │
                    │  ┌───────────┐  │
                    │  │    ADM    │  │
                    │  │  Models   │  │
                    │  └─────┬─────┘  │
                    │        ↓        │
                    │  ┌───────────┐  │
                    │  │Arbitration│  │
                    │  └─────┬─────┘  │
                    └────────┼────────┘
                             ↓
DOWNSTREAM DELIVERY CHANNELS
═══════════════════════════════════════════════════════════════════
Web Portal           ← Real-time NBA action (< 200ms)
Mobile App           ← Real-time NBA action (< 200ms)
Call Centre Desktop  ← Real-time NBA action (< 200ms)
Email Platform       ← Batch NBA decisions (nightly)
SMS Platform         ← Batch NBA decisions (hourly)
Push Platform        ← Triggered NBA decisions
Branch Terminal      ← Real-time NBA action
═══════════════════════════════════════════════════════════════════
                             ↓
OUTCOME CAPTURE
═══════════════════════════════════════════════════════════════════
CRM                  → Application outcomes (Accepted/Rejected)
Billing              → Product activation (Converted)
Web Analytics        → Click events (Clicked/NoResponse)
Mobile Analytics     → App conversion events
═══════════════════════════════════════════════════════════════════
                             ↓
           ┌─────────────────────────────┐
           │  INTERACTION HISTORY (IH)   │
           │  Central event log          │
           │  All decisions + outcomes   │
           └─────────────────────────────┘
                             ↓
ANALYTICS AND FEEDBACK LOOP
═══════════════════════════════════════════════════════════════════
ADM Models           ← IH outcomes (continuous learning)
Value Finder         ← IH engagement scores
Impact Analyzer      ← IH historical decisions
Actuals Dataset      ← IH + CRM outcomes joined
Explainability       ← IH + predictor values at decision time
BI / Reporting       ← IH exports to data warehouse
```

---

## Customer Data Integration

### Required Customer Properties

These fields must be available in CDH for effective arbitration:

| Property | Source System | Update Frequency | Priority |
|----------|-------------|-----------------|---------|
| Age | CRM | Annual | Critical |
| AccountStatus | CRM | Real-time | Critical |
| CreditScore | Credit Bureau | Monthly | Critical |
| AnnualIncome | CRM | Annual | Critical |
| TenureMonths | CRM | Monthly (calculated) | Critical |
| TotalProducts | CRM | Daily | High |
| HoldsCreditCard | CRM | Daily | High |
| HoldsMortgage | CRM | Daily | High |
| VulnerabilityFlag | CRM | Real-time on change | Critical (compliance) |
| MarketingConsent | Preference Centre | Real-time on change | Critical (compliance) |
| ChurnProbability | Churn Model | Weekly | High |
| CLVScore | CLV Model | Monthly | Medium |
| LifeEventFlag | CRM / Events | Real-time | High |
| MissedPayments3Mo | Billing | Monthly | High |
| MissedPayments12Mo | Billing | Monthly | High |

### Data Integration Methods

**Method 1: Real-Time API (Preferred)**
```
CDH pulls customer data at decision time via REST API
  GET /api/customer/{customerId}
  Response: {age, creditScore, accountStatus, products, ...}
  Latency: Must be < 50ms to meet 200ms total decision target
  Cache: Properties cached in CDH for 15–60 minutes per property
```

**Method 2: Nightly Batch Load**
```
CRM exports customer file at 2am
CDH loads via ETL job
Data is available by 5am
Properties current as of previous day's end-of-business
Suitable for: Slowly-changing properties (age, income, tenure)
NOT suitable for: Real-time status changes (account blocks, fraud flags)
```

**Method 3: Event-Driven Update**
```
CRM publishes event to Kafka when property changes
CDH consumes Kafka topic and updates customer property
Event payload: {customerId, property, newValue, timestamp}
Suitable for: Status changes, compliance flags, consent updates
Latency: < 5 seconds from CRM change to CDH update
```

### Recommended Integration Pattern by Property Type

| Property Type | Example | Recommended Method |
|-------------|---------|-------------------|
| Static/slow-changing | Age, Region | Nightly batch |
| Fast-changing operational | AccountStatus, Balance | Real-time API |
| Compliance-critical | VulnerabilityFlag, Consent | Event-driven |
| Model scores | CLV, ChurnPropensity | Weekly batch |
| Session signals | PageViews, AppLogins | Real-time (in-session) |

---

## Interaction History Integration

### IH Write Path (CDH → IH)

CDH writes an IH record immediately when a decision is made:

```
CDH Decision Engine
    ↓ Decision made in < 200ms
IH Write (async, does not block decision response)
    ↓
IH Record:
  pxInteractionID: auto-generated UUID
  SubjectID: CustomerID from session
  ActionName: selected action
  Channel: from interaction context
  Propensity: from ADM model
  Priority: calculated priority score
  Outcome: "Impression" (initial state)
  pxDecisionTime: server timestamp
    ↓
IH Data Store (Cassandra or similar columnar store)
    ↓
Available for query within < 5 seconds
```

### IH Read Path (IH → CDH Analytics)

```
IH Data Store
    ↓
IH Export Service (nightly at 1am)
    ↓
CSV / JSON export files
    ↓
Data Warehouse (Snowflake, BigQuery, Azure Synapse)
    ↓
Downstream systems:
  - ADM Snapshot generation
  - Actuals Dataset construction
  - Value Finder input
  - Impact Analyzer simulation data
  - BI/Reporting tools
  - Regulatory audit archive
```

### IH Retention Architecture

```
Operational IH (CDH active store):
  Retention: 90 days
  Access: Real-time, low latency
  Use: ADM training, contact policy checks, real-time personalisation

Archive IH (data warehouse):
  Retention: 5–7 years (regulatory requirement)
  Access: Batch query, high latency acceptable
  Use: Regulatory audit, historical analysis, year-on-year comparison

Cold Archive (object storage):
  Retention: 10+ years
  Access: Rare, restore needed
  Use: Legal discovery, regulatory investigation
```

---

## ADM Data Flow

### Predictor Data Flow to ADM

```
Customer Profile (CRM)
    ↓ Property mapping
CDH Customer Object (real-time in-memory)
    ↓ Predictor extraction
ADM Predictor Values for this customer
    ↓ Model inference
Propensity Score [0.001, 1.0]
    ↓ Priority formula
Arbitration result
```

### ADM Training Data Flow (Online Learning)

```
IH record: Outcome = "Impression"
    ↓ Customer responds
Outcome system: Accepted / Rejected
    ↓ Outcome written to IH (real-time or batch)
IH record updated: Outcome = "Accepted"
    ↓ ADM model update trigger
ADM reads:
  - Customer predictor values at decision time
  - Outcome label (1 = accepted, 0 = rejected)
    ↓ Online model update (Naive Bayes) or batch retraining (Gradient Boost)
Updated model ready for next prediction
```

### ADM Predictor Mapping

Each IH outcome maps to predictor values for training:

```sql
-- Predictors used to train ADM Gold_Card model
-- Stored at decision time in IH or reconstructed at training time

SELECT
    ih.pxInteractionID,
    ih.ActualLabel,          -- Training label
    cp.Age,                  -- Predictor 1
    cp.CreditScore,          -- Predictor 2
    cp.TenureMonths,         -- Predictor 3
    cp.AnnualIncome,         -- Predictor 4
    cp.HoldsCreditCard,      -- Predictor 5
    cp.MissedPayments3Mo,    -- Predictor 6
    ih.WebVisits30d,         -- Predictor 7 (from IH aggregates)
    ih.LastChannelUsed       -- Predictor 8 (from IH)
FROM InteractionHistory ih
JOIN CustomerProfile cp ON ih.SubjectID = cp.CustomerID
WHERE ih.ActionName = 'Gold_Card_Offer'
  AND ih.Channel = 'Web'
  AND ih.Outcome != 'Impression'    -- Only labelled outcomes
  AND ih.pxDecisionTime >= DATEADD(day, -180, GETDATE())
```

---

## Outcome Capture Integration

### Integration by Channel

| Channel | Outcome System | Capture Method | Typical Lag |
|---------|--------------|----------------|------------|
| Web | Web Analytics / CRM | Real-time API callback | < 1 hour |
| Mobile | Mobile Analytics | Real-time event | < 1 hour |
| Email | Email Platform | Click/open webhook | 0–7 days |
| SMS | SMS Platform | Click tracking | 0–48 hours |
| CallCentre | Agent CRM | Agent records outcome | During call |
| Branch | Branch CRM | Teller records outcome | Same day |
| Print | CRM | Manual entry / QR code | 7–30 days |

### Outcome API Integration (Reference)

```python
# Example: E-commerce platform calling CDH when customer purchases
import requests

def record_cdh_outcome(interaction_id, outcome, revenue=0):
    """
    Call CDH Outcome API when customer converts.
    Call this from your checkout confirmation page, CRM workflow,
    or billing system activation event.
    """
    payload = {
        "interactionId": interaction_id,
        "outcome": outcome,           # "Accepted" | "Rejected" | "Converted"
        "outcomeTime": datetime.utcnow().isoformat() + "Z",
        "conversionValue": revenue    # £ value of the conversion, 0 if unknown
    }

    response = requests.post(
        url="https://cdh.yourdomain.com/prweb/api/v1/outcomes",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CDH_API_TOKEN}"
        },
        timeout=5  # Don't let CDH call slow down your checkout
    )

    if response.status_code != 200:
        # Log failure — don't fail checkout for CDH error
        logger.warning(f"CDH outcome API failed: {response.status_code}")
```

---

## Data Quality Monitoring

### Daily Pipeline Health Checks

```sql
-- 1. IH write rate (should be stable)
SELECT
    CAST(pxDecisionTime AS DATE) AS DecisionDate,
    COUNT(*) AS IHRecords,
    COUNT(*) - LAG(COUNT(*), 1) OVER (ORDER BY CAST(pxDecisionTime AS DATE))
        AS DailyChange
FROM InteractionHistory
WHERE pxDecisionTime >= DATEADD(day, -14, GETDATE())
GROUP BY CAST(pxDecisionTime AS DATE)
ORDER BY DecisionDate;

-- 2. Outcome capture rate (should be > 95%)
SELECT
    CAST(pxDecisionTime AS DATE) AS DecisionDate,
    COUNT(*) AS Impressions,
    SUM(CASE WHEN Outcome != 'Impression' THEN 1 ELSE 0 END) AS WithOutcome,
    CAST(SUM(CASE WHEN Outcome != 'Impression' THEN 1 ELSE 0 END) AS FLOAT)
        / COUNT(*) AS CaptureRate
FROM InteractionHistory
WHERE pxDecisionTime BETWEEN DATEADD(day, -21, GETDATE())
                         AND DATEADD(day, -7, GETDATE())  -- Allow lag
GROUP BY CAST(pxDecisionTime AS DATE)
ORDER BY DecisionDate;

-- 3. Predictor availability (should be > 99%)
SELECT
    PredictorName,
    COUNT(*) AS TotalDecisions,
    SUM(CASE WHEN PredictorValue IS NULL THEN 1 ELSE 0 END) AS MissingValues,
    CAST(SUM(CASE WHEN PredictorValue IS NULL THEN 1 ELSE 0 END) AS FLOAT)
        / COUNT(*) AS MissingRate
FROM ADMPredictorLog
WHERE DecisionDate >= DATEADD(day, -7, GETDATE())
GROUP BY PredictorName
HAVING MissingRate > 0.01
ORDER BY MissingRate DESC;
```

### Data Lineage Audit

For regulatory and compliance purposes, document the lineage of every
data element used in CDH decisions:

```
Decision: CustomerID C001 received Gold_Card_Offer on 2024-01-15

Data lineage:
  Propensity (0.421) ← ADM model Gold_Card_Web
    ← Training data: IH last 180 days
    ← Predictor: CreditScore = 720
         ← Source: CreditBureau API
         ← Last updated: 2024-01-10
    ← Predictor: TenureMonths = 48
         ← Source: CRM Customer table
         ← Last updated: 2024-01-01
    ← Predictor: WebVisits30d = 12
         ← Source: Web Analytics event stream
         ← Last updated: 2024-01-15 (today)

  Value (650) ← CreditCard_LTV_Value component
    ← Expression: CreditScore > 700 → 650
    ← CreditScore source: as above

  Weight (1.0) ← Action Gold_Card_Offer default weight
  ContextWeight (1.0) ← No context rules fired

  Priority: 650 × 0.421 × 1.0 × 1.0 = 273.65
  Result: Selected (ranked #1 of 4 eligible actions)
```

This level of lineage tracing is required for GDPR Article 22 compliance
(automated decision making) and internal model governance.
