# Pega CDH — Explainability Extract & Fairness: Reference Guide

## Overview

The Explainability Extract provides transparency into ADM model decisions. For each customer-action combination, it shows which predictors drove the propensity score — positively or negatively — and by how much.

This serves three key purposes:
1. **Model auditing** — verify the model is using expected predictors
2. **Fairness and compliance** — detect if sensitive attributes are influencing decisions
3. **Debugging** — understand why a specific customer received (or did not receive) a specific action

---

## Explainability Extract Fields

| Field | Description | Example |
|-------|-------------|---------|
| CustomerID | Customer identifier | C0012345 |
| ActionName | Action being explained | Gold_Card_Offer |
| Channel | Channel context | Web |
| ModelID | ADM model that made the decision | Model_001 |
| Propensity | Final propensity score | 0.421 |
| PredictorName | Feature driving the score | CreditScore |
| PredictorValue | Customer's value for this predictor | 720 |
| PredictorWeight | How much this predictor contributed | +0.082 |
| Direction | Positive or Negative contribution | Positive |
| Rank | Importance rank (1 = most important) | 1 |
| DecisionTime | When the decision was made | 2024-01-15 09:32:11 |

---

## Reading Predictor Weights

### Positive vs Negative Contributions

```
Predictor: CreditScore = 720
Weight: +0.082, Direction: Positive
Meaning: A credit score of 720 INCREASES propensity by 0.082

Predictor: DaysSinceLastContact = 180
Weight: -0.054, Direction: Negative
Meaning: Not having been contacted for 180 days DECREASES propensity

Final propensity = Base rate + SUM(all predictor contributions)
```

### Top Predictors Analysis

Aggregate predictor weights across all customers to find globally important features:

```sql
SELECT
    ActionName,
    PredictorName,
    AVG(ABS(PredictorWeight))   AS AvgAbsWeight,
    AVG(PredictorWeight)         AS AvgWeight,
    COUNT(*)                     AS CustomerCount,
    SUM(CASE WHEN Direction = 'Positive' THEN 1 ELSE 0 END) AS PositiveCount,
    SUM(CASE WHEN Direction = 'Negative' THEN 1 ELSE 0 END) AS NegativeCount
FROM ExplainabilityExtract
GROUP BY ActionName, PredictorName
ORDER BY ActionName, AvgAbsWeight DESC
```

---

## Fairness Audit Using Explainability

### Detecting Proxy Discrimination

Even if a sensitive attribute (e.g. ethnicity) is not directly used as a predictor, other predictors that correlate with it (e.g. postcode, certain product types) may introduce indirect discrimination.

**Red flags to investigate:**

| Predictor | Why It Is Suspicious | Investigation |
|-----------|---------------------|---------------|
| PostcodeArea | Highly correlated with race/ethnicity | Check correlation with protected attributes |
| LanguagePreference | May proxy nationality | Review with legal/compliance |
| BranchType | Urban vs rural may proxy socioeconomic status | Analyse acceptance rate by branch type |
| ProductType_Legacy | May reflect historical discriminatory offering | Review which customers hold legacy products |

### Monthly Fairness Report

Run monthly on the Explainability Extract:

```
1. Extract top 5 predictors by AvgAbsWeight per action
2. Cross-reference each predictor with list of sensitive attributes
3. Run correlation analysis: predictor value vs protected group membership
4. Flag any predictor with Correlation > 0.3 with a protected attribute
5. Submit report to compliance team
```

### Acceptance Rate Disparities

Also check Actuals Dataset for acceptance rate differences across demographic groups:

```sql
SELECT
    CustomerDemographic,
    COUNT(*) AS Impressions,
    SUM(ActualLabel) AS Accepts,
    AVG(ActualLabel) AS AcceptRate
FROM ActualsDataset
JOIN CustomerProfile ON CustomerID
GROUP BY CustomerDemographic
HAVING COUNT(*) > 500
ORDER BY AcceptRate
```

Flag if any group's accept rate is < 80% of the highest group's accept rate (the "four-fifths rule").

---

## Explainability for Individual Customer Queries

When a customer or regulator asks "why was I shown this offer?" or "why did I not receive this offer?":

```
CDH > Decision Audit > Customer Lookup
Enter: CustomerID + Date range

Output:
  Decision made: 2024-01-15 09:32
  Action: Gold_Card_Offer
  Propensity: 0.421
  Priority: 252.0
  Result: Selected (rank 1 of 5 eligible actions)

  Top 5 reasons for propensity score:
  1. CreditScore = 720         → +0.082 (Positive)
  2. Tenure = 48 months        → +0.065 (Positive)
  3. WebVisits30d = 12         → +0.041 (Positive)
  4. DaysSinceContact = 45    → -0.028 (Negative)
  5. Balance = £2,100          → +0.019 (Positive)
```

---

# Pega CDH — Engagement Policy: Reference Guide

## Overview

The Engagement Policy defines the rules that govern which customers can receive which actions, in which contexts, subject to which business constraints. It is the primary tool for translating business strategy and regulatory requirements into CDH configuration.

Every action must pass through three layers of the Engagement Policy before reaching arbitration: Eligibility, Applicability, and Suitability.

---

## Eligibility Rules

**Question:** Can this customer ever receive this action?

Eligibility rules are evaluated first. They filter the entire action pool down to actions the customer is fundamentally qualified to receive.

### Common Eligibility Patterns

```
# Age-based eligibility
Customer.Age >= 18 AND Customer.Age <= 70

# Product holding check
Customer.HoldsCurrentAccount = true

# Existing product exclusion
Customer.HoldsCreditCard = false

# Geographic restriction
Customer.Country IN ('UK', 'IE')

# Account status
Customer.AccountStatus = 'Active' AND Customer.ArrearsDays = 0

# Tenure requirement
Customer.TenureMonths >= 12

# Income threshold
Customer.AnnualIncome >= 20000
```

### Eligibility vs Applicability Decision

A useful rule of thumb:
- **Eligibility:** Would this be true even if the customer called in asking for the product?
- **Applicability:** Is this right given the current interaction context?

Credit score eligibility = Eligibility (absolute requirement)
Channel = Web eligibility = Applicability (only in web context)

---

## Applicability Rules

**Question:** Is this action appropriate for this specific interaction context?

Applicability rules are evaluated after eligibility. They filter based on the current session or interaction.

### Common Applicability Patterns

```
# Channel matching
Interaction.Channel IN ('Web', 'Mobile')

# Inbound vs outbound
Interaction.Direction = 'Inbound'

# Session-level signals
Session.ProductPageViewed = 'CreditCards'

# Time-based applicability
CurrentTime.Hour BETWEEN 9 AND 20    -- Business hours only

# Date-based campaign
CurrentDate BETWEEN '2024-06-01' AND '2024-08-31'

# No open complaint
NOT EXISTS (OpenCase WHERE Type = 'Complaint')
```

---

## Suitability Rules

**Question:** Is this action appropriate given broader business and regulatory constraints?

Suitability rules apply last. They enforce compliance, affordability, and responsible lending/selling requirements.

### Common Suitability Patterns

```
# Affordability check
Customer.DebtToIncomeRatio < 0.4

# Maximum credit exposure
Customer.TotalCreditLimit < 50000

# Vulnerability check
Customer.VulnerabilityFlag = false OR Action.Type != 'HighRisk'

# Regulatory cooling-off
Customer.LastApplicationDate < DATEADD(day, -30, today)

# Complaints suppression
Customer.ActiveComplaint = false

# Previous rejection
Customer.LastDeclineReason != 'Fraud'

# Maximum products of type
Customer.CreditCardCount < 3
```

---

## Writing Effective Engagement Policy Rules

### Rule Design Principles

1. **Test every rule with real data** before deployment — check what percentage of customers pass/fail each rule
2. **Document the business rationale** for each rule with a reference to policy or regulation
3. **Set expiry dates** on time-limited rules to prevent them accumulating as technical debt
4. **Use hierarchy** — put the cheapest rules (simple lookups) first, expensive rules (real-time calls) last
5. **Log rule failures** — Decision Audit should record which rule blocked an action

### Rule Coverage Analysis

Regularly check what percentage of customers are blocked at each layer:

| Layer | Customers Blocked | Typical Expected Rate |
|-------|------------------|----------------------|
| Eligibility | 40–60% | Expected — broad filter |
| Applicability | 20–40% | Context-specific reduction |
| Suitability | 5–15% | Compliance filter |
| Arbitration loser | Remaining | Normal competition |
| Selected | 1–5% | Final serving rate |

If Eligibility is blocking > 80%, rules may be too restrictive.
If Suitability is blocking > 30%, compliance rules may be misconfigured.

---

## Contact Policy Configuration

Contact policy is an additional layer that limits how frequently customers can be contacted across all actions.

### Global Limits

```
CDH > Contact Policy > Global Limits

Weekly limits:
  All channels:    max 7 interactions per customer
  Email:           max 2
  SMS:             max 1
  Push:            max 5
  Outbound calls:  max 1

Daily limits:
  All channels:    max 2 per day
```

### Segment-Specific Overrides

```
CDH > Contact Policy > Segment Overrides

Segment: Vulnerable customers (VulnerabilityFlag = true)
Override: max 1 interaction per week, email only

Segment: Opted-out of marketing (MarketingOptOut = true)
Override: max 0 marketing contacts
```

### Post-Interaction Suppression

```
Action: Gold_Card_Offer
Post-impression suppression:  7 days
Post-rejection suppression:   30 days
Post-acceptance suppression:  Permanent (auto-suppress)
```

---

## Engagement Policy Governance

### Version Control

Every change to Engagement Policy should be version controlled:
```
CDH > NBA Designer > Version Management
Version: 2024-Q2-v3
Change log: Added debt-to-income suitability rule per Credit Policy CP-2024-003
Author: [Name]
Approved by: [Credit Policy team]
Effective date: 2024-06-01
```

### Policy Review Schedule

| Policy Layer | Review Frequency | Reviewer |
|---|---|---|
| Eligibility rules | Quarterly | Product team |
| Applicability rules | Monthly | Strategy team |
| Suitability rules | Monthly | Compliance + Credit |
| Contact policy | Quarterly | Compliance |
| Suppression windows | Quarterly | Strategy team |

### Pre-Deployment Checklist

- [ ] All new rules have been tested against 30-day historical data
- [ ] Eligible customer count is within expected range (not too high or too low)
- [ ] Suitability rules reference current policy document version
- [ ] Contact policy limits comply with current regulatory guidance
- [ ] Suppression windows are consistent with channel best practice
- [ ] Rules have documented expiry dates where applicable
- [ ] Impact Analyzer run shows expected change in eligible volume
- [ ] Change has been approved by strategy and compliance sign-off
