# CDH Impact Analyzer — Worked Scenarios and Interpretation Guide

## Article Purpose
This article provides step-by-step worked examples of every major Impact
Analyzer scenario type. Each scenario includes setup, expected output,
interpretation, decision criteria, and what to do when results are
ambiguous or unexpected.

---

## Scenario 1: Weight Change Analysis

### Business Context
Marketing wants to increase exposure for a new Rewards Credit Card launched
last month. Current weight = 1.0. Proposed weight = 2.5.

### Setup in Impact Analyzer

```
CDH > Impact Analyzer > New Analysis
Analysis Name: RewardsCard_WeightIncrease_2.5x_Jun2024
Baseline: Production_Strategy_v14 (current)
Proposed Change: Rewards_Credit_Card weight → 2.5

Simulation Settings:
  Period: Last 30 days of IH
  Population: All customers (100% sample)
  Channels: Web, Mobile, Email
  Monte Carlo: 1,000 iterations
```

### Results Output

```
IMPACT ANALYSIS RESULTS
═══════════════════════════════════════════════════════════
Action               | Baseline    | Projected   | Change
─────────────────────|─────────────|─────────────|────────
Rewards_Credit_Card  | 8,234 impr  | 18,102 impr | +120%
                     | 4.8% AR     | 4.8% AR     | 0%
                     | £24,547 rev | £53,993 rev | +£29,446

Gold_Card_Offer      | 22,451 impr | 14,832 impr | -34%
                     | 9.2% AR     | 9.2% AR     | 0%
                     | £113,434 rev| £74,930 rev | -£38,504

Personal_Loan        | 18,332 impr | 16,445 impr | -10%
                     | 7.1% AR     | 7.1% AR     | 0%
                     | £54,734 rev | £49,129 rev | -£5,605

All others           | 51,983 impr | 50,621 impr | -3%
─────────────────────|─────────────|─────────────|────────
NET REVENUE IMPACT   |             |             | -£14,663/mo
CONFIDENCE INTERVAL  |             |             | -£9,200 to -£20,100
SIGNIFICANCE         | STATISTICALLY SIGNIFICANT (p < 0.001)
═══════════════════════════════════════════════════════════
```

### Interpretation

The analysis shows the weight increase would cost £14,663/month because
Rewards Card (4.8% accept rate) displaces Gold Card (9.2% accept rate)
and Personal Loan (7.1% accept rate). Despite nearly doubling Rewards Card
impressions, the net revenue is NEGATIVE because the displaced actions
had higher accept rates and higher value.

### Decision

**Reject the weight increase as proposed.** Instead:
- Option A: Increase Rewards Card value to reflect true LTV if it is understated
- Option B: Set weight = 1.5 (smaller boost, less displacement)
- Option C: Target the weight increase to customers for whom Rewards Card
  ADM propensity already exceeds Gold Card propensity (segment-specific lever)

---

## Scenario 2: New Action Introduction

### Business Context
A new Home Insurance cross-sell action is being added. No historical
interaction data exists. Estimate impact before launch.

### Challenge
Impact Analyzer cannot use historical accept rates for new actions.
Solution: Use similar existing action's accept rate as a proxy.

### Setup

```
CDH > Impact Analyzer > New Analysis
Analysis Name: HomeInsurance_NewAction_Launch
Change Type: New Action Introduction
Action: Home_Insurance_CrossSell
Value: 280
Initial Weight: 1.0
Propensity Proxy: Use accept rate of Contents_Insurance (similar product)
  → Contents_Insurance historical accept rate: 5.3%

Note: Mark analysis as ESTIMATED (proxy used, not historical data)
```

### Results Output

```
⚠ ESTIMATED RESULTS — New action with no historical data
   Proxy: Contents_Insurance accept rate (5.3%)

Action                  | Projected Monthly
─────────────────────────|──────────────────
Home_Insurance_CrossSell | 12,341 impressions
                         | 5.3% accept rate (proxy)
                         | 654 predicted accepts
                         | £183,120 estimated revenue

Actions displaced        | -4% average impression reduction
Net impact               | +£94,000/month (estimated)
Confidence interval      | Wide: +£45K to +£143K (95%)

RECOMMENDATION: Wide confidence interval reflects proxy uncertainty.
Deploy as 20% Challenger first; validate with real accept rate after
2 weeks before scaling to 100%.
```

### Interpretation and Decision

Use this as a go/no-go indicator only:
- Positive projected revenue → proceed with Champion/Challenger test
- Wide confidence interval → do NOT set final budget expectations from this
- Real accept rate may differ from proxy — monitor actual IH within 7 days

---

## Scenario 3: Contact Policy Tightening

### Business Context
Compliance requires reducing total outbound contacts from 7 per week
to 5 per week per customer. Quantify revenue impact.

### Setup

```
CDH > Impact Analyzer > New Analysis
Analysis Name: ContactPolicy_5PerWeek_Compliance
Change: Global weekly contact limit 7 → 5

Note: This change affects ALL actions equally. Impact Analyzer
will recalculate which impressions would not have occurred
under the tighter policy.
```

### Results Output

```
CONTACT POLICY IMPACT
═══════════════════════════════════════════
Policy Change: Max contacts/week 7 → 5
Customers affected: 18,332 (customers currently receiving 6-7/week)

Impressions removed: 36,664/month (-18% of total impressions)
Accepts removed: 2,199/month (-18% of total accepts)
Revenue removed: £131,940/month

Breakdown by channel:
  Email:      -8,112 impressions → -£38,400/month
  Push:       -15,443 impressions → -£23,200/month
  Web:        0 impressions removed (inbound, not counted in limit)
  SMS:        -13,109 impressions → -£70,340/month

NET REVENUE IMPACT: -£131,940/month
CONFIDENCE: Narrow (±£8,000) — HIGH CONFIDENCE
Note: This change is compliance-mandated; revenue impact is unavoidable.
═══════════════════════════════════════════
```

### Mitigation Analysis

With the projected loss quantified, run a second analysis to find
mitigations:

```
CDH > Impact Analyzer > New Analysis
Analysis Name: ContactPolicy_MitigationTest
Changes (combined):
  1. Global limit: 7 → 5 (required)
  2. Web personalisation weight: 1.0 → 2.0 (mitigation)
  3. CallCentre weight: 1.0 → 1.5 (mitigation)

Net impact: -£131,940 + £67,200 (web) + £28,400 (CC) = -£36,340/month
Mitigation recovers 72% of revenue loss via channel rebalancing
```

---

## Scenario 4: Value Recalibration

### Business Context
Finance team updated net present value calculations. Premium_Savings value
increases from 200 to 380. Understand the strategy-wide impact.

### Setup

```
CDH > Impact Analyzer > New Analysis
Analysis Name: PremiumSavings_ValueIncrease_200to380
Change: Premium_Savings_Account value 200 → 380

Simulation Period: Last 60 days
Population: All channels, all customers
```

### Results Output

```
VALUE CHANGE IMPACT
═══════════════════════════════════════════════════════════
                      | Baseline  | Projected | Change
──────────────────────|──────────|───────────|────────
Premium_Savings impr  | 9,112    | 19,887    | +118%
Premium_Savings AR    | 6.2%     | 6.2%      | unchanged
Premium_Savings rev   | £113K    | £246K     | +£133K

Gold_Card displaced   | -22%     |           | -£89K
Personal_Loan displ   | -8%      |           | -£31K

NET IMPACT: +£13,000/month (modest positive)
CONFIDENCE: p = 0.12 — NOT STATISTICALLY SIGNIFICANT
NOTE: Confidence interval crosses zero (-£4K to +£30K)
═══════════════════════════════════════════════════════════
```

### Interpretation — Not Significant

The result is NOT statistically significant (p = 0.12). The confidence
interval includes zero, meaning the change could easily have no effect.

**Why this happens:** Value = 380 makes Premium_Savings competitive with
Gold Card (Value 650 × lower propensity) but the populations where it
wins arbitration are thin. The net effect is small and uncertain.

**Decision tree for non-significant results:**

```
Is the projected change positive?
  YES → Small-but-uncertain positive outcome
         → Implement if organisationally simple; monitor closely
         → Do NOT include in revenue forecasts

Is the projected change negative?
  YES → Even uncertain negative outcomes should be reviewed
         → Do not implement; investigate why recalibrated value causes harm

Is the projected change near zero?
  YES → Value change has no meaningful arbitration effect
         → Still implement if Finance calculation is correct
         → No need for mitigation
```

---

## Scenario 5: Champion/Challenger Strategy Test

### Business Context
A new strategy variant (Challenger) uses a different eligibility rule
set and different weights. Before full deployment, quantify expected
revenue impact.

### Setup

```
CDH > Impact Analyzer > New Analysis
Analysis Name: StrategyV2_vs_Current_Q3
Baseline: Production_Strategy_v14 (Champion, 100% traffic)
Proposed: Strategy_v15 (Challenger, proposed full deployment)

Upload modified strategy configuration as Strategy_v15
Impact Analyzer runs all historical IH through both strategies
and compares which actions would have been selected
```

### Results Output

```
STRATEGY COMPARISON: v14 (Baseline) vs v15 (Proposed)
═══════════════════════════════════════════════════════════
Metric                | v14 Baseline | v15 Proposed | Delta
──────────────────────|──────────────|──────────────|──────
Total impressions     | 101,112      | 98,445       | -2.6%
Predicted accepts     | 7,234        | 8,102        | +12.0%
Predicted accept rate | 7.15%        | 8.23%        | +1.08pp
Predicted revenue     | £456K        | £511K        | +£55K/mo
Coverage (≥1 action)  | 94.2%        | 95.1%        | +0.9pp

Top improved actions:
  Home_Insurance: +3,201 impressions, predicted +8.2% accept
  Premium_Savings: +1,102 impressions

Top reduced actions:
  Legacy_Savings: -4,312 impressions (expected, planned retirement)
  Basic_Card: -2,108 impressions

RECOMMENDATION: Strong candidate for full deployment.
However: Run as 15% Challenger for 3 weeks first to validate
         predicted accept rate improvement with real data.
═══════════════════════════════════════════════════════════
```

---

## Interpreting Impact Analyzer Confidence Intervals

### What the Confidence Interval Means

```
Projected change: +£55,000/month
95% Confidence interval: +£38,000 to +£72,000

Interpretation:
  If we ran this simulation 100 times with different samples of customers,
  95 of those simulations would show a result between +£38K and +£72K.
  The true expected value is most likely £55K but could reasonably
  be as low as £38K or as high as £72K.
```

### When Confidence Intervals Are Wide

Wide intervals (span > 2× the point estimate) indicate:

| Cause | Evidence | Fix |
|-------|----------|-----|
| Small simulation population | < 10,000 customers | Increase to full population |
| Short time period | < 14 days | Extend to 30+ days |
| High variance in outcomes | Seasonal or event-driven data | Use longer period that spans multiple cycles |
| New action with proxy accept rate | Marked as ESTIMATED | Accept wider interval; use Champion/Challenger to narrow |

### Statistical Significance Interpretation

```
p-value < 0.001:  Very strong evidence — result is not due to chance
p-value 0.001–0.05: Significant — reasonable confidence in result
p-value 0.05–0.15:  Marginal — treat as uncertain; small sample or small effect
p-value > 0.15:   Not significant — result may be due to random variation
```

### Decision Rules Based on Significance

```
Change projected positive AND significant (p < 0.05):
  → Strong case to deploy; use in financial projections

Change projected positive AND NOT significant (p > 0.05):
  → Weak case; deploy as small Challenger (5%) to gather real data

Change projected negative AND significant:
  → Strong case to reject the change

Change projected negative AND NOT significant:
  → Investigate why impact is negative; unlikely to be random if model correct

Confidence interval crosses zero (includes both + and -):
  → Cannot conclude direction of impact; need more data before deciding
```

---

## Common Impact Analyzer Errors and Misinterpretations

### Error 1: Treating projections as guaranteed outcomes

**Wrong:** "Impact Analyzer says +£55K/month so we'll budget that"
**Right:** "Impact Analyzer projects +£38K to +£72K. We'll budget £38K
(lower bound) and validate with 15% Challenger before full deployment."

Impact Analyzer uses historical accept rates. If customer behaviour
changes (new competitor, economic change), actual results will differ.

### Error 2: Ignoring displaced actions

**Wrong:** Looking only at the target action's impression increase
**Right:** Always check which actions are DISPLACED — they are losing
impressions. If displaced actions have higher accept rates, net revenue
may be negative even when target action grows significantly.

### Error 3: Running on too short a period

**Wrong:** Running a 7-day simulation to approve a permanent strategy change
**Right:** Use minimum 30 days. 60–90 days for seasonal products.
The shorter the period, the higher the variance and the less reliable the result.

### Error 4: Comparing percentage change vs absolute change

**Wrong:** "Rewards Card impressions increased 120% — great result!"
**Right:** 120% increase on a base of 8,234 = +9,868 impressions.
Gold Card dropped 34% on a base of 22,451 = -7,633 impressions.
The absolute displacement matters more than the percentage.

### Error 5: Using Impact Analyzer for ADM model changes

Impact Analyzer does NOT predict the effect of propensity changes.
If you change a predictor in the ADM model, Impact Analyzer will not
reflect the resulting propensity change — it uses current propensity scores.

For ADM model changes, use Champion/Challenger exclusively.
