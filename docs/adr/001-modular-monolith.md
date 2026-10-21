# ADR-001: модульный монолит

- Status: accepted for MVP
- Date: 2026-10-22

## Context
Personal OS covers tasks/time, studies, tutoring, projects, calendar sync, analytics and notifications. Initial usage is personal/small-scale and needs rapid iteration. There is no evidence justifying microservices.

## Decision
Use a modular FastAPI monolith, PostgreSQL, React PWA and separate worker process for long-running/periodic jobs. Domain modules stay separate packages, external services are behind adapters.

## Consequences
Pros: simpler deployment, migrations, transactions, testing and debugging. Cons: discipline is needed to avoid cyclic dependencies. Revisit only when measured scale or independent deployability needs justify it.
