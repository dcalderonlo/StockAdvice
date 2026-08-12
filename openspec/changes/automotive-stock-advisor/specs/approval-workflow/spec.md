# approval-workflow — Specification

## Purpose

Manages the lifecycle of replenishment recommendations through a state machine (pending → approved | rejected | handled | ordered) with threshold-based escalation from branch manager to coordinator to gerente. Ensures every action is human-approved and audited.

## Requirements

### REQ-AW-001: State machine
The system **shall** manage recommendations through the following states:
- **pending**: newly generated, awaiting review
- **approved**: branch manager or coordinator has approved the recommendation
- **rejected**: reviewer has decided not to act on this recommendation this run
- **handled**: reviewer has already acted on this recommendation externally (off-system)
- **ordered**: confirmation that external action (purchase/transfer) has been completed

#### Scenario: New recommendation enters pending
- GIVEN a replenishment run generates a recommendation
- WHEN the recommendation is created
- THEN its initial state is "pending"
- AND the branch manager is notified

#### Scenario: Branch manager approves
- GIVEN a recommendation in "pending" state
- WHEN the branch manager approves it
- THEN the state transitions to "approved"
- AND the action is recorded in the audit log with the role used

#### Scenario: Branch manager rejects
- GIVEN a recommendation in "pending" state
- WHEN the branch manager rejects it
- THEN the state transitions to "rejected"
- AND the recommendation is skipped for this run

#### Scenario: Branch manager marks as handled
- GIVEN a recommendation in "pending" state
- WHEN the branch manager marks it as handled
- THEN the state transitions to "handled"
- AND the system records that external action was taken off-system

#### Scenario: Confirmation after external action
- GIVEN a recommendation in "approved" state
- WHEN the user confirms external action is complete
- THEN the state transitions to "ordered"

### REQ-AW-002: Default approver
The system **shall** assign the branch manager of the target branch as the default approver for recommendations in "pending" state.

#### Scenario: Branch manager is default approver
- GIVEN a recommendation for Branch A
- WHEN the recommendation enters pending state
- THEN the branch manager of Branch A is the assigned approver
- AND only the branch manager (or an escalator) can change the state

### REQ-AW-003: Escalation by threshold
The system **shall** auto-escalate recommendations that cross configured thresholds (value, volume, or impact) from branch manager to coordinator. The coordinator may further escalate to gerente for cross-coordinator cases.

#### Scenario: Value threshold crossed
- GIVEN a recommendation with total value exceeding the configured threshold
- WHEN the recommendation is generated
- THEN the system auto-escalates to the coordinator
- AND the coordinator becomes the approver

#### Scenario: Coordinator escalates to gerente
- GIVEN an escalated recommendation that the coordinator deems requires higher authority
- WHEN the coordinator escalates
- THEN the recommendation is routed to the gerente
- AND the gerente becomes the approver

### REQ-AW-004: Cross-coordinator transfer approval
Cross-coordinator transfers (between branches in different coordinator scopes) **shall** be decided by the gerente. The source and destination coordinators are notified but do not approve.

#### Scenario: Cross-coordinator transfer
- GIVEN a transfer recommendation from Branch A (Coordinator X's scope) to Branch B (Coordinator Y's scope)
- WHEN the system evaluates the approval flow
- THEN the gerente is the decision authority
- AND both Coordinator X and Coordinator Y are notified
- AND neither coordinator can approve or reject the transfer

#### Scenario: Gerente rejects cross-coordinator transfer
- GIVEN a cross-coordinator transfer pending gerente decision
- WHEN the gerente rejects it
- THEN the transfer is not executed
- AND the recommendation state transitions to "rejected"
- AND both coordinators are notified of the rejection

### REQ-AW-005: Single-coordinator transfer approval
Single-coordinator transfers (within the same coordinator scope) **shall** follow the standard branch manager → coordinator approval flow.

#### Scenario: Within-scope transfer
- GIVEN a transfer recommendation from Branch A to Branch B, both under Coordinator X
- WHEN the system evaluates the approval flow
- THEN the branch manager reviews first
- AND if approved, the coordinator confirms the transfer

### REQ-AW-006: Audit logging
The system **shall** record every state transition in the audit log, including: user ID, role used, action, entity type, entity ID, timestamp, and metadata.

#### Scenario: Approval logged
- GIVEN a branch manager approves a recommendation
- WHEN the state transitions to "approved"
- THEN the audit log records: user_id, role_used_id = warehouse_manager, action = approve, entity_type = recommendation, entity_id, timestamp

#### Scenario: Escalation logged
- GIVEN a recommendation is auto-escalated to a coordinator
- WHEN the escalation occurs
- THEN the audit log records: action = escalate, reason = threshold_crossed, from_role = warehouse_manager, to_role = coordinator

### REQ-AW-007: Bulk actions
The system **shall** allow branch managers to approve, reject, or mark as handled multiple recommendations in a single action.

#### Scenario: Bulk approve
- GIVEN a branch manager has 47 pending recommendations
- WHEN the manager selects 30 and clicks "Approve All"
- THEN all 30 recommendations transition to "approved"
- AND each transition is individually logged in the audit log

## Edge cases

- Recommendation in "pending" state but branch manager has left the organization (reassign to coordinator)
- Bulk action on a mix of pending and already-processed recommendations (skip non-pending)
- Escalation threshold set to zero (all recommendations escalate — system should allow but warn)
- Coordinator approves a recommendation that was not escalated (out of scope — system should reject)
- Gerente approves a cross-coordinator transfer after source branch has already consumed the excess stock
- State transition from "rejected" to "pending" (not allowed — rejected recommendations are final for that run)

## Acceptance criteria

- AC-1: New recommendations always start in "pending" state
- AC-2: Branch manager is the default approver for own branch recommendations
- AC-3: Threshold-crossing recommendations auto-escalate to coordinator
- AC-4: Cross-coordinator transfers require gerente approval (coordinators notified only)
- AC-5: Every state transition is recorded in the audit log with role used
- AC-6: Bulk actions process only pending recommendations and log each individually
- AC-7: Rejected recommendations cannot be re-opened within the same run

## Notes

- System never auto-approves — all actions require human decision
- Audit log is append-only (no update/delete on AuditLog rows)
- Escalation thresholds are configurable per tenant and per coordinator scope
