# CDH NBA Strategy — Design Patterns and Anti-Patterns

## Article Purpose
Documents proven NBA strategy configurations (patterns) and common
mistakes (anti-patterns) observed in Pega CDH implementations.
Use this for strategy review, troubleshooting, and new implementation guidance.

---

## Pattern 1: Segment-Contextual Weight Levers

### Description
Use context rules to apply different weights to the same action depending
on the customer segment, without creating duplicate actions.

### Implementation
```
Action: Personal_Loan_Offer
Base Weight: 1.0

Context Rule: HighValueSegment
  Condition: Customer.CLVScore > 75
  Context Weight: 2.0
  Effect: Priority × 2.0 for high-value customers

Context Rule: RecentWebInterest
  Condition: Session.LoanPageVisits >= 2
  Context Weight: 1.8
  Effect: Priority × 1.8 when customer is browsing loans

Context Rule: AtRisk_Suppress
  Condition: Customer.MissedPayments3Months >= 1
  Context Weight: 0.2
  Effect: Priority × 0.2 — nearly suppressed for risky customers
```

### Benefit
One action definition, multiple personalised behaviours.
Avoids the maintenance burden of managing dozens of near-identical actions.

---

## Pattern 2: ADM Warm-Up with Fixed Propensity Bridge

### Description
New actions have no ADM data. Without intervention, propensity = 0.001
and the action never competes. This pattern provides a "warm-up" phase.

### Implementation
```
Phase 1 (Days 1–30): Fixed propensity bridge
  Action: New_Reward_Card
  Propensity Override: 0.10 (use industry average for similar product)
  Weight: 1.0
  Effect: Action competes at reasonable level during data collection

Phase 2 (Days 30–90): Hybrid mode
  When ResponseCount > 200:
    Propensity Override: Remove
    ADM Naive Bayes: Takes over
    Monitor: AUC weekly

Phase 3 (Day 90+): Full ADM
  When ResponseCount > 500:
    Switch to Gradient Boost
    Normal operation
```

### Configuration Path
```
CDH > Adaptive Models > New_Reward_Card > Propensity Override
Override Type: Fixed value
Value: 0.10
Remove when: ResponseCount > 200
```

---

## Pattern 3: Value Finder Closed-Loop Targeting

### Description
Value Finder identifies underserved customers → their profile is
tagged → NBA strategy automatically targets them more aggressively.

### Implementation
```
Step 1: Monthly Value Finder run writes tags to customer profiles
  Customer.ValueFinderQuadrant = "Underserved"
  Customer.EngagementGap = 45.2
  Customer.TopRecommendedAction = "Premium_Investment"

Step 2: Context Rule in NBA strategy reads the tag
  Context Rule: ValueFinder_Underserved_Boost
  Condition: Customer.ValueFinderQuadrant == "Underserved"
             AND Customer.EngagementGap > 20
  ContextWeight: 2.5
  Applies to: Customer.TopRecommendedAction (dynamic action selection)

Step 3: Contact Policy exception
  Underserved customers get +2 additional contacts per week
  (They are currently UNDER-contacted, not over-contacted)
  CDH > Contact Policy > Segment Override
    Segment: ValueFinderQuadrant = "Underserved"
    Max contacts/week: 7 (vs standard 5)

Step 4: Monthly re-run updates tags
  As engagement improves, CustomerValueFinderQuadrant updates to "Balanced"
  Context rule no longer fires → normal contact frequency resumes
```

### Benefit
Automatic, self-updating targeting that closes engagement gaps over time.

---

## Pattern 4: Revenue-Weighted Champion/Challenger

### Description
Standard C/C tests compare accept rate. This pattern compares
revenue per impression, which is the true business outcome.

### Implementation
```
Standard C/C evaluation:
  Champion accept rate: 8.2%
  Challenger accept rate: 9.1%
  Decision: Promote Challenger → WRONG

Revenue-weighted evaluation:
  Champion: 8.2% × £850/accept = £69.70/impression
  Challenger: 9.1% × £650/accept = £59.15/impression
  Decision: Keep Champion → CORRECT

The Challenger drives more conversions but the product being
accepted has lower revenue. Accept rate alone misleads.
```

### SQL for Revenue-Weighted C/C Evaluation
```sql
SELECT
    ExperimentGroup,
    COUNT(*) AS Impressions,
    SUM(ActualLabel) AS Accepts,
    CAST(SUM(ActualLabel) AS FLOAT) / COUNT(*) AS AcceptRate,
    AVG(CASE WHEN ActualLabel=1 THEN ConversionValue ELSE 0 END)
        AS RevenuePerImpression,
    SUM(ConversionValue) AS TotalRevenue
FROM ActualsDataset
WHERE ExperimentGroup IN ('Champion', 'Challenger')
  AND DecisionTime >= DATEADD(day, -30, GETDATE())
GROUP BY ExperimentGroup;
```

---

## Pattern 5: Cascade Strategy — Primary and Safety Net

### Description
Primary actions target ideal customers. Safety Net actions ensure
every customer receives something relevant even if they fail
all primary action eligibility checks.

### Implementation
```
Primary Actions (high value, restrictive eligibility):
  Gold_Credit_Card: Income > £40K, CreditScore > 700
  Premium_Loan: Tenure > 12mo, No missed payments
  ISA_Investment: HoldsCurrent AND Balance > £5K

Safety Net Actions (low eligibility barrier, lower value):
  Account_Review: All active customers eligible
  Digital_Banking_Features: All digital customers eligible
  Customer_Satisfaction_Survey: All customers, quarterly

Zero-eligible rate check:
  If customer fails ALL primary eligibility → safety net fires
  Safety net should cover > 98% of customer base
```

### Benefit
Eliminates zero-action interactions. Every customer interaction
has purpose. Safety net builds engagement data even for
low-propensity customers.

---

## Anti-Pattern 1: The Monolithic Value Problem

### Description
All actions assigned identical Value = 100 (or same value).
Arbitration becomes entirely propensity-driven with no business control.

### Symptoms
```
Accept rate: High (propensity drives good selection)
Revenue: Suboptimal (high-revenue actions not prioritised)
Strategy control: None (cannot prioritise products)
```

### Correct Approach
```
Values should reflect relative business importance:
  Premium_Credit_Card:  650 (high margin, strategic product)
  Personal_Loan:        450 (moderate margin)
  Standard_Savings:     120 (low margin but high volume)
  Survey:               20 (operational, low value)

The ratio of values matters more than absolute amounts.
Premium card should be ~5× value of survey to ensure it wins
when propensities are similar.
```

---

## Anti-Pattern 2: Weight Inflation

### Description
Marketing keeps adding weight levers without removing old ones.
After 18 months, multiple actions have Weight = 5.0+.
Arbitration is dominated by the most-heavily-weighted recent campaign.

### Symptoms
```
Action concentration: Single action > 60% of all impressions
ADM models: Losing training data on non-weighted actions
Accept rate: High for weighted action, others collapsing
Revenue: Short-term boost, long-term ADM degradation
```

### Correct Approach
```
Weight Policy:
  Levers have mandatory expiry dates (max 90 days)
  Total weight budget: Max 3 actions with Weight > 2.0 simultaneously
  Weight audit: Quarterly review removes expired levers
  Concentration alert: Alert if any action > 35% of impressions
```

---

## Anti-Pattern 3: Orphaned ADM Models

### Description
Actions are retired from the strategy but their ADM models
remain in the system. Models continue to train on historical
data that becomes increasingly irrelevant.

### Symptoms
```
ADM model list shows 150 models
Active strategy has 40 actions
110 models are orphaned
Performance: System slowdown, confusing health reports
```

### Correct Approach
```
Action retirement procedure:
  1. Set action Weight = 0 (stops selection)
  2. Mark ADM model as Inactive
  3. Archive ADM model after 90 days
  4. Document in change log

Model audit query (run quarterly):
SELECT
    m.ModelName,
    CASE WHEN a.ActionName IS NULL THEN 'ORPHANED' ELSE 'ACTIVE' END AS Status
FROM ADMModelInventory m
LEFT JOIN ActiveStrategyActions a ON m.ActionName = a.ActionName
WHERE Status = 'ORPHANED';
```

---

## Anti-Pattern 4: Contact Policy Too Strict + High Weight Compensation

### Description
Contact policy limits are set very low (2 per week) but
high-priority actions have Weight = 10 to "break through".
This creates an arms race that degrades strategy health.

### Symptoms
```
Contact policy blocks: > 40% of attempts
Weight on top actions: 8–15
ADM model training: Degraded (not enough impressions per model)
Customer experience: Always seeing same 1-2 actions
```

### Correct Approach
```
Contact policy and weights should be calibrated together:
  Reasonable contact frequency: 4–6 per week for engaged customers
  Reasonable max weight: 2.0–4.0
  Expected impressions: ~2–4 per action per eligible customer per week

High weights are a symptom of insufficient contact frequency.
Increase contact limit before increasing weights.
```

---

## Anti-Pattern 5: Ignoring Outcome Lag in Analysis

### Description
Analyst reports accept rates for the last 7 days.
Recent days show near-zero acceptance.
Decision: "Our strategy has collapsed" → wrong diagnosis.

### What's Actually Happening
```
Today's impressions: 45,000
Today's outcomes captured so far: 1,200 (most not yet processed)
Apparent accept rate: 1,200/45,000 = 2.7% ← WRONG

If we wait 14 days for outcomes to arrive:
Today's impressions: 45,000
Outcomes after 14 days: 3,870
Actual accept rate: 3,870/45,000 = 8.6% ← CORRECT
```

### Correct Approach
```
Never report accept rate for periods < outcome lag + 3 days buffer:
  Web/Mobile: Exclude last 1 day
  Email: Exclude last 10 days
  SMS: Exclude last 4 days

Apply lag-correction formula when recent data is needed:
  Lag-corrected rate = Observed rate × (HistoricalRate30d / HistoricalRate7d)
  (see SQL cookbook for implementation)
```

---

## Pre-Deployment Review Checklist (Complete)

Use before any strategy deployment to production:

### Strategy Configuration
- [ ] All actions have Value > 0
- [ ] No action has Weight = 0 unintentionally
- [ ] All levers have expiry dates
- [ ] Contact policy limits are calibrated for expected volume
- [ ] Suppression windows are consistent across related actions
- [ ] Safety net actions cover > 98% of customers

### ADM Models
- [ ] All actions have an active ADM model
- [ ] All models have AUC > 0.60 (or are in warm-up phase)
- [ ] All models have ResponseCount > 200 (or have propensity override)
- [ ] No orphaned models (retired actions without archived models)

### Engagement Policy
- [ ] Eligibility covers 10–90% of target customers (not too broad/narrow)
- [ ] Suitability rules reference current policy version
- [ ] Vulnerable customer rules are in place and tested
- [ ] Impact Analyzer run with results attached to change request

### Data Pipeline
- [ ] IH outcome capture confirmed for all channels
- [ ] ADM predictor data flows tested
- [ ] Actuals Dataset match rate > 95%
- [ ] Value Finder scheduled for next month

### Governance
- [ ] Strategy version increment
- [ ] Change log entry with author, approver, effective date
- [ ] Rollback plan documented (which version to revert to)
- [ ] Monitoring dashboard alert thresholds configured
