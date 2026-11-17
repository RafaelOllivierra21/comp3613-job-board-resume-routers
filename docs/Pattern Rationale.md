# Pattern Rationale for the Application Lifecycle

## 1. Special Feature and Inherited Weakness

Our special feature is application lifecycle tracking. An application submitted on the platform moves from Submitted to Reviewed to Shortlisted, and finally to Rejected or Hired. Only the Employer who owns the listing may change an application's status, only legal transitions are allowed, and Graduates must always see one consistent status (AC 9 to AC 12, FR-13 to FR-17).

The inherited code stores the lifecycle in two places at once. The Application model in app/models/application.py has a free-text status column and four integer flags (flag_reviewed, flag_shortlisted, flag_rejected and flag_hired). A single function, apply_action() in app/services/lifecycle.py, updates both through nested if/elif branches that check the status and the flags. Nothing keeps the two in agreement, and nothing defines which transitions are legal.

## 2. Target Defects

| ID | Defect | Location | Breaks | Evidence |
|----|----------------|----------|---|---|
| DEF-1 | Status and flags drift apart. Rejecting an application does not clear flag_shortlisted, and reopen sets the status back to submitted but leaves flag_hired and flag_rejected set | lifecycle.py, apply_action(), lines 98 to 106 and 124 to 126 | AC 11 | INT-25 |
| DEF-2 | Two readers disagree. The Graduate view works out the status from the flags while the Employer view reads the status column, so the same application can show two different statuses | applications.py, my_applications() lines 65 to 67 and listing_applicants(), lifecycle.py, derived_status_from_flags() line 138 | AC 11 | INT-25 |
| DEF-3 | Illegal jumps are accepted. An application can be hired or shortlisted straight from Submitted without being reviewed | lifecycle.py, apply_action(), lines 84 to 85 and 108 to 111 | AC 10 | INT-34 |
| DEF-4 | Final statuses are not final. A rejected application can be reviewed, shortlisted or hired, a hired one can be rejected, and a reopen action exists with no rule | lifecycle.py, apply_action(), lines 69, 79, 100, 115 and 124 | AC 10 | INT-16, INT-33 |
| DEF-5 | Illegal actions behave inconsistently. Some succeed, some are silently ignored and still report success (marking a hired application as reviewed or hiring it again), and one returns an error (shortlisting a hired application) | lifecycle.py, apply_action(), lines 63 to 64, 93 and 119 | AC 10 | None |
| DEF-6 | The nested branching on status and flags is the Switch Statements code smell. Any change to a status means editing the shared branches, which breaks the Open/Closed Principle, and one function holds the rules for every status, which breaks the Single Responsibility Principle | lifecycle.py, apply_action(), lines 61 to 126 | NFR-05 | None |
| DEF-7 | Any Employer, and any Administrator, can change the status of any application because listing ownership is never checked | applications.py, transition_application(), lines 108 to 109 | AC 12, FR-14 | INT-15, INT-30 |

The starter's comments already point to most of these problems. What we added was tracing each one to the acceptance criterion it breaks and to what the stakeholders told us, and finding the related problems below, two of which the comments do not mark at all.

### Related Problems Fixed in Sprint 2 Alongside the Pattern

- The API trusts an actor_id sent in the request body, so any caller can act as any user (app/routers/board.py, TransitionBody, lines 42 to 46, NFR-06).
- There are no lifecycle tests. The existing tests only cover authentication, the health check and the job list endpoint.
- Graduates can apply to pending or expired listings, and external-link listings still create an application record (applications.py, line 32, AC 4, AC 6 and AC 13).

## 3. Pattern Identified

We identified the State pattern. State lets an object change its behaviour when its internal state changes, so that the object appears to change its class. This fits our problem directly. An application's behaviour depends on its current status, and the same action, such as reject, must succeed from Shortlisted and be refused from every other status. The starter handles this with nested if/elif checks on the status and flags, which is the Switch Statements smell, where branching on a type or state should be replaced by polymorphism. Under State, each status becomes its own class, and the branches become calls on the current state object. The state classes are plain runtime classes rather than database tables, and only the name of the current state is stored.

### Why the Open/Closed Principle Decided It

A design cannot be closed against every change, so it should be closed against the changes most likely to happen. Our interviews show the lifecycle is exactly where change is likely. Stakeholders described rejecting an application straight from Reviewed (INT-16, FR-27) and moving a Shortlisted application back to Reviewed (INT-37, FR-28), both of which we left out of this version. In the inherited design, either change means editing the shared branches of apply_action() and keeping the flags in step. With State, allowing rejection from Reviewed only changes one class, ReviewedState. Adding a brand new action, such as moving back to Reviewed, adds one method to ApplicationState and a response in each state, but every change stays inside the state it belongs to.

### Agreed Transitions

| From | Action | To |
|---|---|---|
| Submitted | mark_reviewed() | Reviewed |
| Reviewed | shortlist() | Shortlisted |
| Shortlisted | reject() | Rejected |
| Shortlisted | hire() | Hired |
| Rejected or Hired | Any | Refused, as both are final |

Every other action is refused. Some interview answers conflicted with AC 10. The Employer said a Shortlisted application could not go straight to Rejected (INT-37), while stakeholders allowed Reviewed to go directly to Rejected or Hired (INT-16). In every case we followed AC 10 (FR-15, D-3). Rejected and Hired are final, which both the Administrator and the Employer confirmed (INT-16, INT-33), so the old reopen action is removed (FR-16, D-4).

### Participants

| Role in the Pattern | Our Class |
|---|---|
| Context | Application. It stores only state_name in place of the status column and the four flags, holds its current state object, and passes mark_reviewed(), shortlist(), reject() and hire() to that state |
| State (interface) | ApplicationState, an abstract class with mark_reviewed(), shortlist(), reject(), hire() and get_state_name() |
| Concrete States | SubmittedState, ReviewedState, ShortlistedState, RejectedState and HiredState. Each one carries out its legal transitions and refuses the rest. RejectedState and HiredState refuse everything |

When an application is loaded, its state object is rebuilt from state_name using a map from each state name to its class.

### How the Pattern Fixes the Target Defects

| Defect | Fix |
|---|---|
| DEF-1 and DEF-2 | There is one source of truth, state_name. The flags are removed and every role reads the same value |
| DEF-3 and DEF-4 | Each state only carries out its legal transitions. The final states refuse everything and reopen is removed |
| DEF-5 | Every illegal action fails in the same way, with an error the API returns as a 4xx response |
| DEF-6 | Each class holds the rules for one state, and changing what a state allows only touches that class |
| DEF-7 | Not fixed by the pattern. The ownership check stays in the service layer, separate from the state logic, and returns a permission error |

### Why Not Strategy

Strategy defines a family of interchangeable algorithms that can vary independently from the clients that use them. Our lifecycle is not a choice of algorithm made by a client. The application's own behaviour changes as its internal state changes, which is what State describes.

### Trade-offs

State adds six classes, and the final states repeat similar refusals. We accept this because the lifecycle is where change is most likely, and the cost of the inherited design, with drifting flags, illegal transitions and shared branches, is already visible in DEF-1 to DEF-6.

## 4. Sprint 2 Change Outline

All changes keep the existing layered structure of routes, services, repositories and models.

### Pattern Implementation

1. Add a new module with ApplicationState and the five concrete states. Each state carries out only its legal transitions, and any illegal action raises an error.
2. Change the Application model so it stores a single state_name in place of status and the four flag columns. Add a state property that rebuilds the state object from state_name, and action methods that pass each request to the current state.
3. Remove apply_action(), derived_status_from_flags() and the reopen action from lifecycle.py.
4. Update transition_application() to call the model's action methods, so illegal transitions return a consistent 4xx error.

### Related Gaps Closed Alongside

5. Only the Employer who owns the listing, checked through listing.employer_id, may change an application's status. Administrators and other Employers are refused with a 403. The same check is added to listing_applicants().
6. The Graduate and Employer views both read state_name, so everyone sees the same status.
7. Update the seed data for the new model, with sample applications in different states for the demo. Running manage.py init drops and recreates the tables by default, so no migration is needed.

### Testing

8. Unit tests that check every legal transition succeeds and every illegal one is refused, including any action on Rejected or Hired.
9. Integration tests for the listing owner, a different Employer and an Administrator, for the same status showing in the Graduate and Employer views, and for reopen no longer being accepted.
