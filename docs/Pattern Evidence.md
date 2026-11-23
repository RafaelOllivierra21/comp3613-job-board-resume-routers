# Pattern Evidence for the Application Lifecycle

## 1. Special Feature and Pattern

Our special feature is application lifecycle tracking. In Sprint 1 we identified the State pattern for it in docs/Pattern Rationale.md and showed it in docs/Class Diagram.pdf. In Sprint 2 we replaced the inherited status string, the four boolean flags and the nested if/elif branches with working State classes.

Each status is now its own class. A state carries out only the transitions that are legal from it and refuses everything else, so the rules for one status live in one place. Application stores a single value, state_name, and hands every action to its current state. The transitions follow AC 10. Submitted can only be reviewed, Reviewed can only be shortlisted, Shortlisted can be rejected or hired, and Rejected and Hired are final with no reopen.

Checking who may change a status stays in the service layer, outside the state classes. The states decide which moves are legal and the service decides who is allowed to ask for one.

## 2. Key Files

| File | Role in the pattern | What it replaced |
|---|---|---|
| app/services/states.py | ApplicationState is the base state and refuses every action by default. The five concrete states each allow only their legal moves. A refused move raises InvalidTransition. STATES and state_for() turn a stored state_name into its state object | The nested branches in the old apply_action() |
| app/models/application.py | Application is the context. It stores only state_name, rebuilds its state with state(), and passes mark_reviewed(), shortlist(), reject() and hire() to that state | The status column and the flag_reviewed, flag_shortlisted, flag_rejected and flag_hired columns |
| app/services/lifecycle.py | A thin entry point. apply_action() checks the action name and calls the matching method on Application, with no branching on status | The old apply_action() with its nested branches and the reopen action |
| app/services/applications.py | The service layer. transition_application() checks ownership with verify_listing_owner() before any state is touched and turns InvalidTransition into a 409 response. application_view() gives every role the same application data read from state_name | The check that let any employer or admin change any application |
| app/routers/board.py | Reads the acting user from the login cookie and returns the status code from the service | Trusting actor_id and 400 for every error |
| tests/test_states.py | 27 unit tests over all 20 pairs of state and action, plus the registry and an unknown state name | No lifecycle tests in the starter |

## 3. How One Transition Runs

This is the path when the employer who owns a listing shortlists an application that is in Reviewed.

1. The employer, already logged in through POST /api/auth/login, sends POST /api/applications/{id}/transition with the action shortlist.
2. The route in board.py reads the employer from the login cookie and calls transition_application() in applications.py. A request with no login gets 401.
3. The service checks that the actor is an employer and that shortlist is a known action. An unknown action returns 400.
4. The service loads the application and its listing. A missing application returns 404.
5. verify_listing_owner() checks that the listing belongs to this employer. Anyone else gets 403 and nothing changes.
6. apply_action() in lifecycle.py calls shortlist() on the Application.
7. Application.state() looks up state_for("reviewed") and gets ReviewedState. Application.shortlist() passes itself to ReviewedState.shortlist().
8. ReviewedState sets state_name to shortlisted. If the move were illegal, for example hire from Reviewed, the base class would raise InvalidTransition, state_name would stay the same and the service would return 409.
9. The service saves the row and returns it through application_view(), so the employer, the graduate and the admin export all show shortlisted.

## 4. Defects Fixed

| Defect | How it was fixed | Where | PR |
|---|---|---|---|
| DEF-1 Status and flags drift apart | The flags are gone and state_name is the only stored status | app/models/application.py | #6 |
| DEF-2 Graduate and employer views disagree | Both views read state_name and return the same fields through application_view() | app/services/applications.py | #6, #7 |
| DEF-3 Illegal jumps are accepted | Each state class only carries out its own legal moves | app/services/states.py | #6 |
| DEF-4 Final statuses are not final and reopen exists | RejectedState and HiredState allow nothing, and reopen was removed from the actions | app/services/states.py, app/services/lifecycle.py | #6 |
| DEF-5 Illegal actions behave inconsistently | Every refused move raises InvalidTransition and returns 409 with the status unchanged | app/services/states.py, app/services/applications.py | #6 |
| DEF-6 Switch Statements smell breaking OCP and SRP | apply_action() has no branching on status and each class holds the rules for one status | app/services/lifecycle.py, app/services/states.py | #6 |
| DEF-7 Any employer or admin can change any status | verify_listing_owner() lets only the listing's employer transition its applications (AC 12) | app/services/applications.py | #7 |

As an example of the Open/Closed Principle, allowing Reviewed to go straight to Rejected later would only mean adding a reject() method to ReviewedState. No other class would change.

## 5. Pull Requests

| PR | Trello card | What it shows |
|---|---|---|
| #6 | #12a, #12b and #12c | The State pattern itself. The state classes and their tests, Application using state_name, and lifecycle.py delegating to the states |
| #7 | #13 | Owner only transitions, both views reading state_name, consistent error codes and the apply checks |
| #8 | #19 | Related MVP gaps closed alongside the pattern. Listings start pending, graduates only see open listings, publishing notifies subscribers and only eligible graduates can subscribe. This PR is not part of the pattern itself |

PR links
https://github.com/RafaelOllivierra21/comp3613-job-board-resume-routers/pull/6
https://github.com/RafaelOllivierra21/comp3613-job-board-resume-routers/pull/7
https://github.com/RafaelOllivierra21/comp3613-job-board-resume-routers/pull/8

## 6. Differences from the Sprint 1 Class Diagram

The pattern is the same as the one in our class diagram, with the same context, base state and five concrete states. A few details changed during implementation.

1. There is no LifecycleService class. The STATE_REGISTRY in the diagram is the STATES dictionary and state_for() in states.py, which replaces get_state_for_name(). transition_application() and verify_listing_owner() are functions in applications.py.
2. Application has no _state attribute and no _set_state() method. Its state object is rebuilt from state_name with state() each time, and a state changes the status by setting state_name.
3. The concrete states only define the actions they allow. ApplicationState refuses every action by default, so the final states do not repeat the same refusals four times.
4. InvalidTransition is a new class that every refused move raises.

These changes are recorded on Trello card #17 so the class diagram can be updated to match the code.

## 7. How to See It Running

1. Run python manage.py init to create and seed the database.
2. Run python -m pytest -q. The lifecycle tests are in tests/test_states.py.
3. Run python manage.py run and open /docs in the browser. Use POST /api/auth/login before each step to log in as the user named in it.
4. Log in as grad.dcit@example.com and apply to listing 1 with a cover letter and resume. The application starts as submitted.
5. Log in as employer@example.com, who owns listing 1, and transition it with mark_reviewed and then shortlist. Each step returns the new status.
6. Still as employer@example.com, try mark_reviewed again. It returns 409 and the status stays shortlisted.
7. Log in as employer2@example.com or admin@example.com and try any action. It returns 403.
8. Log in as grad.dcit@example.com and list your applications. The status matches what employer@example.com sees for listing 1.
