# NBA Strategy Configuration Guide

## Overview
This document describes how to configure Next Best Action (NBA) strategies
in Pega Customer Decision Hub (CDH).

## Engagement Policy Configuration

### Eligibility Rules
Eligibility rules determine which customers can receive an action.
Navigate to: CDH > NBA Designer > Engagement Policy > Eligibility

Key fields:
- CustomerSegment: Target segment (Gold, Silver, Bronze)
- AccountStatus: Must be "Active"
- DaysSinceLastContact: Minimum 7 days suppression window

### Applicability Rules
Applicability rules filter based on the current context:
- Channel must match action's configured channels
- Customer must not have an open case for the same issue

### Suitability Rules
Suitability rules apply business constraints:
- Do not offer CreditCard if customer already has 3 cards
- Do not offer Loan if debt-to-income ratio > 0.4

## Arbitration Configuration

### Priority Formula
Priority = Value × Propensity × Weight × Context Weight

Where:
- Value: Business value of the action (configured per action)
- Propensity: ADM model output [0,1]
- Weight: Strategy-level weight (default 1.0)
- Context Weight: Situation-specific multiplier

### Champion / Challenger Setup
Navigate to: ADM > Model Management > Champion Challenger
1. Set champion model (default: production model)
2. Configure challenger with traffic split (e.g. 10% challenger)
3. Monitor AUC delta weekly; promote if AUC improves > 0.02

## Contact Policy
Maximum 3 outbound contacts per customer per week across all channels.
Email: max 2 per week. SMS: max 1 per week. Push: max 3 per week.
