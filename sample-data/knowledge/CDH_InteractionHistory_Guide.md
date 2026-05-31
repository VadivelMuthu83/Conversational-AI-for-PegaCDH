# Pega CDH — Interaction History: Complete Reference Guide

## Overview

Interaction History (IH) is the central event log of Pega CDH. Every decision CDH makes — every action presented, every customer response, every channel interaction — is recorded in Interaction History. It is the single source of truth for all NBA performance analysis, ADM model training, and regulatory audit requirements.

Understanding IH is fundamental to working with any CDH analytics tool, because every other analysis — ADM snapshots, Actuals Dataset, Value Finder, Impact Analyzer — ultimately draws from IH data.

---

## Interaction History Record Lifecycle

```
Customer triggers an interaction
    ↓
CDH runs arbitration
    ↓
IH record created immediately:
    pxInteractionID = new unique ID
    Outcome = "Impression"
    Propensity = [ADM score]
    Priority = [arbitrated priority]
    pxDecisionTime = [now]
    ↓
Action presented to customer
    ↓
Customer responds (or doesn't)
    ↓
IH record UPDATED:
    Outcome = "Accepted" | "Rejected" | "NoResponse"
    OutcomeTime = [response time]
    ↓
ADM model receives outcome signal
    ↓
Propensity model updated for next interaction
```

---

## IH Field Reference

### Core Identity Fields

| Field | Data Type | Description | Example |
|-------|-----------|-------------|---------|
| pxInteractionID | String | Globally unique interaction identifier | IH-20240115-00123456 |
| SubjectID | String | Customer identifier (links to CRM) | C0012345 |
| CustomerID | String | Alias for SubjectID in some exports | C0012345 |
| pyWorkID | String | Associated case/work object (if any) | WORK-NBA-12345 |

### Action Fields

| Field | Data Type | Description | Example |
|-------|-----------|-------------|---------|
| ActionName | String | Name of the action presented | Gold_Card_Offer |
| Issue | String | Business issue (highest level category) | Growth |
| Group | String | Action group within the issue | CreditCards |
| Treatment | String | Variant of the action (A/B test) | EmailVariant_A |
| Direction | String | Inbound or Outbound interaction | Outbound |

### Decision Fields

| Field | Data Type | Description | Example |
|-------|-----------|-------------|---------|
| Propensity | Decimal [0,1] | ADM model propensity at decision time | 0.421 |
| Priority | Decimal | Final arbitrated priority score | 252.0 |
| Weight | Decimal | Action weight applied in arbitration | 1.5 |
| Value | Decimal | Business value of the action | 500 |
| Rank | Integer | Rank of this action in the result set | 1 |
| ExperimentGroup | String | Champion or Challenger | Champion |
| Context | String | Context rules applied | HighIntent |

### Outcome Fields

| Field | Data Type | Description | Example |
|-------|-----------|-------------|---------|
| Outcome | String | Customer response | Accepted |
| OutcomeTime | DateTime | When customer responded | 2024-01-15 14:32:00 |
| pxDecisionTime | DateTime | When CDH made the decision | 2024-01-15 09:32:00 |

### Channel Fields

| Field | Data Type | Description | Example |
|-------|-----------|-------------|---------|
| Channel | String | Delivery channel | Web |
| Direction | String | Inbound/Outbound | Outbound |
| ApplicationName | String | Application that triggered the interaction | WebPortal |

---

## Outcome Values and Their Meaning

| Outcome Value | Meaning | Counts As | ADM Signal |
|--------------|---------|-----------|------------|
| Impression | Action was shown, no response yet | — | Pending |
| Clicked | Customer clicked but did not complete | Negative (partial) | Positive (weak) |
| Accepted | Customer positively responded | Positive | Positive (strong) |
| Rejected | Customer explicitly declined | Negative | Negative |
| NoResponse | Time window expired with no action | Negative | Negative (weak) |
| Converted | Full conversion completed (purchase, activation) | Strong Positive | Positive (strong) |
| Suppressed | Action was suppressed before showing | — | None |

### Outcome Timing

CDH waits for a configurable response window before converting an "Impression" to "NoResponse":

```
Web/Mobile:     30 minutes (session-level response window)
Email:          7 days (email response window)
SMS:            48 hours
Push:           72 hours
CallCentre:     During call (immediate outcome required)
```

**Configuration path:** CDH > Interaction > Channel Settings > Response Window

---

## IH Data Volume Considerations

IH grows quickly. A mid-size deployment might generate:

```
1,000 customers/day × 3 channels × 2 actions/channel = 6,000 records/day
Large deployment: 100,000 customers/day = 600,000 records/day
Annual volume: 6,000 × 365 = 2.19M records/year (small)
Annual volume: 600,000 × 365 = 219M records/year (large)
```

### IH Retention Policy

IH records should be retained for:
- **Operational use** (ADM training): rolling 90 days minimum
- **Regulatory compliance**: depends on jurisdiction (typically 5–7 years)
- **Analytics**: archive beyond 90 days to cold storage, retain 2 years minimum

**Configuration path:** CDH > Data Management > Interaction History > Retention Policy

---

## IH Pre-Aggregation for Analysis

Raw IH with millions of rows is impractical to query directly for strategic analysis. Pre-aggregate to the level appropriate for the question being answered.

### Standard Aggregation — Action × Channel × Week

This is the most useful aggregation for NBA performance reporting:

```sql
SELECT
    ActionName,
    Channel,
    DATETRUNC('week', pxDecisionTime)  AS Week,
    COUNT(*)                            AS Impressions,
    SUM(CASE WHEN Outcome IN ('Accepted','Converted') THEN 1 ELSE 0 END) AS Accepts,
    SUM(CASE WHEN Outcome = 'Rejected' THEN 1 ELSE 0 END) AS Rejects,
    AVG(Propensity)                     AS AvgPropensity,
    AVG(Priority)                       AS AvgPriority,
    CAST(SUM(CASE WHEN Outcome IN ('Accepted','Converted') THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(*), 0)           AS AcceptRate
FROM InteractionHistory
WHERE pxDecisionTime >= DATEADD(week, -12, GETDATE())
GROUP BY ActionName, Channel, DATETRUNC('week', pxDecisionTime)
ORDER BY Week DESC, Impressions DESC
```

### Accept Rate by Issue and Group

```sql
SELECT
    Issue,
    [Group],
    COUNT(*)                AS Impressions,
    SUM(CASE WHEN Outcome = 'Accepted' THEN 1 ELSE 0 END) AS Accepts,
    AVG(CAST(Outcome = 'Accepted' AS FLOAT)) AS AcceptRate,
    AVG(Propensity)         AS AvgPropensity
FROM InteractionHistory
WHERE pxDecisionTime >= DATEADD(month, -3, GETDATE())
GROUP BY Issue, [Group]
ORDER BY AcceptRate DESC
```

---

## IH Export Formats

### JSON Export (IHData.json)

```json
{
  "InteractionHistory": [
    {
      "pxInteractionID": "IH-20240115-00123456",
      "SubjectID": "C0012345",
      "ActionName": "Gold_Card_Offer",
      "Issue": "Growth",
      "Group": "CreditCards",
      "Channel": "Web",
      "Direction": "Outbound",
      "Outcome": "Accepted",
      "Propensity": 0.421,
      "Priority": 252.0,
      "Weight": 1.0,
      "Value": 500,
      "Rank": 1,
      "ExperimentGroup": "Champion",
      "pxDecisionTime": "2024-01-15T09:32:11.000Z",
      "OutcomeTime": "2024-01-15T14:32:45.000Z"
    }
  ]
}
```

### CSV Export

```
pxInteractionID,SubjectID,ActionName,Issue,Group,Channel,Direction,Outcome,Propensity,Priority,Weight,Value,Rank,ExperimentGroup,pxDecisionTime,OutcomeTime
IH-20240115-00123456,C0012345,Gold_Card_Offer,Growth,CreditCards,Web,Outbound,Accepted,0.421,252.0,1.0,500,1,Champion,2024-01-15 09:32:11,2024-01-15 14:32:45
```

---

## IH Data Quality Checks

Run these checks before any IH-based analysis:

| Check | Query Logic | Alert If |
|-------|------------|----------|
| Records with no decision time | COUNT WHERE pxDecisionTime IS NULL | > 0.1% |
| Records with no outcome | COUNT WHERE Outcome IS NULL | > 0.5% |
| Duplicate interaction IDs | COUNT vs COUNT DISTINCT pxInteractionID | Any duplicates |
| Future-dated decisions | COUNT WHERE pxDecisionTime > NOW() | Any records |
| Propensity out of range | COUNT WHERE Propensity NOT BETWEEN 0 AND 1 | Any records |
| Zero priority records | COUNT WHERE Priority = 0 | > 0.1% |
| Unknown channels | COUNT WHERE Channel NOT IN (known_channels) | Any records |

---

## IH in the CDH Analytics Ecosystem

| Tool | How It Uses IH |
|------|----------------|
| ADM Models | IH outcomes are the training labels for propensity learning |
| Value Finder | IH impression counts and accept rates feed the Engagement Score |
| Impact Analyzer | Historical IH is replayed through modified strategies for simulation |
| Actuals Dataset | IH provides the CDH-side records; merged with CRM outcomes |
| Explainability Extract | IH decision records linked to predictor values at decision time |
| Contact Policy | IH queried in real-time to check recent contact frequency |
| Decision Audit | Full IH record for a specific customer/interaction for troubleshooting |

---

## Troubleshooting IH Issues

| Symptom | Likely Cause | Diagnostic | Fix |
|---------|-------------|------------|-----|
| IH records show Impression but never update to Accepted | Outcome pipeline not connected | Check outcome API or batch upload | Configure real-time outcome capture |
| Propensity = 0 for all records | ADM model not initialised | Check model status in ADM console | Initialise Naive Bayes model |
| No records for a specific channel | Channel not configured | Check channel configuration | Add channel to CDH configuration |
| SubjectID missing from some records | Anonymous sessions | Check session management | Require login before decision |
| IH growing too fast | Too many impressions per customer | Check contact policy | Tighten contact policy limits |
| Outcome = NoResponse unusually high | Response window too short | Check channel response window | Extend response window |
