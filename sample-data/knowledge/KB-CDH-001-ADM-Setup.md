# KB-CDH-001: ADM Model Setup and Configuration

## Summary
This KB article describes the setup procedure for Adaptive Decision Manager
models in Pega CDH and common configuration issues.

## Prerequisites
- Pega Platform 8.7 or higher
- CDH license activated
- Interaction History data flow configured
- Minimum 200 positive responses per action

## Setup Procedure

### Step 1: Create Model
1. Navigate to CDH > Adaptive Models
2. Click New > Adaptive Model
3. Set Model Type: Gradient Boost (recommended) or Naive Bayes
4. Configure context: Issue, Group, Channel

### Step 2: Configure Predictors
Common high-value predictors for CDH:
- Customer age and tenure
- Account balance and product holdings
- Recent interaction history (last 30/60/90 days)
- Channel preference score
- Geographic region

Avoid sensitive predictors:
- Race, ethnicity, religion
- Gender (in regulated markets)
- Postcode as proxy for race

### Step 3: Set Performance Thresholds
| AUC Range | Status | Action Required |
|-----------|--------|-----------------|
| > 0.80 | Excellent | No action |
| 0.70-0.80 | Good | Monitor |
| 0.60-0.70 | Fair | Review predictors |
| < 0.60 | Poor | Retrain or disable |

## Known Issues
Issue: AUC drops after large IH data import
Resolution: Rebuild model index. Navigate to ADM > Tools > Rebuild Index.

Issue: Model shows "Insufficient Data" despite 500+ responses
Resolution: Check that IH data flow maps pxDecisionTime correctly.
