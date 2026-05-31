# Pega CDH — Value Finder: Complete Reference Guide

## Overview

Value Finder is a strategic analysis component within Pega CDH that identifies mismatches between a customer's business value to the organisation and the level of engagement CDH is delivering to that customer. It surfaces actionable revenue opportunities that the current NBA strategy is missing.

The core insight Value Finder provides: not all high-value customers are receiving high engagement, and not all low-value customers should be receiving expensive interactions.

---

## The Value-Engagement Matrix

Value Finder plots every customer segment on a 2×2 matrix:

```
High Value │ UNDERSERVED          │ BALANCED
           │ ← Top opportunity   │ ← Keep doing this
           │ High value,          │ High value,
           │ low engagement       │ high engagement
           ├──────────────────────┼────────────────────
Low Value  │ LOST                 │ OVERSERVED
           │ Low value,           │ ← Cost risk
           │ low engagement       │ Low value,
           │                      │ high engagement
           └──────────────────────┴────────────────────
                Low Engagement         High Engagement
```

### Quadrant Definitions

| Quadrant | Definition | Business Implication | Recommended Action |
|----------|-----------|---------------------|-------------------|
| **Underserved** | High value, low engagement | Top revenue opportunity — we are not serving these customers well | Increase NBA actions, improve personalisation, targeted campaigns |
| **Balanced** | High value, high engagement | Current strategy working well | Maintain; optimise specific actions |
| **Overserved** | Low value, high engagement | Cost risk — over-investing in low-return customers | Reduce contact frequency, shift to low-cost channels |
| **Lost** | Low value, low engagement | Review — some may have been high-value previously | Analyse churn; consider re-engagement or retirement |

---

## How Value Finder Calculates Scores

### Value Score

The Value Score measures the business value of a customer or segment. It is derived from:

| Input | Description | Weight |
|-------|-------------|--------|
| Current product revenue | Net revenue from existing products | 40% |
| Predicted lifetime value | CLV model prediction | 30% |
| Cross-sell opportunity | Products customer is eligible for but does not hold | 20% |
| Retention risk adjustment | Probability of churn × revenue at risk | 10% |

Value Score is normalised to 0–100 across all customers.

### Engagement Score

The Engagement Score measures how actively CDH is serving the customer. It is derived from:

| Input | Description | Weight |
|-------|-------------|--------|
| NBA impressions (30 days) | Number of times customer was served an action | 35% |
| Accept rate | Customer's responsiveness to actions | 25% |
| Channel coverage | Number of channels used to reach this customer | 20% |
| Recency | Days since last interaction (inverted — recent = high score) | 20% |

Engagement Score is normalised to 0–100 across all customers.

### Engagement Gap

```
Engagement Gap = Value Score − Engagement Score
```

| Gap Range | Classification | Priority |
|-----------|---------------|----------|
| > 30 | Severely Underserved | Critical |
| 15 – 30 | Underserved | High |
| -15 – 15 | Balanced | Monitor |
| -15 to -30 | Overserved | Review |
| < -30 | Severely Overserved | Urgent Cost Review |

---

## Value Finder Output Fields

The Value Finder exports a dataset with one row per customer segment.

| Field | Description | Use in Analysis |
|-------|-------------|----------------|
| SegmentID | Unique segment identifier | Join key |
| SegmentName | Human-readable segment label | Display |
| CustomerCount | Number of customers in segment | Scale weighting |
| ValueScore | Business value score [0–100] | Y-axis on matrix |
| EngagementScore | CDH engagement level [0–100] | X-axis on matrix |
| EngagementGap | ValueScore − EngagementScore | Opportunity rank |
| TopActions | Recommended actions for this segment | Campaign targeting |
| Channel | Recommended channel | Channel selection |
| OpportunityValue | £ revenue potential if gap closed | Business case |
| Quadrant | Underserved/Overserved/Balanced/Lost | Categorisation |
| SnapshotDate | Date Value Finder ran | Trend analysis |

---

## Running Value Finder

### Standard Run (Monthly)

```
CDH > Value Finder > New Analysis
Analysis Type: Full Population
Segmentation: Customer Tier + Product Holdings
Snapshot Date: [Current date]
```

### Segment-Specific Run

Target specific customer groups for focused analysis:

```
CDH > Value Finder > New Analysis
Analysis Type: Segment Specific
Filters:
  - Customer Tier = Gold, Platinum
  - Region = North West
  - Tenure > 24 months
```

### Scheduled Run

Automate monthly execution:
```
CDH > Value Finder > Schedule
Frequency: Monthly (1st of each month)
Notification: Strategy team distribution list
```

---

## Interpreting Value Finder Results

### Reading the Opportunity Table

Sort by EngagementGap descending to identify the highest opportunity segments:

| SegmentName | Customers | ValueScore | EngageScore | Gap | OppValue | Quadrant |
|-------------|-----------|------------|-------------|-----|----------|----------|
| Platinum Inactive | 2,341 | 87 | 23 | +64 | £2.1M | Underserved |
| Gold Savers | 8,902 | 72 | 31 | +41 | £1.4M | Underserved |
| High-Income Young | 5,612 | 68 | 28 | +40 | £890K | Underserved |
| Mid-Tier Digital | 22,441 | 55 | 60 | -5 | — | Balanced |
| Retired Low Balance | 18,332 | 22 | 68 | -46 | — | Overserved |
| New to Bank | 9,112 | 18 | 12 | +6 | £120K | Lost/Review |

**Key insight from this table:**
- Platinum Inactive: 2,341 customers worth £2.1M opportunity — top priority
- Retired Low Balance: Overserved — costs being incurred with no value return

### Calculating Total Revenue Opportunity

```
Total Underserved Opportunity = SUM(OpportunityValue WHERE Quadrant = 'Underserved')

Realistic capture rate: 20–40% (depends on action effectiveness)

Realistic Revenue Opportunity = Total Opportunity × Capture Rate

Example:
Total Opportunity: £4.51M
Capture Rate: 30%
Realistic Revenue: £1.35M/year
```

---

## Acting on Value Finder Results

### Step 1 — Prioritise Segments

Rank underserved segments by:
```
Priority Score = OpportunityValue × (1/CustomerCount) × (1/EngagementGap)
```

This gives preference to high-value segments with large gaps that can be addressed with focused campaigns.

### Step 2 — Design Targeted Actions

For each top underserved segment, design specific NBA actions:

| Segment | Current Engagement | Recommended Action | Channel | Expected Lift |
|---------|-------------------|-------------------|---------|--------------|
| Platinum Inactive | 1 impression/month | Personalised relationship manager call | CallCentre | +45% engagement |
| Gold Savers | Email only | Cross-sell investment products | Web + Email | +28% accept rate |
| High-Income Young | No digital engagement | Mobile app feature promotion | Mobile | +35% activation |

### Step 3 — Update Arbitration Weights

For underserved segments, temporarily increase the weight of recommended actions:

```
CDH > Arbitration > Levers > Add Lever
Condition: CustomerSegment = "Platinum Inactive"
Action: Relationship_Manager_Call
Weight Multiplier: 3.0 (triple the normal selection rate)
Duration: 90 days
Review: Monthly via Value Finder re-run
```

### Step 4 — Measure Progress

Run Value Finder monthly and track:
- Has EngagementGap for target segments decreased?
- Has OpportunityValue been captured (Actuals Dataset)?
- Are targeted segments moving from Underserved to Balanced?

---

## Value Finder and Interaction History Integration

Value Finder reads Interaction History to calculate the Engagement Score. This means:

- If IH is not capturing all channels, the Engagement Score will be understated
- Dark channel interactions (branch visits, ATM usage) not captured in IH will show customers as lower engagement than they are
- Ensure all customer touchpoints are captured in IH for accurate Value Finder analysis

### IH Fields Used by Value Finder

| IH Field | Used For |
|----------|---------|
| SubjectID | Customer identification |
| pxDecisionTime | Recency calculation |
| Channel | Channel coverage calculation |
| Outcome | Accept rate calculation (impressions vs accepts) |
| ActionName | Action variety measure |

---

## Value Finder Segments in NBA Strategy

### Using Segment Tags in Engagement Policy

Value Finder quadrant assignments can be written back to the customer profile and used in eligibility rules:

```
CDH > Data Management > Value Finder Write-Back
Write segment quadrant to: Customer.ValueFinderQuadrant

Use in Engagement Policy:
Eligibility condition: Customer.ValueFinderQuadrant = "Underserved"
```

This creates a closed-loop system where:
1. Value Finder identifies underserved customers
2. Their profile is tagged as Underserved
3. NBA strategy eligibility rules activate targeted actions for Underserved customers
4. Engagement Score increases
5. Value Finder re-run shows segment moving to Balanced

---

## Overserved Segments — Cost Reduction

For Overserved segments, reduce contact frequency to lower cost-to-serve:

**Approach A — Channel Downgrade**
```
Segment: Retired Low Balance
Current: Email + SMS + Push (£8/year contact cost)
Proposed: Email only (£2/year contact cost)
Saving: £6 × 18,332 customers = £109K/year
```

**Approach B — Contact Frequency Reduction**
```
Segment: Retired Low Balance
Current: Contact policy allows 5/week
Proposed: Limit to 1/week for this segment
Implementation: CDH > Contact Policy > Segment Override
```

**Approach C — Lower-Cost Actions**
```
Replace high-cost outbound (call centre) actions
with low-cost self-serve digital actions for overserved segments
```

---

## Value Finder Report — Standard Template

### Section 1: Executive Summary
```
Total customers analysed: [N]
Underserved segments: [N] segments, [N] customers, £[M] opportunity
Overserved segments: [N] segments, [N] customers, £[K] cost risk
Balanced segments: [N] segments, [N] customers
Key opportunity: [Top segment name] — [£M] potential
```

### Section 2: Opportunity Rankings
Table sorted by OpportunityValue descending, top 10 underserved segments.

### Section 3: Cost Risk
Table sorted by Overserved gap descending, segments generating cost with low return.

### Section 4: Recommended Actions
Specific NBA actions recommended per top-5 underserved segment.

### Section 5: Progress vs Last Period
Compare current Value Score and Engagement Score to previous month.
Track segments moving between quadrants.

---

## Key Performance Indicators — Value Finder

Track these monthly:

| KPI | Formula | Target |
|-----|---------|--------|
| % customers in Balanced quadrant | Balanced / Total | > 50% |
| % customers in Underserved | Underserved / Total | Decrease month-on-month |
| Total Underserved Opportunity | SUM(OpportunityValue, Underserved) | Decrease as gaps close |
| Overserved Cost Risk | SUM(ContactCost × CustomerCount, Overserved) | Decrease month-on-month |
| Avg Engagement Gap | AVG(ABS(EngagementGap)) | Decrease towards 0 |
| Segments moved to Balanced | Count segments transitioning | Increase month-on-month |

---

## Troubleshooting Value Finder

| Issue | Cause | Fix |
|-------|-------|-----|
| All customers show in Lost quadrant | Value Score calculation not configured | Check Value Components configuration |
| Engagement Score = 0 for all | IH not connected | Verify IH data flow is active |
| High-value customers show Balanced but accept rate is 0 | Engagement is impressions, not accepts | Review action content and targeting |
| OpportunityValue = 0 for all segments | Value not configured on actions | Set Value on all actions |
| Value Finder shows same result every month | IH data not refreshing | Check IH pipeline schedule |
| Underserved customers not receiving more actions | Segment tag not written back to profile | Enable Value Finder Write-Back |
