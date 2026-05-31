# Pega CDH — Impact Analyzer: Complete Reference Guide

## Overview

Impact Analyzer is a simulation and what-if analysis tool within Pega CDH that allows strategy designers to predict the business impact of changes to NBA strategies **before** those changes go live in production.

Instead of deploying a strategy change and waiting weeks to measure results, Impact Analyzer runs the proposed change against historical Interaction History data and projects the expected difference in business outcomes — number of impressions, predicted accepts, estimated revenue impact, and changes to action distribution.

This de-risks strategy changes and gives business stakeholders quantified projections to support decision-making.

---

## What Impact Analyzer Can Predict

| Analysis Type | Input | Output |
|--------------|-------|--------|
| Strategy change impact | Modified engagement policy | Projected accept rate change, impression count change |
| Value change impact | Modified action value | Change in action selection frequency |
| Weight change impact | Modified action weight | Change in arbitration rank distribution |
| Contact policy change | Modified contact limits | Change in total impression volume |
| New action introduction | New action configuration | Projected reach and estimated accept rate |
| Action removal | Remove action from strategy | Impact on overall NBA coverage |

---

## How Impact Analyzer Works

### Simulation Method

Impact Analyzer replays historical Interaction History events through the **modified strategy configuration** and compares outcomes to what actually happened under the original strategy.

```
Step 1: Define the change
  → e.g. "Increase weight of Gold_Card_Offer from 1.0 to 1.5"

Step 2: Select simulation population
  → Use last 30 days of IH data (or a specific customer segment)

Step 3: Re-run arbitration on historical interactions
  → Apply modified strategy to each historical decision point
  → Record what action would have been selected

Step 4: Compare to actual outcomes
  → Actual: Gold_Card_Offer selected 12% of the time
  → Projected: Gold_Card_Offer selected 19% of the time

Step 5: Apply historical accept rates
  → Project accept volume and estimated revenue impact
```

### Key Assumption

Impact Analyzer assumes that customer response propensities remain constant. It does not predict how customers will react differently to new offers — it projects **selection frequency** changes and applies historical **accept rates** to estimate impact.

This means:
- Impact Analyzer is reliable for arbitration-level changes (weights, values, contact policy)
- Impact Analyzer is less reliable for predicting impact of new actions with no history
- Impact Analyzer cannot predict the effect of ADM model changes (propensity changes)

---

## Running an Impact Analysis

### Step-by-Step Procedure

#### Step 1 — Access Impact Analyzer
```
CDH > Impact Analyzer > New Analysis
```

#### Step 2 — Define the Baseline
Select the current production strategy version as the baseline.
```
Baseline Strategy: Production_v12 (current)
Simulation Period: Last 30 days
Customer Scope: All customers (or select a segment)
```

#### Step 3 — Define the Proposed Change

Choose the type of change:

**Option A — Modify existing configuration**
```
Change Type: Weight Modification
Action: Gold_Card_Offer
Current Weight: 1.0
Proposed Weight: 1.5
```

**Option B — Upload a new strategy version**
```
Upload modified strategy configuration file
Impact Analyzer will compare to baseline automatically
```

#### Step 4 — Configure Simulation Parameters
```
Simulation Population: 100,000 customers (sample for speed)
Channels: All / Specific channels
Monte Carlo Iterations: 1,000 (higher = more accurate, slower)
Confidence Interval: 95%
```

#### Step 5 — Run the Analysis
```
Click "Run Analysis"
Typical runtime: 5–30 minutes depending on population size
```

#### Step 6 — Review Results
The results dashboard shows:

```
IMPACT SUMMARY
─────────────────────────────────────────────
                      Baseline    Projected    Change
Gold_Card_Offer impressions  45,234     71,892    +58.9%
Gold_Card_Offer accepts       4,750      7,548    +58.9%
Gold_Card_Offer revenue      £308K      £490K    +£182K

Personal_Loan impressions    38,112     22,445    -41.1%
Personal_Loan accepts         2,672      1,574    -41.1%
Personal_Loan revenue        £267K      £157K    -£110K

NET REVENUE IMPACT: +£72K per month
CONFIDENCE INTERVAL: +£58K to +£86K (95%)
─────────────────────────────────────────────
```

---

## Understanding Impact Analyzer Output

### Impression Distribution Chart

Shows how action selection frequency changes across all actions. Look for:

- **Actions with large positive changes** — will they have enough ADM training data to support increased volume?
- **Actions with large negative changes** — are these actions still meeting business targets?
- **Actions dropping to near zero** — will they lose ADM training data over time?

### Revenue Impact Table

| Action | Baseline Accepts | Projected Accepts | Accept Rate | Revenue/Accept | Projected Revenue Change |
|--------|-----------------|-------------------|-------------|----------------|--------------------------|
| Gold Card | 4,750 | 7,548 | 10.5% | £65 | +£182,110 |
| Personal Loan | 2,672 | 1,574 | 7.0% | £100 | -£109,800 |
| Balance Transfer | 3,100 | 3,100 | 8.2% | £40 | £0 |
| **Total** | **10,522** | **12,222** | | | **+£72,310** |

### Confidence Intervals

Impact Analyzer shows 95% confidence intervals around all projections. Wide confidence intervals indicate:
- Small simulation population (increase sample size)
- High variance in historical outcomes (inherently uncertain)
- Short simulation period (extend to 60 or 90 days)

Narrow confidence intervals indicate reliable projections.

### Statistical Significance

Impact Analyzer flags changes that are **not statistically significant** at the 95% level. These should be treated as uncertain rather than projected outcomes.

```
⚠ Gold_Card_Offer impression change: NOT STATISTICALLY SIGNIFICANT
   p-value: 0.14 (threshold: 0.05)
   Recommend: Extend simulation period or increase population
```

---

## Common Impact Analysis Use Cases

### Use Case 1 — Testing a Weight Increase for a New Campaign

**Scenario:** Marketing wants to push a new Travel Insurance product for the upcoming holiday season.

**Analysis:**
```
Change: Travel_Insurance weight from 1.0 to 3.0
Period: Last 60 days
Result: +180% impressions, projected +£45K/month
Risk: Personal_Loan impressions drop 30%
Decision: Approve with 60-day campaign window, then revert
```

### Use Case 2 — Contact Policy Tightening

**Scenario:** Compliance requires reducing email contacts from 3/week to 2/week.

**Analysis:**
```
Change: Email channel limit from 3 to 2 per week
Period: Last 30 days
Result: -28% total email impressions, -£89K/month projected revenue
Risk: Low (compliance-driven change is required)
Decision: Approve. Partially offset by increasing web channel weight.
```

### Use Case 3 — Evaluating Action Retirement

**Scenario:** Classic Savings Account offer is being discontinued.

**Analysis:**
```
Change: Remove Classic_Savings from strategy
Period: Last 30 days
Result: Classic_Savings impressions reallocated to other actions
Top beneficiary: Premium Savings (+32% impressions)
Revenue impact: +£12K/month (Premium Savings has higher value)
Decision: Proceed with retirement
```

### Use Case 4 — Value Recalibration

**Scenario:** Finance team updated net present value calculations — Personal Loan value should increase from 800 to 1,100.

**Analysis:**
```
Change: Personal_Loan value from 800 to 1,100
Period: Last 30 days
Result: Personal_Loan rises to #1 ranked action for 34% of customers
Revenue impact: +£156K/month
Risk: Significant shift — run champion/challenger instead of direct change
Decision: Deploy as 20% Challenger for 2 weeks, then promote if results match projection
```

---

## Impact Analyzer vs Champion/Challenger

| Dimension | Impact Analyzer | Champion/Challenger |
|-----------|----------------|---------------------|
| When run | Before deployment | After deployment |
| Data used | Historical IH | Live customer interactions |
| Customer impact | None (simulation only) | Real customers see challenger |
| Time to results | Hours | 2–4 weeks |
| Accuracy | Moderate (assumes stable behaviour) | High (actual customer responses) |
| Best for | Initial go/no-go decision | Final validation before full rollout |

**Recommended workflow:**
```
1. Impact Analyzer → Quantify expected benefit
2. If positive: Deploy as 10% Challenger
3. Champion/Challenger → Validate with real data
4. If validated: Promote to full production
```

---

## Impact Analyzer Configuration Options

### Simulation Population Selection

| Option | Use When |
|--------|---------|
| All customers | General strategy changes |
| Segment filter | Change applies to specific segment only |
| Channel filter | Channel-specific changes |
| Sample (10–30%) | Large populations — faster runtime |
| Full population | Final pre-deployment analysis (most accurate) |

### Time Period Selection

| Period | Use When |
|--------|---------|
| Last 14 days | Quick sanity check |
| Last 30 days | Standard analysis |
| Last 90 days | Seasonal effects need to be captured |
| Custom range | Specific event analysis |

**Recommendation:** Use 30-day minimum for all production decisions. 90 days is preferred for changes affecting seasonal products.

---

## Interpreting Impact Analyzer Limitations

### What Impact Analyzer Cannot Predict

1. **Customer behaviour changes** — if a new price point changes how customers respond, Impact Analyzer will not capture this (it uses historical accept rates)

2. **ADM model learning effects** — as ADM sees more data with the new strategy, propensities will change over time. Impact Analyzer uses current propensities.

3. **Competitive response** — if a competitor changes their offer, historical accept rates may not apply

4. **Cannibalization effects** — if showing more of Action A reduces the customer's appetite for Action B, this interaction is not modelled

5. **Long-term revenue** — Impact Analyzer projects monthly impact; it does not model customer lifetime value changes

### Adjusting for Known Limitations

| Limitation | Mitigation |
|-----------|-----------|
| Historical accept rates may not hold | Apply a confidence discount: multiply projected revenue by 0.7–0.85 |
| Seasonal patterns | Align simulation period to the same season as planned deployment |
| New action (no history) | Use similar action's accept rate as a proxy, flag as estimate |

---

## Impact Analyzer Output Reports

### Executive Summary Report
One-page PDF suitable for stakeholder sign-off.
```
CDH > Impact Analyzer > [Analysis Name] > Export > Executive Summary
```

### Detailed Action Impact Report
Full breakdown by action, channel, and customer segment.
```
CDH > Impact Analyzer > [Analysis Name] > Export > Detailed Report
```

### Comparison Report (Multiple Analyses)
Compare multiple proposed changes side by side.
```
CDH > Impact Analyzer > Compare > Select 2–5 analyses
```

---

## Governance: Using Impact Analyzer in the Change Process

**Recommended governance rule:** Any strategy change expected to impact monthly revenue by > £10,000 must have a completed Impact Analyzer report attached to the change request before deployment approval.

### Change Request Template

```
STRATEGY CHANGE REQUEST
═══════════════════════
Change Description: [Brief description]
Proposed By: [Name, Team]
Target Deployment Date: [Date]

Impact Analyzer Results:
  Analysis Name: [Name]
  Run Date: [Date]
  Simulation Period: [Period]
  Population: [Count]

  Projected Revenue Change: +/- £[Amount]/month
  Confidence Interval: £[Low] to £[High] (95%)
  Statistical Significance: [Yes/No]

  Key Actions Affected:
  - [Action 1]: [Change description]
  - [Action 2]: [Change description]

Recommendation: [Approve / Approve with Champion/Challenger / Reject]
Approved By: [Senior Strategy Manager]
═══════════════════════
```

---

## Impact Analyzer Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Analysis runs but shows 0 impact | Change too small or wrong parameter modified | Verify change was saved before running |
| Very wide confidence intervals | Population too small | Increase to minimum 50,000 customers |
| Analysis fails to complete | IH data volume too large | Use 10–30% sample or reduce time period |
| Projected change does not match Champion/Challenger result | Historical accept rates shifted | Normal — extend Champion/Challenger period |
| All actions show equal impact | Arbitration change not loading | Check strategy version selected is correct |
| Revenue impact shows 0 for all actions | Value not configured on actions | Set Value on all actions in Engagement Policy |
