# Pega CDH — Arbitration: Complete Reference Guide

## Overview

Arbitration is the decision engine at the heart of Pega Customer Decision Hub (CDH). It determines which Next Best Actions (NBAs) are presented to a customer when multiple eligible actions compete for the same interaction slot. Arbitration ensures that every customer interaction delivers the action that maximises value for both the business and the customer.

Arbitration runs every time a customer triggers an interaction — a web visit, inbound call, email send, or mobile app session. It evaluates all eligible actions and ranks them using a priority formula before selecting the top action(s) to present.

---

## The Arbitration Priority Formula

The core formula used by Pega CDH arbitration is:

```
Priority = Value × Propensity × Weight × ContextWeight
```

### Component Definitions

| Component | Description | Typical Range | Configured Where |
|-----------|-------------|---------------|-----------------|
| Value | Business value of the action to the organisation | 0 – 1,000,000 | Action configuration |
| Propensity | ADM model prediction of customer response probability | 0.0 – 1.0 | Adaptive Decision Manager |
| Weight | Strategy-level multiplier to boost or suppress an action | 0.0 – 10.0 | Engagement Policy |
| ContextWeight | Situation-specific multiplier applied by context rules | 0.0 – 5.0 | Context rules |

### Priority Calculation Example

| Action | Value | Propensity | Weight | ContextWeight | Priority |
|--------|-------|-----------|--------|---------------|----------|
| Gold Card Offer | 500 | 0.42 | 1.0 | 1.2 | 252.0 |
| Personal Loan | 800 | 0.18 | 0.8 | 1.0 | 115.2 |
| Balance Transfer | 300 | 0.55 | 1.5 | 1.0 | 247.5 |
| Travel Insurance | 200 | 0.61 | 1.0 | 0.9 | 109.8 |

Gold Card Offer wins arbitration with Priority = 252.0.

---

## Arbitration Layers

Arbitration operates in three sequential layers. Each layer eliminates ineligible actions before the final priority ranking.

### Layer 1 — Eligibility

Determines whether the customer **can** receive the action at all.

Common eligibility conditions:
- Customer must hold a specific product type
- Customer age must be within a range (e.g. 18–65)
- Account must be in good standing (no arrears, no blocks)
- Customer must not already hold the offered product
- Customer must be in the target geographic region

**Configuration path:** CDH > NBA Designer > Engagement Policy > Eligibility

**Best practice:** Keep eligibility rules broad. Over-restricting here reduces the action pool and limits personalisation. Save fine-grained filtering for Applicability.

### Layer 2 — Applicability

Determines whether the action is relevant **in this specific context**.

Common applicability conditions:
- Channel matches action's configured delivery channels
- Inbound vs Outbound direction matches
- Customer segment matches action targeting
- Active case exists requiring this action
- Current date is within the action's active date range

**Configuration path:** CDH > NBA Designer > Engagement Policy > Applicability

### Layer 3 — Suitability

Applies business rules and regulatory constraints.

Common suitability conditions:
- Debt-to-income ratio below threshold for credit products
- No active complaint or escalation on account
- Customer has not declined the same action within the suppression window
- Affordability check passes for financial products
- Vulnerable customer flag not set (for high-risk products)

**Configuration path:** CDH > NBA Designer > Engagement Policy > Suitability

---

## Suppression and Contact Policy

### Contact Policy
Limits the total number of interactions across all channels per time period.

Typical configuration:
```
Global:  max 5 contacts per customer per week
Email:   max 2 per week
SMS:     max 1 per week
Push:    max 3 per week
Web:     unlimited (passive channel)
CallCentre: max 1 per week (outbound)
```

**Configuration path:** CDH > Contact Policy > Global Limits

### Action-Level Suppression
Prevents the same action from being shown too frequently.

```
Standard suppression:  7 days after impression
Post-rejection:        30 days after rejection
Post-acceptance:       Permanent (customer already accepted)
```

### Suppression Check Order
1. Global contact policy checked first
2. Channel contact policy checked
3. Action-level suppression checked
4. If any limit exceeded → action removed from candidate pool

---

## Value Configuration

Value represents the business benefit of a customer accepting the action. It should reflect the net present value or revenue contribution of the outcome.

### Value Types

**Static Value:** Fixed number assigned to the action.
```
Gold Card Offer Value = 500
Personal Loan Value   = 800
```

**Dynamic Value:** Calculated using a value component or expression.
```
Loan Value = LoanAmount × NetMargin × CustomerLifetimeMultiplier
```

**Value Components:** Reusable value calculations that can be shared across actions. Configured in CDH > Value Components.

### Setting Realistic Values

Recommended approach:
1. Calculate average net revenue per successful conversion
2. Multiply by average retention rate improvement if applicable
3. Subtract cost to serve (contact cost, offer cost)
4. Apply a risk adjustment factor

| Product | Gross Revenue | Cost to Serve | Net Value |
|---------|--------------|---------------|-----------|
| Credit Card | £800/year | £150 | 650 |
| Personal Loan | £1,200/year | £200 | 1,000 |
| Home Insurance | £300/year | £50 | 250 |
| Travel Insurance | £150/year | £20 | 130 |

---

## Levers and Weights

Weights are the primary tool for a strategy designer to influence arbitration without changing the value or propensity.

### When to Use Weights

| Use Case | Weight Adjustment | Example |
|----------|------------------|---------|
| Promote a strategic action | Increase weight > 1.0 | New product launch: weight = 2.5 |
| Suppress a low-priority action | Decrease weight < 1.0 | Legacy product: weight = 0.3 |
| A/B test equal exposure | Set equal weights | Champion/Challenger: both = 1.0 |
| Block an action entirely | Set weight = 0 | Under compliance review: weight = 0 |

### Weight Hierarchy

Weights can be applied at multiple levels. Lower levels override higher levels.

```
Issue Level Weight
  └── Group Level Weight
        └── Action Level Weight  ← most specific, wins
```

### Levers (Real-Time Weight Adjustment)

Levers allow business users to adjust weights without deploying code changes. Used for:
- Seasonal campaigns (increase weight for holiday offers)
- Regulatory compliance adjustments
- Budget pacing (reduce weight when budget is spent)

**Configuration path:** CDH > Arbitration > Levers

---

## Context Weighting

Context weights apply situational multipliers based on the customer's current state or behaviour.

### Common Context Rules

| Context | Trigger | Weight Multiplier |
|---------|---------|-------------------|
| High-intent signal | Customer viewed product page 3+ times | 1.8 |
| Life event — new home | Mortgage enquiry in past 90 days | 2.0 |
| At-risk | Missed payment in past 30 days | 0.5 (reduce sales offers) |
| Inbound call — complaint | Call reason = complaint | 0.0 (suppress all sales) |
| High-value customer | CustomerTier = Platinum | 1.5 |

**Configuration path:** CDH > Arbitration > Context Weighting

---

## Bundles and Multi-Action Responses

By default arbitration returns a single top-ranked action. Bundles allow multiple actions to be returned simultaneously.

### Bundle Types

**Fixed Bundle:** Always returns exactly N actions.
- Used for: Email with 3 product recommendations, web page with 2 offers

**Ranked Bundle:** Returns top N actions by priority.
- Used for: Call centre agent desktop showing 3 suggestions

**Diversified Bundle:** Returns top N actions ensuring variety (no two actions from same group).
- Used for: Prevents all slots being filled by variations of one product

**Configuration path:** CDH > Interaction > Bundle Configuration

---

## Champion / Challenger in Arbitration

Champion/Challenger testing within arbitration allows you to compare two strategy variants.

### How It Works

1. Define Champion strategy (current production strategy)
2. Define Challenger strategy (new variant to test)
3. Set traffic split (e.g. 90% Champion, 10% Challenger)
4. Arbitration routes each interaction to Champion or Challenger based on split
5. Outcomes recorded separately in Interaction History with ExperimentGroup field

### Measuring Results

Compare across ExperimentGroup values:
```
SELECT ExperimentGroup, COUNT(*) as impressions,
       SUM(CASE WHEN Outcome = 'Accepted' THEN 1 ELSE 0 END) as accepts,
       AVG(Propensity) as avg_propensity
FROM InteractionHistory
GROUP BY ExperimentGroup
```

Promote Challenger to Champion when:
- Accept rate improvement > 5% (statistically significant)
- Minimum 1,000 impressions per group
- No regression in customer satisfaction metrics

---

## Arbitration Diagnostics

### Investigating Why an Action Was Not Selected

Use the **Decision Audit** trail in CDH > Tools > Decision Audit to trace why a specific action was excluded for a customer.

Common exclusion reasons logged:
- `ELIGIBILITY_FAILED` — customer did not meet eligibility conditions
- `APPLICABILITY_FAILED` — context not applicable
- `SUITABILITY_FAILED` — business rule blocked action
- `CONTACT_POLICY_EXCEEDED` — too many contacts this period
- `SUPPRESSION_ACTIVE` — action suppressed after recent interaction
- `ZERO_WEIGHT` — action weight set to 0
- `OUTRANKED` — action was eligible but lower priority than selected action

### Common Arbitration Issues and Fixes

| Symptom | Likely Cause | Diagnostic Step | Fix |
|---------|-------------|-----------------|-----|
| Only one action ever selected | Weight = 0 on other actions | Check action weights in Engagement Policy | Set appropriate weights |
| High propensity actions not selected | Low value assigned | Compare Value × Propensity across actions | Recalibrate value |
| No actions returned | All fail eligibility | Check Decision Audit for ELIGIBILITY_FAILED | Broaden eligibility rules |
| Same action shown repeatedly | Suppression not configured | Check suppression settings | Add 7-day post-impression suppression |
| Accept rate dropped suddenly | Weight or value change | Check strategy change log | Revert or investigate change |

---

## Arbitration Performance Tuning

### Reducing Arbitration Latency

Target latency: < 200ms for real-time channels (web, mobile)

| Optimisation | Impact | How |
|---|---|---|
| Pre-compute eligibility | High | Use scheduled rules for slowly-changing conditions |
| Limit candidate pool | High | Ensure tight eligibility to reduce evaluation count |
| Cache ADM predictions | Medium | Enable propensity caching for same-session actions |
| Simplify suitability rules | Medium | Combine multiple conditions into one rule |
| Index engagement policy | Low | CDH > Admin > Rebuild Policy Index |

### Monitoring Arbitration Health

Key metrics to track daily:
- Average candidate actions per customer (target: 5–15)
- % interactions with zero eligible actions (target: < 2%)
- Average arbitration latency (target: < 200ms)
- Actions ranked #1 concentration (no single action > 40% of selections)

---

## Arbitration Configuration Checklist

Before going live, verify:

- [ ] All actions have a non-zero Value configured
- [ ] All actions have at least one Eligibility rule
- [ ] Contact policy limits are defined for each channel
- [ ] Suppression windows are set for each action
- [ ] Weight levers are defined for campaign management
- [ ] Champion/Challenger split configured for new strategies
- [ ] Decision Audit trail enabled for at least 7 days of history
- [ ] Arbitration latency tested under expected peak load
- [ ] Bundle size matches UI/channel capacity (e.g. 3 for call centre desktop)

---

## Related CDH Components

| Component | Relationship to Arbitration |
|-----------|---------------------------|
| ADM Models | Provide Propensity input to priority formula |
| Value Finder | Identifies segments where arbitration output misses opportunity |
| Interaction History | Records every arbitration outcome |
| Impact Analyzer | Predicts effect of arbitration changes before deployment |
| Engagement Policy | Defines eligibility, applicability, suitability rules |
| Contact Policy | Global suppression limits applied during arbitration |
