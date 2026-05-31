# CDH Data Dictionary

## Interaction History Fields

| Field | Type | Description |
|-------|------|-------------|
| pxInteractionID | String | Unique interaction identifier |
| CustomerID | String | Customer unique identifier |
| ActionName | String | Name of the NBA action offered |
| Issue | String | Business issue (Retention, Growth, Risk) |
| Group | String | Action group within the issue |
| Channel | String | Web, Email, Mobile, CallCentre |
| Direction | String | Inbound or Outbound |
| Outcome | String | Impression, Clicked, Accepted, Rejected |
| Propensity | Decimal | ADM model propensity score [0,1] |
| Priority | Decimal | Arbitrated final priority |
| pxDecisionTime | DateTime | When the decision was made |
| ExperimentGroup | String | Champion or Challenger |

## ADM Snapshot Fields

| Field | Type | Description |
|-------|------|-------------|
| ModelID | String | Unique model identifier |
| AUC | Decimal | Area under ROC curve [0.5,1.0] |
| ResponseCount | Integer | Training response count |
| PositiveResponses | Integer | Accept count |
| Positivity | Decimal | Accept rate = Positive/Total |
| SnapshotTime | DateTime | Snapshot timestamp |

## Common Channel Values
- Web: Customer-facing web portal
- Mobile: Mobile app (iOS/Android)
- Email: Outbound email campaign
- CallCentre: Agent-assisted inbound call
- SMS: Text message
- Push: Mobile push notification
