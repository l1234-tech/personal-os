# Personal OS — Development checkpoint

Last updated: 2026-10-22

This file is the durable resume point for future work sessions. Read it before continuing.

## Repository
- Repository: https://github.com/l1234-tech/personal-os
- Foundation branch: `feat/foundation`
- Foundation PR: https://github.com/l1234-tech/personal-os/pull/1 (draft; targets `main`)
- Auth branch: `feat/auth-security`
- Auth PR: https://github.com/l1234-tech/personal-os/pull/3 (draft; targets `feat/foundation`)
- MVP tracker: https://github.com/l1234-tech/personal-os/issues/2

## Current state
### Foundation
- MVP specification, architecture, data model, security notes, roadmap and development docs are present.
- React/Vite PWA shell and responsive dashboard prototype exist.
- FastAPI skeleton, Docker Compose, GitHub Actions CI and basic tests exist.
- Dashboard tasks and timer are still in-memory demo state, not persistent.
- Confirmed green foundation CI: https://github.com/l1234-tech/personal-os/actions/runs/39684779365.

### Auth/security branch
- SQLAlchemy models: users, invitations and server-side user sessions.
- Alembic initial migration for auth tables.
- Argon2 password hashing; opaque session/invite tokens stored as SHA-256 hashes.
- Endpoints: invite-only registration, login, logout, authenticated `GET /api/v1/auth/me`.
- Invitation issuance is disabled unless `BOOTSTRAP_INVITATION_SECRET` is configured; secret comparison uses constant time.
- Session cookie is HttpOnly, SameSite=Lax, configurable Secure; cookie-authenticated mutations check Origin.
- Docker image contains migration files and applies `alembic upgrade head` before starting API in local Compose.
- Tests cover password/token hashing, auth guards and PostgreSQL-backed registration/login/logout, invitation email binding/expiry, duplicate registration and invalid credentials.
- CI now starts a PostgreSQL 16 service for backend tests and cancels superseded runs on the same ref.
- React `AuthGate` checks `/auth/me`, provides login and invite-only registration forms, sends cookies with `credentials: include`, and supports logout. Tokens/passwords are not written to localStorage.
- Latest commits add integration tests and fix TypeScript/fixture issues found by CI. **CI for the current head is queued/running; do not treat it as green yet.** Latest run: https://github.com/l1234-tech/personal-os/actions/runs/39686866316. Last confirmed green CI before these additions: https://github.com/l1234-tech/personal-os/actions/runs/39686541508.

## Important constraints
- Do not call the project production-ready solely because CI passes.
- Before adding private-data CRUD, implement and test ownership checks on every API operation.
- Before production, add rate limiting, HTTPS/secure deployment config, robust secret management and operational invitation workflow.
- Never log tokens, passwords, OAuth credentials or personal data.
- A calendar event is not proof work occurred; a scheduled lesson is not proof it happened; accrued tutoring income is not the same as paid.
- Calendar writes require confirmation. Sync jobs must be idempotent.
- Full personal finance and bank statement imports remain post-MVP.

## Next steps
1. Confirm CI for the current auth branch head; fix any remaining Ruff/mypy/pytest/ESLint/TypeScript/build errors.
2. Review the new auth integration tests and verify they really run against the PostgreSQL service in CI.
3. Add rate limiting and strengthen CSRF/origin policy. Require Secure cookies and robust secrets in production.
4. Implement user-owned task CRUD + PostgreSQL persistence and ownership-isolation tests in `feat/tasks-time-tracking`.
5. Continue Calendar/planning, tutoring, study/projects and integrations/analytics in separate PRs with tests/CI.
6. Do not merge to main without user review/approval.

## Stop/resume workflow
- Read this file before continuing.
- Work in small focused commits, inspect CI failures and rerun checks.
- On stop, update this file with branch/commit, completed work, test results, risks and exact next action.
- Never claim checks passed unless GitHub Actions or local execution confirms them.


## Stop checkpoint — 2026-10-22

### Exact repository state
- Branch: `feat/auth-security`
- Exact branch HEAD: `7083c202d76143638685d48a5076a57778612208`
- Auth PR #3: https://github.com/l1234-tech/personal-os/pull/3 — open, draft, base `feat/foundation`; not merged.
- This checkpoint commit updates documentation only; no new application-code changes were started after the requested stop.

### CI status at checkpoint
Both latest workflow runs for the exact current HEAD completed successfully:
- Backend + frontend run 39686961537: success — https://github.com/l1234-tech/personal-os/actions/runs/39686961537
- Backend + frontend run 39686952679: success — https://github.com/l1234-tech/personal-os/actions/runs/39686952679

Older runs on earlier commits failed or were cancelled during rapid commits. The failures seen earlier included frontend TypeScript issues (now fixed) and Ruff lint issues in auth tests (now fixed). Those historical failures do not describe the current HEAD, but the code still needs human/security review and deeper validation.

### Work completed
- Auth models/migration and invite-only registration, login, logout, and `GET /api/v1/auth/me`.
- Argon2 password hashing; opaque invitation/session tokens are stored as hashes.
- HttpOnly, SameSite=Lax session cookie; configurable Secure setting; Origin check on cookie-authenticated mutations.
- Optional bootstrap invitation endpoint is unavailable when no server-side bootstrap secret is configured.
- React AuthGate provides login, invitation registration, existing-session check, and logout. Requests include cookies; auth tokens are not written to localStorage.
- CI provisions PostgreSQL 16 and runs backend checks; workflow concurrency cancels superseded runs.
- Auth integration tests cover registration/login/logout, invitation email binding/expiry, duplicate registration, and invalid credentials.
- `docs/PROGRESS.md` is the durable handoff file.

### Not yet verified / remaining risks
- CI success is not a security audit and does not establish production readiness.
- No production deployment has been verified. Rate limiting, HTTPS enforcement, secure production cookie configuration, managed secrets, invitation operations, and account recovery still need work.
- Ownership isolation for future user-owned task/student/project CRUD is not implemented yet; do not expose private-data CRUD until every endpoint enforces and tests ownership.
- The dashboard tasks and timer remain demo/in-memory state, not durable PostgreSQL features.
- Auth tests use a disposable CI PostgreSQL database; ensure tests are never pointed at real user data.
- OAuth integrations, calendar sync, persistent task/time CRUD, tutoring workflows, and analytics remain incomplete.
- Full personal-finance module and bank statement import remain post-MVP.

### Single next action
Review PR #3 and its auth integration tests, then run a focused security/configuration review (especially Origin/CSRF behavior, production cookie defaults, invitation bootstrap, and session expiry) before starting task CRUD. Keep the PR in draft and do not merge without user approval.
