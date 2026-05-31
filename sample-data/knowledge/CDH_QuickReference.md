# Pega CDH — Quick Reference Card

## Core Formulas

| Formula | Expression |
|---------|-----------|
| Arbitration Priority | Value × Propensity × Weight × ContextWeight |
| Accept Rate | Accepts / Impressions |
| Lift (decile) | Decile Accept Rate / Overall Accept Rate |
| Engagement Gap | Value Score − Engagement Score |
| Calibration Error | ABS(Predicted Accept Rate − Actual Accept Rate) |
| Revenue per Impression | Total Revenue / Total Impressions |
| Model Positivity | Positive Responses / Total Responses |

---

## AUC Thresholds

| AUC | Rating | Action |
|-----|--------|--------|
| > 0.90 | Exceptional — check for overfitting | Investigate |
| 0.80–0.90 | Excellent | Promote to production |
| 0.70–0.80 | Good | Monitor quarterly |
| 0.60–0.70 | Fair | Review predictors |
| 0.50–0.60 | Poor | Retrain immediately |
| < 0.50 | Failing | Disable model |

---

## Response Count Requirements

| Count | Reliability |
|-------|------------|
| < 200 | Very Low — do not use for important decisions |
| 200–500 | Low — use Naive Bayes |
| 500–2,000 | Medium — switch to Gradient Boosting |
| > 2,000 | High — reliable model |

---

## Value Finder Quadrants

| Quadrant | Value | Engagement | Action |
|----------|-------|-----------|--------|
| Underserved | High | Low | Increase NBA intensity |
| Balanced | High | High | Maintain strategy |
| Overserved | Low | High | Reduce contact cost |
| Lost | Low | Low | Review or retire |

---

## Channel Response Windows

| Channel | Response Window |
|---------|----------------|
| Web/Mobile | 30 minutes |
| Email | 7 days |
| SMS | 48 hours |
| Push | 72 hours |
| CallCentre | During call |

---

## Standard Contact Policy Limits

| Scope | Limit |
|-------|-------|
| All channels | 7 per customer per week |
| Email | 2 per week |
| SMS | 1 per week |
| Push | 5 per week |
| Outbound calls | 1 per week |

---

## Suppression Windows

| Trigger | Suppression Period |
|---------|-------------------|
| Impression | 7 days |
| Rejection | 30 days |
| Acceptance | Permanent |
| Complaint | Until complaint closed + 30 days |

---

## IH Key Fields

```
pxInteractionID  — unique event ID
SubjectID        — customer identifier
ActionName       — action presented
Channel          — delivery channel
Outcome          — Impression/Accepted/Rejected/NoResponse
Propensity       — ADM score [0,1]
Priority         — arbitrated priority
pxDecisionTime   — when decision was made
ExperimentGroup  — Champion or Challenger
```

---

## Outcome Values

| Outcome | ADM Signal | Analysis Count |
|---------|-----------|----------------|
| Impression | Pending | Denominator |
| Accepted | Positive (strong) | Numerator |
| Converted | Positive (strong) | Numerator |
| Clicked | Positive (weak) | Numerator (partial) |
| Rejected | Negative | Denominator |
| NoResponse | Negative (weak) | Denominator |

---

## Key Alert Thresholds

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| Accept rate drop | > 15% week-on-week | Investigate immediately |
| Model AUC drop | > 0.05 in 30 days | Review model and data pipeline |
| IH match rate | < 95% | Fix outcome pipeline |
| Zero-eligible rate | > 2% | Broaden eligibility rules |
| Decision latency (web) | > 500ms | Check CDH performance |
| Top action concentration | > 40% | Diversify arbitration |
| Calibration error | > 10% per decile | Recalibrate model |

---

## Engagement Policy Decision Tree

```
Is this about customer's fundamental qualification?
  YES → Eligibility rule

Is this about the current interaction context?
  YES → Applicability rule

Is this about business/regulatory constraints?
  YES → Suitability rule

Is this about how often we contact?
  YES → Contact Policy

Is this about action priority vs other actions?
  YES → Arbitration (Value, Weight, Propensity)
```

---

## CDH Navigation Quick Reference

| Task | Path |
|------|------|
| View all ADM models | CDH > Adaptive Models |
| Export ADM snapshot | CDH > Adaptive Models > Export |
| Run Value Finder | CDH > Value Finder > New Analysis |
| Run Impact Analyzer | CDH > Impact Analyzer > New Analysis |
| Decision Audit | CDH > Tools > Decision Audit |
| Edit engagement policy | CDH > NBA Designer > Engagement Policy |
| Configure contact policy | CDH > Contact Policy |
| Manage IH retention | CDH > Data Management > IH Retention |
| Export IH data | CDH > Data Management > IH Export |
| Upload actuals | CDH > Data Management > Outcome Upload |
| Configure channels | CDH > Channels |
| View champion/challenger | CDH > Adaptive Models > Champion Challenger |
| Rebuild policy index | CDH > Admin > Rebuild Policy Index |
