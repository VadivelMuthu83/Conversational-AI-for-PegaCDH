# CDH Arbitration — Priority Formula Deep Dive and Worked Examples

## Article Purpose
This article provides exhaustive detail on how Pega CDH calculates the final
Arbitration Priority score for every action candidate. It covers the exact
formula, each component in isolation, realistic worked examples, edge cases,
and common miscalculations.

---

## The Exact Priority Formula

```
Priority = Value × Propensity × Weight × ContextWeight
```

All four components are multiplied together. If ANY component is zero, Priority = 0
and the action is immediately excluded from selection regardless of how strong the
other components are.

### Component Ranges and Defaults

| Component     | Minimum | Maximum  | Default | Configured In          |
|---------------|---------|----------|---------|------------------------|
| Value         | 0       | No limit | 0       | Action / Value Component |
| Propensity    | 0.001   | 1.0      | N/A     | ADM Model              |
| Weight        | 0       | No limit | 1.0     | Engagement Policy      |
| ContextWeight | 0       | No limit | 1.0     | Context Rules          |

---

## Component 1: Value

### What Value Represents
Value is the expected business benefit to the organisation if the customer
accepts this action. It is NOT the probability of acceptance — that is
Propensity. Value represents the worth of a successful outcome.

### How to Set Value

**Method A — Fixed monetary value (simplest)**
```
Action: Premium_Credit_Card
Value: 650
Basis: Average net annual revenue per credit card customer = £650
```

**Method B — Value Component (recommended for production)**
Value Components are reusable calculations attached to multiple actions.

```
CDH > Value Components > New Component
Name: CreditCard_LTV_Value
Expression:
  IF Customer.CreditScore > 750
    THEN 800
  ELSE IF Customer.CreditScore > 700
    THEN 650
  ELSE IF Customer.CreditScore > 650
    THEN 500
  ELSE 350
```

This means high-credit-score customers generate more value from the same
credit card — the priority formula naturally favours them.

**Method C — Dynamic revenue calculation**
```
Action: Personal_Loan
Value Component: Loan_Revenue_Value
Expression:
  LoanAmount × InterestRate × TermYears × NetMarginFactor
  WHERE NetMarginFactor = 0.35
```

### Common Value Misconfiguration

| Problem | Symptom | Fix |
|---------|---------|-----|
| Value = 0 on all actions | Priority = 0, no actions selected | Set non-zero value on every action |
| All actions same value | Arbitration decided entirely by propensity | Differentiate value by product revenue |
| Value too high on one action | That action always wins regardless of propensity | Balance values proportionally |
| Value not updated after pricing change | Stale revenue figures in arbitration | Update Value Components when pricing changes |

---

## Component 2: Propensity

### What Propensity Represents
Propensity is the ADM model's estimate of the probability that THIS customer
will positively respond to THIS action on THIS channel. It ranges from 0.001
to 1.0.

### How Propensity Is Calculated (ADM Internals)

For a Gradient Boost model with three predictors:
```
Base rate (overall accept rate): 0.05 (5%)

Predictor adjustments:
  CreditScore = 720  → +0.08 (above average, increases propensity)
  Tenure = 48mo      → +0.04 (long-tenured, loyal customer)
  WebVisits = 12/mo  → +0.06 (high engagement signal)

Raw score: 0.05 + 0.08 + 0.04 + 0.06 = 0.23
Sigmoid transformation: σ(0.23) = 0.557

Final Propensity: 0.557
```

Note: This is a simplified illustration. Gradient Boost uses decision trees,
not additive linear terms. The sigmoid ensures output stays in [0,1].

### Propensity Floor
Pega CDH sets a propensity floor of 0.001 to prevent Priority = 0 for
new models with no data. This means unlearned models still participate in
arbitration at a very low level.

### Propensity vs Accept Rate — Critical Distinction

| Metric | Meaning | Typical Value |
|--------|---------|---------------|
| Propensity | Model prediction for this specific customer | 0.001–1.0 |
| Accept Rate | Historical average across all customers | 2%–15% |
| Lift | Propensity / Accept Rate | 1.0–10.0 |

A customer with Propensity = 0.42 is predicted to be 8.4× more likely to
accept than the average customer (if average accept rate = 5%).

---

## Component 3: Weight

### What Weight Represents
Weight is a business-controlled multiplier that strategy designers use to
adjust action competitiveness without changing the Value or Propensity.
Weight = 1.0 is neutral. Weight > 1.0 boosts the action. Weight < 1.0
suppresses it.

### Weight Use Cases

```
Scenario 1: New product launch — boost Credit Card for 90 days
Action: Premium_Credit_Card
Weight: 2.5
Effect: Priority × 2.5, Credit Card wins more arbitration slots
Duration: Campaign lever, expires after 90 days

Scenario 2: Regulatory review — temporarily suppress Payday Loan
Action: Payday_Loan_Offer
Weight: 0
Effect: Priority = 0, action never selected
Duration: Until compliance review complete

Scenario 3: A/B test equal exposure
Champion: Standard_Offer, Weight = 1.0
Challenger: New_Offer, Weight = 1.0
Effect: Actions compete equally; difference driven by propensity

Scenario 4: Premium channel boost
Action: Investment_Portfolio, Channel = CallCentre
Weight: 3.0
Effect: Investment actions heavily preferred in call centre
         (where conversion rate is highest)
```

### Weight Hierarchy — Which Level Wins

Weights can be set at four levels. More specific levels override broader ones.

```
Issue Weight (broadest)
  └── Group Weight
        └── Action Weight
              └── Action × Channel Weight (most specific, wins)

Example:
  Issue "Growth" Weight = 1.2
  Group "CreditCards" Weight = 0.8
  Action "Gold_Card" Weight = 1.5
  Gold_Card × Email Weight = 0.6

  Gold_Card selected via Web: Uses Action Weight = 1.5
  Gold_Card selected via Email: Uses Action×Channel Weight = 0.6
```

### Levers — Runtime Weight Adjustment

Levers allow authorised business users to change weights without a full
strategy deployment. Used for campaign management and rapid response.

```
CDH > Arbitration > Levers > Create Lever

Lever: HolidaySeason_TravelInsurance
Condition: CurrentDate BETWEEN '2024-06-01' AND '2024-08-31'
Target: Travel_Insurance_Offer
Weight Modifier: 3.0 (multiplicative with existing weight)
Activation: Business User self-service
```

---

## Component 4: ContextWeight

### What ContextWeight Represents
ContextWeight applies a situational multiplier based on real-time signals
about the customer's current state, intent, or life events.

### Context Rule Examples

```
Rule: HighPurchaseIntent
Trigger: Customer viewed product page ≥ 3 times in current session
ContextWeight: 2.0
Actions: All matching actions for that product category

Rule: LifeEvent_NewMortgage
Trigger: MortgageApplicationDate within last 90 days
ContextWeight: 1.8
Actions: Home_Insurance_Offer, Buildings_Cover, Contents_Insurance

Rule: AtRisk_LatePayment
Trigger: PaymentDueDate passed AND PaymentStatus = 'Pending'
ContextWeight: 0.1
Actions: ALL sales actions (suppress sales when customer is stressed)

Rule: InboundComplaint_SuppressAll
Trigger: CallReason = 'Complaint' AND Channel = 'CallCentre'
ContextWeight: 0
Actions: ALL sales actions (never sell during complaint call)

Rule: HighNetWorth
Trigger: Customer.AUM > 500000
ContextWeight: 1.5
Actions: Private_Banking_Offer, Investment_Portfolio
```

### ContextWeight vs Weight — When to Use Each

| Use Weight When | Use ContextWeight When |
|----------------|----------------------|
| Permanent strategy change | Temporary, session-level adjustment |
| Applies to all customers equally | Depends on current interaction signal |
| Campaign-level control | Real-time behavioural trigger |
| Set by strategy designer | Set by context rule author |

---

## Complete Worked Examples

### Example 1: Standard Arbitration — Customer A

**Customer profile:** 42 years old, £72K income, credit score 735, 6-year tenure,
Gold tier, visited credit cards page twice this session.

**Candidate actions:**

| Action | Value | Propensity | Weight | Context | Priority |
|--------|-------|-----------|--------|---------|----------|
| Gold_Card_Offer | 650 | 0.41 | 1.0 | 1.0 | **266.5** |
| Personal_Loan_5K | 420 | 0.28 | 1.2 | 1.0 | 141.1 |
| Balance_Transfer | 180 | 0.55 | 1.0 | 1.0 | 99.0 |
| Travel_Insurance | 130 | 0.38 | 1.0 | 1.0 | 49.4 |
| Savings_Account | 80 | 0.22 | 0.9 | 1.0 | 15.8 |

**Winner: Gold_Card_Offer** with Priority 266.5

Insight: Despite Balance_Transfer having highest propensity (0.55), Gold Card
wins because its Value (650) is much higher. Propensity alone does not determine
the winner — Value × Propensity × Weight must all be considered together.

---

### Example 2: Context Suppresses Sales — Customer B

**Scenario:** Same customer calls the call centre. Call reason detected as
complaint about charges.

Context rule fires: `InboundComplaint_SuppressAll` → ContextWeight = 0

| Action | Value | Propensity | Weight | Context | Priority |
|--------|-------|-----------|--------|---------|----------|
| Gold_Card_Offer | 650 | 0.41 | 1.0 | **0** | **0** |
| Personal_Loan | 420 | 0.28 | 1.2 | **0** | **0** |
| Balance_Transfer | 180 | 0.55 | 1.0 | **0** | **0** |
| Complaint_Resolution | 50 | 0.92 | 2.0 | 1.0 | 92.0 |
| Fee_Waiver_Offer | 30 | 0.78 | 1.5 | 1.0 | 35.1 |

**Winner: Complaint_Resolution** — all sales actions suppressed.

---

### Example 3: Weight Boost Overrides Propensity — Customer C

**Scenario:** Marketing has set Weight = 4.0 on new ISA_Product for Q1 campaign.

| Action | Value | Propensity | Weight | Context | Priority |
|--------|-------|-----------|--------|---------|----------|
| ISA_Product | 300 | 0.15 | **4.0** | 1.0 | **180.0** |
| Gold_Card_Offer | 650 | 0.41 | 1.0 | 1.0 | 266.5 |
| Personal_Loan | 420 | 0.28 | 1.2 | 1.0 | 141.1 |

**Winner: Gold_Card_Offer** still wins (266.5 > 180.0).

This shows that even a Weight = 4.0 boost cannot override a much higher
Value × Propensity product. To guarantee ISA wins, Weight would need to be
> 266.5 / (300 × 0.15) = 5.92, so Weight ≥ 6.0.

**Key insight:** Weight amplifies, but does not override, the natural ranking.
To guarantee selection use Weight = (Target Priority) / (Value × Propensity).

---

### Example 4: New Action with No ADM Data — Customer D

**Scenario:** New action "Premium_Reward_Card" launched today. ADM model has
no training data → Propensity defaults to base rate = 0.001.

| Action | Value | Propensity | Weight | Context | Priority |
|--------|-------|-----------|--------|---------|----------|
| Premium_Reward_Card | 700 | **0.001** | 5.0 | 1.0 | **3.5** |
| Gold_Card_Offer | 650 | 0.41 | 1.0 | 1.0 | 266.5 |

New action will almost never win despite high value and high weight because
propensity is at floor level. Solution: pre-populate the model with pilot data
or set a temporary fixed propensity until ADM has enough data (min 200 responses).

```
CDH > Adaptive Models > Premium_Reward_Card > Propensity Override
Override Type: Fixed value
Fixed Propensity: 0.12  (use industry average for similar products)
Duration: Until ResponseCount > 500
```

---

## Priority Debugging Checklist

When an expected action is not being selected:

```
Step 1: Check Value
  → Is Value > 0?
  → Is the Value Component configured and returning a number?
  → Run: CDH > Decision Audit > [Customer] > [Action] > Component Values

Step 2: Check Propensity
  → Is the ADM model Active?
  → Is ResponseCount > 0?
  → Is Propensity > 0.001 (above floor)?

Step 3: Check Weight
  → Is Weight > 0?
  → Which weight level is being applied (action vs action×channel)?
  → Are any levers setting weight to 0?

Step 4: Check ContextWeight
  → Which context rules are firing?
  → Is any context rule setting ContextWeight = 0?

Step 5: Compare to winning action
  → Calculate Priority for winning action
  → Calculate Priority for expected action
  → The winner has higher Priority — is this intended?

Step 6: Check eligibility (separate from Priority)
  → Is the action passing all three engagement policy layers?
  → Decision Audit shows ELIGIBILITY_FAILED / SUITABILITY_FAILED etc.
```
