# notification-service — Specification

## Purpose

Delivers email and in-app alerts for recommendations, escalations, and system events. Recipients include branch managers, coordinators, and gerente del departamento. Email is batched (digest per run); in-app notifications are real-time per item.

## Requirements

### REQ-NS-001: Recommendation pending notification
The system **shall** notify the branch manager when new recommendations are generated for their branch. Email is sent as a digest (one email per run, not one per recommendation).

#### Scenario: Digest email after replenishment run
- GIVEN a replenishment run generates 47 new recommendations for Branch A
- WHEN the run completes
- THEN the branch manager receives one digest email listing all 47 recommendations
- AND the email includes: SKU codes, quantities, source types, and a link to the dashboard

#### Scenario: In-app notification per recommendation
- GIVEN a replenishment run generates 47 new recommendations
- WHEN the run completes
- THEN 47 in-app notifications appear in the branch manager's dashboard
- AND each notification shows the individual recommendation details

### REQ-NS-002: Escalation notification
The system **shall** notify the coordinator when a recommendation is auto-escalated due to threshold crossing. For cross-coordinator transfers, the gerente is notified.

#### Scenario: Coordinator receives escalation
- GIVEN a recommendation exceeds the value threshold
- WHEN the system auto-escalates
- THEN the coordinator receives an email notification
- AND an in-app notification appears in the coordinator's dashboard
- AND the notification includes the recommendation details and escalation reason

#### Scenario: Gerente notified of cross-coordinator transfer
- GIVEN a transfer crosses coordinator boundaries
- WHEN the system routes the approval to the gerente
- THEN the gerente receives an email notification
- AND both source and destination coordinators are notified (but do not approve)

### REQ-NS-003: Partial fulfillment alert
The system **shall** alert the branch manager, coordinator(s), and gerente del departamento when a recommendation cannot be fully fulfilled by inter-branch transfer and requires external purchase for the remainder.

#### Scenario: Partial fulfillment alert
- GIVEN a recommendation needs 30 units but only 18 units are available via transfer
- WHEN the system generates the partial fulfillment recommendation
- THEN the branch manager, coordinator(s), and gerente are all notified
- AND the notification explains the partial availability and the remaining gap

### REQ-NS-004: Cold-start flag notification
The system **shall** notify the branch manager when a SKU is flagged as requiring manual override due to zero sales history.

#### Scenario: Cold-start SKU flagged
- GIVEN a new SKU with zero sales history is encountered during a replenishment run
- WHEN the system flags the SKU
- THEN the branch manager receives a notification
- AND the notification explains that manual demand override is required

### REQ-NS-005: Classification review notification
The system **shall** notify the gerente (or delegated coordinator) when the monthly classification pass completes and Lifecycle Stage codes require review.

#### Scenario: Classification review queue
- GIVEN the monthly classification pass produces 12 new Lifecycle Stage codes
- WHEN the pass completes
- THEN the gerente receives a notification with the count of items requiring review
- AND a link to the classification review queue in the dashboard

#### Scenario: Delegated coordinator notified
- GIVEN the gerente has delegated classification review to a coordinator
- WHEN the monthly classification pass completes
- THEN the delegated coordinator receives the notification instead of the gerente
- AND the gerente retains oversight visibility

### REQ-NS-006: DC stock critical alert
The system **shall** alert the DC branch manager, dependent coordinators, and gerente when DC stock falls below a critical threshold for the demand of its dependents.

#### Scenario: DC stock critical
- GIVEN a DC's stock falls below the critical threshold for its dependents' demand
- WHEN the system detects the condition
- THEN the DC branch manager, all dependent coordinators, and the gerente are alerted
- AND the alert includes the DC's current stock, projected demand, and risk level

### REQ-NS-007: Notification channels
The system **shall** support two notification channels: email and in-app dashboard. Email is batched (digest); in-app is real-time.

#### Scenario: Email digest timing
- GIVEN a replenishment run completes at 3:00 AM
- WHEN the system sends the digest email
- THEN the email is sent immediately (or at the configured digest time)
- AND contains all recommendations from that run

#### Scenario: In-app real-time
- GIVEN a recommendation is generated
- WHEN the user is logged into the dashboard
- THEN the in-app notification appears within 5 minutes

### REQ-NS-008: Admin receives no direct notifications
The administrator role **shall not** receive direct notifications. The admin views consolidated state in the dashboard.

#### Scenario: Admin not notified
- GIVEN a recommendation is generated or escalated
- WHEN the notification dispatch runs
- THEN the admin does not receive an email or in-app notification
- AND the admin can view the recommendation in the dashboard's global view

## Edge cases

- Branch manager has no email configured (in-app notification still delivered)
- Email delivery failure (system retries and logs the failure)
- User receives duplicate notifications (same recommendation escalated and then re-escalated)
- Notification sent to a deactivated user (system should skip and log)
- Digest email with zero recommendations (run produced no triggers — no email sent)
- In-app notification for a recommendation that was already approved by another user
- Notification throttling during high-volume runs (hundreds of recommendations)

## Acceptance criteria

- AC-1: Branch manager receives one digest email per replenishment run (not one per recommendation)
- AC-2: In-app notifications appear within 5 minutes of recommendation generation
- AC-3: Escalation notifications include the reason and recommendation details
- AC-4: Partial fulfillment alerts reach branch manager, coordinator(s), and gerente
- AC-5: Admin does not receive direct notifications
- AC-6: Email delivery failures are logged and retried
- AC-7: Cold-start flag notifications prompt the branch manager to apply a demand override

## Notes

- Email templates defined in design.md §7
- Throttling: one digest per run + daily 8AM summary for all pending items
- Admin receives no notifications; views consolidated state in dashboard
