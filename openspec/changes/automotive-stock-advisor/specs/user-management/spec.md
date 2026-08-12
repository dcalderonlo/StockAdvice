# user-management — Specification

## Purpose

Manages user invitation, role assignment, and branch access control. Supports multi-role per user with effective permissions computed as the union of all assigned roles. Enforces hierarchical access: admin (global), gerente (org-wide), coordinator (scoped), branch manager (single branch).

## Requirements

### REQ-UM-001: User invitation
The system **shall** invite users via email, specifying role and branch (or scope) at invite time. The invitation includes a link to create a password and activate the account.

#### Scenario: Email-based invitation
- GIVEN an admin wants to invite a new user
- WHEN the admin enters the user's email, role, and branch/scope
- THEN the system sends an invitation email with an activation link
- AND the link expires after a configurable period (default: 7 days)

#### Scenario: Invitation accepted
- GIVEN a user clicks the activation link in the invitation email
- WHEN the user creates a password
- THEN the user account is activated
- AND the user can log in with their email and password

#### Scenario: Expired invitation
- GIVEN an invitation link has expired (7 days passed)
- WHEN the user clicks the link
- THEN the system displays an error that the invitation has expired
- AND the admin can resend the invitation

### REQ-UM-002: Role assignment
The system **shall** support four roles: administrator, gerente (department manager), warehouse coordinator, and warehouse manager. A user can have one or more roles.

#### Scenario: Single role assignment
- GIVEN a new user is invited as a warehouse manager for Branch A
- WHEN the user is created
- THEN the user has exactly one role: warehouse_manager
- AND the user can access only Branch A's data

#### Scenario: Multi-role assignment
- GIVEN a user is assigned both warehouse_manager (Branch A) and warehouse_coordinator (Branches A, B)
- WHEN the user logs in
- THEN the user's effective permissions are the union of both roles
- AND the user can access Branch A and Branch B data

### REQ-UM-003: Effective permissions = union of roles
The system **shall** compute effective permissions as the union of all assigned roles. A user with multiple roles can perform any action permitted by any of their roles.

#### Scenario: Union of permissions
- GIVEN a user has warehouse_manager (Branch A) and warehouse_coordinator (Branches A, B)
- WHEN the user attempts to approve a recommendation for Branch B
- THEN the action is allowed (coordinator role permits it)
- AND the audit log records which role was used (coordinator)

#### Scenario: Conflict of interest warning
- GIVEN an admin assigns both administrator and warehouse_manager roles to the same user
- WHEN the assignment is saved
- THEN the system displays a warning about potential conflict of interest
- AND the assignment is still allowed (admin can override the warning)

### REQ-UM-004: Hierarchical access control
The system **shall** enforce hierarchical access:
- **Admin**: all branches, all data, all users
- **Gerente**: all branches (read + approval for cross-coordinator cases), global KPIs
- **Coordinator**: branches in their scope (read + approval), KPIs within scope
- **Branch manager**: own branch only

#### Scenario: Branch manager sees only own branch
- GIVEN a branch manager for Branch A
- WHEN the user views the dashboard
- THEN only Branch A's data is visible
- AND the user cannot access Branch B's data

#### Scenario: Coordinator sees scoped branches
- GIVEN a coordinator with Branches A, B, C in their scope
- WHEN the user views the dashboard
- THEN aggregated data for A, B, C is visible
- AND the user can drill down into each branch individually

### REQ-UM-005: User management hierarchy
The system **shall** enforce who can manage which users:
- **Admin**: can manage all users
- **Gerente**: can manage users with gerente role and below
- **Coordinator**: can manage users within their scope (branch managers)
- **Branch manager**: cannot manage other users

#### Scenario: Coordinator invites branch manager
- GIVEN a coordinator wants to invite a branch manager for a branch in their scope
- WHEN the coordinator sends the invitation
- THEN the invitation is valid and the user is created
- AND the new user is linked to the coordinator's scope

#### Scenario: Branch manager cannot invite
- GIVEN a branch manager attempts to invite another user
- WHEN the manager tries to access the user management panel
- THEN the system denies access
- AND displays an authorization error

### REQ-UM-006: Audit log for role-based actions
The system **shall** record which role was used for each action in the audit log. When a user has multiple roles, the system **shall** determine the effective role for the action and log it.

#### Scenario: Multi-role action logged
- GIVEN a user with warehouse_manager and warehouse_coordinator roles approves a recommendation
- WHEN the approval is processed
- THEN the audit log records the specific role used (e.g., warehouse_coordinator)
- AND the timestamp, user ID, and action are recorded

### REQ-UM-007: Branch assignment
The system **shall** link users to branches:
- **Branch manager**: linked to exactly one branch
- **Coordinator**: linked to a subset of branches (multiple branches supported)
- **Gerente**: org-wide (no specific branch assignment)
- **Admin**: global (no specific branch assignment)

#### Scenario: Coordinator with multiple branches
- GIVEN a coordinator is assigned to Branches A, B, and C
- WHEN the coordinator views their scope
- THEN all three branches are accessible
- AND the coordinator can manage users for all three branches

## Edge cases

- User deactivated while having pending approvals (pending recommendations reassigned)
- User with no roles assigned (system should prevent — every user must have at least one role)
- Coordinator scope changes (user loses access to removed branches immediately)
- Branch manager transferred to another branch (access to old branch revoked)
- User invited with an email that already exists (system should merge roles, not create duplicate account)
- All admin users deactivated (system should prevent — at least one admin must remain active)
- Role assignment during active session (permissions take effect on next request, not mid-session)

## Acceptance criteria

- AC-1: Invitation email includes activation link with configurable expiry
- AC-2: Multi-role users have effective permissions = union of all roles
- AC-3: Conflict of interest warnings displayed for risky role combinations
- AC-4: Branch manager can access only their assigned branch
- AC-5: Coordinator can access only branches in their scope
- AC-6: Audit log records the specific role used for each action
- AC-7: User management follows the hierarchy (admin → gerente → coordinator → branch manager)
- AC-8: At least one active admin must always exist

## Notes

- Auth: Django sessions + allauth (email + password)
- Session expiry: 2h idle, 24h absolute
- Password policy: minimum 8 chars, Django's default validators
- Rate-limit login: 5 attempts/15 min per IP
