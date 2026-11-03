# Shared registration review implementation plan

**Goal:** Every teacher with a student in an active class roster can review that student's global account application through that class.

**Architecture:** Keep course classes, attendance and scores independent. Use existing student IDs and active enrollments to associate an application with every teacher's roster, without matching class names or changing ownership. Teachers may query only their own course classes. Student monitor permissions retain their existing submission-class scope.

**Tech stack:** FastAPI, SQLAlchemy, pytest.

This implements the approved multi-teacher review rule using the existing roster associations. It does not introduce an administrative-class management system or merge rosters. A student must already be on each teacher's roster to appear in that teacher's review list.

- [x] Add API regression tests for cross-course listing, approval/rejection, shared history, stale decisions, unrelated students, removed enrollments and archived classes; observe failure before implementation.
- [x] Centralize teacher application scope (submitted to this class OR student actively enrolled here), use it in both listing and batch review; retain monitor scope and current locking/account safeguards.
- [x] Preserve submission class in audit records and record review context separately; expose shared history to teachers.
- [x] Document roster-based sharing, run registration/portal/monitor regressions, lint and type checks, inspect final diff.

Verification: the new cross-teacher test first failed because the second teacher received an empty list. Final regression run: 30 passed. Ruff check and format check passed for both changed Python files. Mypy passed for all 71 backend source files. No schema migration required; runtime deployment/restart was not performed.
