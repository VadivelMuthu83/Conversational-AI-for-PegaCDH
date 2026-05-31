# CDH NBA Strategy — Performance Benchmarks and KPI Reference

## Article Purpose
Definitive reference for all Pega CDH performance metrics, benchmarks,
alert thresholds, and KPI calculation methods. Use this article to
answer questions about what "good" looks like across all CDH components.

---

## Accept Rate Benchmarks

Accept rate = Accepted / Impressions (for a given action/channel/period)

### By Channel — Industry Benchmarks

| Channel | Poor | Below Average | Average | Good | Excellent |
|---------|------|--------------|---------|------|-----------|
| CallCentre (inbound) | < 5% | 5–10% | 10–18% | 18–30% | > 30% |
| CallCentre (outbound) | < 2% | 2–5% | 5–10% | 10–18% | > 18% |
| Web (personalised) | < 2% | 2–5% | 5–10% | 10–15% | > 15% |
| Mobile App | < 2% | 2–6% | 6–12% | 12–18% | > 18% |
| Email | < 1% | 1–3% | 3–6% | 6–10% | > 10% |
| SMS | < 0.5% | 0.5–2% | 2–4% | 4–7% | > 7% |
| Push Notification | < 0.5% | 0.5–2% | 2–4% | 4–6% | > 6% |

### By Product Category

| Product Type | Typical Accept Rate Range |
|-------------|--------------------------|
| Credit Card (upgrade existing customer) | 8–15% |
| Credit Card (new to card) | 3–8% |
| Personal Loan (pre-approved) | 12–25% |
| Personal Loan (standard) | 4–10% |
| Insurance (home) | 5–12% |
| Insurance (travel) | 8–18% |
| Savings Account | 6–14% |
| Mortgage (existing customer) | 2–6% |
| Investment / ISA | 3–8% |

---

## ADM Model Performance Benchmarks

### AUC Benchmarks by Model Maturity

| Response Count | Expected AUC Range | Note |
|---|---|---|
| < 200 | 0.50–0.60 | Insufficient data — AUC unreliable |
| 200–500 | 0.55–0.68 | Naive Bayes phase; improving |
| 500–2,000 | 0.62–0.75 | Gradient Boost phase; reliable |
| 2,000–10,000 | 0.68–0.82 | Mature model; high confidence |
| > 10,000 | 0.72–0.88 | Fully mature; diminishing returns |

### Model KPI Summary Table

| Metric | Calculation | Good | Alert |
|--------|------------|------|-------|
| AUC | ROC curve area | > 0.70 | < 0.60 |
| Top Decile Lift | Decile 1 AR / Base AR | > 3.0 | < 2.0 |
| Positivity Rate | Positive / Total responses | 2–15% | < 0.5% or > 40% |
| Active Predictors | Count of Active status predictors | 5–15 | 0 |
| Response Count | Total training responses | > 500 | < 200 |
| AUC Weekly Change | Current − Last week AUC | |ΔAUCl < 0.02 | > 0.05 drop |

---

## Interaction History Volume Benchmarks

### Expected IH Volume Indicators

| Metric | Calculation | Healthy Range |
|--------|------------|--------------|
| Impressions/customer/month | Total impressions / active customers | 4–20 |
| Accepts/customer/month | Total accepts / active customers | 0.5–2.0 |
| Channel coverage | Channels used per customer per month | 2–4 |
| Impression:Accept ratio | Impressions / Accepts | 7:1 to 30:1 |
| IH records/day | COUNT(*) from yesterday's IH | Stable ±20% |

### IH Data Quality KPIs

| Metric | Formula | Target |
|--------|---------|--------|
| Outcome completeness | Outcomes recorded / Impressions | > 95% |
| Real-time capture rate | Outcomes captured within 1hr / total | > 80% (digital) |
| CustomerID match rate | IH SubjectID found in CRM / total | > 99% |
| Propensity coverage | IH rows with non-null Propensity | > 99.5% |
| Duplicate IH rate | Duplicate pxInteractionIDs | 0% |

---

## Value Finder Benchmarks

### Quadrant Distribution Targets

| Quadrant | Target % of Customers |
|----------|----------------------|
| Balanced | > 50% |
| Underserved | < 25% (and decreasing) |
| Overserved | < 15% (and decreasing) |
| Lost | < 20% |

### Engagement Gap KPIs

| Metric | Formula | Target |
|--------|---------|--------|
| Avg Engagement Gap | AVG(ABS(ValueScore − EngagementScore)) | Decreasing MoM |
| Underserved Opportunity | SUM(OpportunityValue WHERE Quadrant='Underserved') | Decreasing MoM |
| Coverage Improvement | % Balanced customers MoM change | Positive |

---

## Contact Policy KPIs

| Metric | Calculation | Target | Alert |
|--------|------------|--------|-------|
| Avg contacts/customer/week | Total impressions / active customers / weeks | 2–4 | > 6 |
| Contact policy block rate | Contact policy blocks / total attempts | < 15% | > 30% |
| Channel concentration | % impressions on top channel | < 50% | > 70% |
| Opt-out rate (email) | Email opt-outs / email impressions | < 2% | > 5% |
| Suppression rate | Suppressed / total decisions | 10–30% | > 50% |

---

## Arbitration KPIs

| Metric | Formula | Target | Alert |
|--------|---------|--------|-------|
| Decision latency (P95) | 95th percentile response time | < 200ms | > 500ms |
| Eligible action count | Avg eligible actions per interaction | 3–10 | < 2 |
| Zero-eligible rate | Interactions with 0 eligible actions | < 2% | > 5% |
| Action concentration | % impressions for single top action | < 35% | > 50% |
| Avg Priority score | AVG(Priority) across all decisions | Monitor trend | Sudden drop |

---

## Champion / Challenger KPIs

| KPI | Target | Minimum Threshold Before Decision |
|-----|--------|----------------------------------|
| Impressions per group | > 1,000 | 500 (minimum) |
| Test duration | > 14 days | 7 days (minimum) |
| Accept rate difference | > 1% absolute for promotion | Any positive for continued test |
| Statistical significance | p < 0.05 | p < 0.10 for continued test |
| Revenue per impression | Champion ≤ Challenger | No regression |

---

## Full CDH Dashboard Metric Reference

### Daily Dashboard (Operations)

| Metric | Source | Alert Condition |
|--------|--------|----------------|
| Total impressions | IH | ±20% vs 7-day average |
| Overall accept rate | IH + Actuals | Drop > 15% |
| Decision latency P95 | CDH performance log | > 500ms |
| IH write success | CDH health | < 99.9% |
| Outcome pipeline status | Outcome pipeline log | Any failure |

### Weekly Dashboard (Strategy)

| Metric | Source | Alert Condition |
|--------|--------|----------------|
| Accept rate by action | IH + Actuals | Any action drop > 20% |
| Accept rate by channel | IH + Actuals | Any channel drop > 20% |
| ADM model AUC | ADM Snapshot | Any model < 0.60 |
| Top 5 / Bottom 5 actions | IH + Actuals | Bottom 5 accept rate < 2% |
| Contact policy block rate | Decision Audit | > 30% |
| Zero-eligible rate | Decision Audit | > 5% |

### Monthly Dashboard (Leadership)

| Metric | Source | Target |
|--------|--------|--------|
| NBA revenue attribution | Actuals | vs plan |
| Accept rate trend | Actuals | Improving |
| ADM model portfolio health | ADM Snapshot | > 85% models with AUC > 0.65 |
| Value Finder opportunity | Value Finder | Decreasing |
| % customers in Balanced quadrant | Value Finder | > 50% |
| Champion/Challenger wins | C/C results | > 50% challengers improve |

---

## Revenue Attribution Formula

```
Monthly CDH Revenue Attribution =
    SUM(ConversionValue) for all accepted actions in the month

WHERE:
    ConversionValue = actual revenue captured in Actuals Dataset
    OR
    ConversionValue = Estimated value (if direct revenue not captured):
        Accepted × ProductValue × RevenueRecognitionFactor

RevenueRecognitionFactor:
    Credit Card:     0.08 (8% of credit limit × 12 months)
    Personal Loan:   0.05 × LoanAmount (5% annual interest margin)
    Insurance:       0.85 × AnnualPremium (85% after claims ratio)
    Savings:         0.01 × Balance (1% margin on deposits)
```

---

## Benchmarking Against Industry Standards

### Personalisation Effectiveness

| Maturity Level | Accept Rate | ADM AUC | Actions per Customer |
|---------------|------------|---------|---------------------|
| Basic (rules-based) | 2–4% | N/A | 1–2 |
| Intermediate (segment-based) | 4–7% | 0.60–0.68 | 3–5 |
| Advanced (individual ADM) | 7–12% | 0.68–0.78 | 5–10 |
| Leader (full real-time AI) | 12–20% | 0.75–0.88 | 8–15 |

### What Drives Maturity Improvement

Progressing from Basic to Intermediate:
→ Implement ADM models for top 10 actions
→ Configure hybrid arbitration (not just segment rules)
→ Connect real-time web signals to CDH

Progressing from Intermediate to Advanced:
→ Expand ADM to all action×channel combinations
→ Implement Champion/Challenger for all significant changes
→ Connect CRM and behavioural data as predictors
→ Implement real-time outcome capture

Progressing from Advanced to Leader:
→ Add life event detection to context rules
→ Implement next-best-channel recommendation
→ Integrate Value Finder into ongoing arbitration strategy
→ Add explainability monitoring for fairness compliance
→ Deploy predictive churn signals as suppression rules
