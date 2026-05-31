# CDH Engagement Policy — Rule Authoring and Coverage Analysis

## Article Purpose
Practical guide for writing, testing, and maintaining Engagement Policy rules.
Includes decision trees for every rule type, real Pega expression syntax,
coverage analysis queries, and governance procedures.

---

## Engagement Policy Architecture

The Engagement Policy is evaluated in strict sequence for every action candidate:

```
All strategy actions
        ↓
[1] ELIGIBILITY CHECK
    "Can this customer ever receive this action?"
        ↓ (pass)
[2] APPLICABILITY CHECK
    "Is this action right for this specific context?"
        ↓ (pass)
[3] SUITABILITY CHECK
    "Are business/regulatory constraints satisfied?"
        ↓ (pass)
[4] ARBITRATION
    Priority = Value × Propensity × Weight × ContextWeight
        ↓
Selected action(s)
```

A FAIL at any layer removes the action from the candidate pool.
The reason is logged in Decision Audit as ELIGIBILITY_FAILED,
APPLICABILITY_FAILED, or SUITABILITY_FAILED.

---

## Eligibility Rules — Complete Reference

### Rule Purpose
Eligibility defines the permanent conditions a customer must meet to
ever be eligible for an action. These conditions should be the same
regardless of channel, time of day, or current session behaviour.

### Eligibility Rule Examples (Pega Expression Syntax)

#### Age Restriction
```
// Credit card — must be 18+
@Customer.Age >= 18

// Premium product — 25+ years required
@Customer.Age >= 25 AND @Customer.Age <= 75
```

#### Account Status
```
// Active account holder only
@Customer.AccountStatus == "Active"

// No recent defaults
@Customer.AccountStatus == "Active"
AND @Customer.DaysSinceLastDefault == null
OR @Customer.DaysSinceLastDefault > 365
```

#### Existing Product Exclusion
```
// Don't offer credit card to customers who already have one
NOT @Customer.HoldsCreditCard

// Don't offer Personal Loan if customer has 3+ credit products
@Customer.TotalCreditProducts < 3

// Cross-sell: must hold current account to be eligible for savings
@Customer.HoldsCurrentAccount
```

#### Geographic Restriction
```
// UK residents only
@Customer.CountryOfResidence == "GB"

// Exclude certain postcodes under regulatory guidance
NOT (@Customer.PostcodeArea IN {"SW1", "EC1", "WC2"})
```

#### Income Threshold
```
// Minimum income for premium products
@Customer.AnnualIncome >= 30000

// Dynamic income eligibility using value component
@Customer.AnnualIncome >= .GetMinimumIncomeThreshold()
// Where GetMinimumIncomeThreshold() looks up from a threshold table
```

#### Tenure
```
// Must have been a customer for at least 6 months
@Customer.TenureMonths >= 6
```

### When Eligibility Is Too Restrictive

Run monthly to check eligibility coverage:

```sql
-- What % of customers are eligible for each action?
-- If < 10%: rules may be too restrictive
-- If > 90%: rules may be too permissive

SELECT
    ActionName,
    COUNT(*) AS TotalCustomers,
    SUM(CASE WHEN EligibilityPass = 1 THEN 1 ELSE 0 END) AS EligibleCount,
    CAST(SUM(CASE WHEN EligibilityPass = 1 THEN 1 ELSE 0 END) AS FLOAT)
        / COUNT(*) AS EligibilityRate,
    CASE
        WHEN CAST(SUM(CASE WHEN EligibilityPass=1 THEN 1 ELSE 0 END) AS FLOAT)
             / COUNT(*) < 0.10 THEN '⚠ Very restrictive — review'
        WHEN CAST(SUM(CASE WHEN EligibilityPass=1 THEN 1 ELSE 0 END) AS FLOAT)
             / COUNT(*) > 0.90 THEN '⚠ Very permissive — review'
        ELSE '✅ OK'
    END AS Status
FROM DecisionAuditLog
GROUP BY ActionName
ORDER BY EligibilityRate;
```

---

## Applicability Rules — Complete Reference

### Rule Purpose
Applicability rules filter based on the real-time interaction context.
They answer: "Is presenting this action appropriate RIGHT NOW for this interaction?"

### Applicability Rule Examples

#### Channel Matching
```
// Only show via digital channels — not call centre
@Interaction.Channel IN {"Web", "Mobile", "Email", "SMS", "Push"}

// Only for inbound interactions
@Interaction.Direction == "Inbound"
```

#### Session Signals
```
// Customer visited the product page in this session
@Session.LastPageViewed == "CreditCards"

// High intent signal — 3+ visits to product pages
@Session.ProductPageVisitCount >= 3

// Customer initiated from specific entry point
@Session.EntryPoint == "Marketing_Email_Jan2024"
```

#### Time and Date Applicability
```
// Business hours only (8am–8pm)
@CurrentDateTime.Hour >= 8 AND @CurrentDateTime.Hour < 20

// Campaign period
@CurrentDate >= Date(2024, 6, 1) AND @CurrentDate <= Date(2024, 8, 31)

// Exclude public holidays (using a lookup table)
NOT @IsPublicHoliday(@CurrentDate)
```

#### No Open Interactions of Same Type
```
// Don't re-offer if application is in progress
NOT EXISTS(.OpenCases[pyWorkStatus != "Resolved" AND pxObjClass == "CreditCard-Application"])

// Don't offer if customer was shown this action in this session
NOT @Session.ActionsShown CONTAINS "Gold_Card_Offer"
```

#### Customer Journey State
```
// Onboarding — only for customers in first 90 days
@Customer.TenureMonths <= 3

// Post-product-activation — cross-sell after product is active
@Customer.ProductActivatedDate != null
AND DATEDIFF(day, @Customer.ProductActivatedDate, @CurrentDate) <= 60
```

---

## Suitability Rules — Complete Reference

### Rule Purpose
Suitability rules apply business and regulatory constraints that must
be satisfied before an action is appropriate to present. These typically
reflect compliance requirements, responsible lending/selling obligations,
and credit risk management.

### Suitability Rule Examples

#### Affordability and Credit Risk
```
// Debt-to-income ratio check (responsible lending)
@Customer.TotalMonthlyDebt / @Customer.MonthlyIncome <= 0.45

// Credit score minimum
@Customer.CreditScore >= 650

// No recent missed payments
@Customer.MissedPayments3Months == 0

// Maximum total credit exposure
@Customer.TotalCreditLimit + 5000 <= 50000
// (5000 is the credit limit of the action being offered)
```

#### Complaints and Disputes
```
// No active complaint
NOT @Customer.HasActiveComplaint

// No complaint within last 30 days
@Customer.DaysSinceComplaintClosed == null
OR @Customer.DaysSinceComplaintClosed >= 30

// No fraud flag
NOT @Customer.FraudFlag
```

#### Regulatory Cooling-Off
```
// Insurance cooling-off — 14 days after previous sale
@Customer.LastInsurancePurchaseDate == null
OR DATEDIFF(day, @Customer.LastInsurancePurchaseDate, @CurrentDate) >= 14

// Post-rejection cooling-off — don't reapply within 90 days
@Customer.LastApplicationDate == null
OR DATEDIFF(day, @Customer.LastApplicationDate, @CurrentDate) >= 90
```

#### Vulnerability Checks
```
// Standard vulnerable customer check
NOT @Customer.VulnerabilityFlag

// Conditional — some actions allowed even for vulnerable customers
// (e.g. debt management, budget account — these help vulnerable customers)
NOT @Customer.VulnerabilityFlag
OR @Action.IsVulnerabilityAppropriate
```

#### Maximum Product Count
```
// No more than 2 credit cards
@Customer.CreditCardCount < 2

// No more than 3 insurance policies of same type
@Customer.TravelInsurancePolicyCount < 3
```

---

## Contact Policy — Precise Configuration

### Global Policy
```
CDH > Contact Policy > Global Settings

Max contacts per customer per rolling 7 days: 5
Max contacts per customer per rolling 24 hours: 2

Per channel limits (rolling 7 days):
  Email:           2
  SMS:             1
  Push:            4
  Outbound Call:   1
  Web/Mobile:      Unlimited (inbound channel — excluded from count)
  Print:           1 (monthly)
```

### How Rolling Windows Work

CDH counts interactions in a rolling window, not a fixed calendar week.

```
Example: Customer contacted Monday, Tuesday, Wednesday, Thursday (4 total)
  Next contact attempt: Friday
  Rolling 7-day window includes Mon–Fri: 4 contacts
  Global limit is 5 → Friday contact ALLOWED

  Next contact attempt: Saturday
  Rolling 7-day window includes Tue–Sat: 4 contacts
  Global limit is 5 → Saturday contact ALLOWED

  Next contact attempt: Sunday
  Rolling 7-day window includes Wed–Sun: 4 contacts
  Still allowed (limit = 5, used = 4)
```

### Suppression Configuration

Per-action post-impression suppression:

```
CDH > [Action] > Engagement Policy > Suppression

After Impression:  7 days (don't show same action again for 7 days)
After Rejection:   30 days (customer explicitly said no)
After Acceptance:  Permanent (customer already has the product)
After Conversion:  Permanent
After NoResponse:  3 days (slightly shorter than rejection)
```

### Segment-Specific Contact Policy Overrides

```
CDH > Contact Policy > Segment Overrides

Segment: Vulnerable Customers
Condition: Customer.VulnerabilityFlag = true
Override: max 1 contact per week, Email only, no SMS/Push/Outbound

Segment: Marketing Opt-Out
Condition: Customer.MarketingConsent = false
Override: max 0 outbound marketing contacts
  (Note: Service interactions are NOT marketing — exempt from this override)

Segment: Opted-In to More Contacts
Condition: Customer.PreferenceContactFrequency = "High"
Override: max 10 contacts per week (customer preference)
```

---

## Coverage Analysis — Finding Policy Gaps

### Analysis 1: Why Are Customers Not Receiving Any Action?

```sql
-- Customers with interactions but no actions served
SELECT
    SubjectID AS CustomerID,
    COUNT(*) AS TotalAttempts,
    SUM(CASE WHEN EligibilityPass = 0 THEN 1 ELSE 0 END) AS EligibilityFails,
    SUM(CASE WHEN ApplicabilityPass = 0 THEN 1 ELSE 0 END) AS ApplicabilityFails,
    SUM(CASE WHEN SuitabilityPass = 0 THEN 1 ELSE 0 END) AS SuitabilityFails,
    SUM(CASE WHEN ContactPolicyFail = 1 THEN 1 ELSE 0 END) AS ContactPolicyFails,
    MAX(ExclusionReason) AS TopExclusionReason
FROM DecisionAuditLog
WHERE InteractionDate >= DATEADD(day, -30, GETDATE())
GROUP BY SubjectID
HAVING SUM(CASE WHEN ActionServed = 1 THEN 1 ELSE 0 END) = 0
ORDER BY TotalAttempts DESC;
```

### Analysis 2: Which Rule Is Blocking the Most Customers?

```sql
SELECT
    PolicyLayer,       -- Eligibility / Applicability / Suitability
    RuleName,          -- Specific rule that failed
    ActionName,
    COUNT(DISTINCT CustomerID) AS CustomersBlocked,
    COUNT(*) AS BlockedAttempts
FROM DecisionAuditLog
WHERE InteractionDate >= DATEADD(day, -7, GETDATE())
  AND ActionServed = 0
GROUP BY PolicyLayer, RuleName, ActionName
ORDER BY CustomersBlocked DESC;
```

### Analysis 3: Eligible Customer Coverage

```sql
-- What fraction of the customer base can receive at least one action?
SELECT
    CAST(COUNT(DISTINCT CustomerID) AS FLOAT)
        / (SELECT COUNT(DISTINCT CustomerID) FROM CustomerProfile)
        AS EligibleCustomerRate,
    COUNT(DISTINCT CustomerID) AS EligibleCustomers,
    COUNT(DISTINCT ActionName) AS AvgEligibleActionsPerCustomer
FROM (
    SELECT CustomerID, ActionName
    FROM DecisionAuditLog
    WHERE EligibilityPass = 1
      AND InteractionDate >= DATEADD(day, -7, GETDATE())
) EligibleActions;
```

### Target Coverage Benchmarks

| Metric | Target | Alert If |
|--------|--------|---------|
| % customers with ≥ 1 eligible action | > 75% | < 60% |
| Avg eligible actions per customer | 3–8 | < 2 or > 15 |
| Contact policy block rate | < 20% of attempts | > 35% |
| Zero-action rate per interaction | < 2% | > 5% |

---

## Engagement Policy Change Management

### Change Classification

| Change Type | Approval Required | Impact Analyzer | Champion/Challenger |
|------------|-----------------|----------------|---------------------|
| Minor (text fix, typo) | Strategy designer | No | No |
| Eligibility rule change | Strategy manager | Recommended | No |
| Suitability rule change | Compliance + Strategy manager | Required | No |
| Contact policy change | Compliance + Strategy manager | Required | No |
| New action | Strategy manager | Recommended | Yes for first 4 weeks |
| Value change > 20% | Finance + Strategy manager | Required | Recommended |

### Pre-Deployment Test

Before deploying any Engagement Policy change:

```
1. Run coverage analysis on production data (read-only)
   → How many customers' eligibility changes?
   → Is the change direction expected?

2. Run Decision Audit on 10 sample customers
   → Verify expected customers pass/fail the new rule
   → Confirm no unexpected exclusions

3. Run Impact Analyzer (if applicable)
   → Quantify revenue impact of eligibility change

4. Confirm rule has correct expiry date set
   → Time-limited campaigns MUST have expiry

5. Confirm change is documented with:
   → Business rationale
   → Policy/regulatory reference
   → Author and approver names
   → Effective date
```
