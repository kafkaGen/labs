# Vision: labs-logging

**Status:** Active
**In one line:** One shared Python logging package so every application in the labs monorepo logs the same way.

## Problem

Each application would otherwise set up its own logging: its own format, its own files, its own cleanup. Output differs from app to app, files grow without limit, and two copies of the same app can overwrite each other's logs. One shared package fixes this once, before more applications exist.

## Goal

An application sets up logging with one config and one call, and gets readable console output, structured log files that stay bounded, and a way to send logs elsewhere later.

## Learning objectives

Not a learning project. It is a utility, so this section does not apply.

## Users

Me, writing applications in this monorepo.

## Core use cases

- I start an application and read colorful, structured logs in the terminal.
- I run two copies of an application and each writes its own log files.
- I look at the logs of a past run, and old runs clean themselves up.
- I add a handler that ships logs to Azure Blob or S3 without editing the package.

## In scope

- Console and file output from one structured event.
- Logger families per application, with a level per logger.
- Capture of standard-library and third-party logs.
- Size-bounded files and retention of whole runs.
- Custom handlers.

## Out of scope

- Ready-made cloud handlers (Azure Blob, S3). They return when a second application needs one.
- Batched or buffered file writes. They return if measured write cost becomes a problem.

## Non-goals

- **Log aggregation, search, or dashboards:** a collector does that, not a logging package.
- **Metrics or distributed tracing:** a different concern with different tools.
- **Secret or PII redaction:** it cannot know what is sensitive. Callers must not log secrets.
- **One file written by several processes:** each run owns its files, so processes never share one.

## Success criteria

- Two different applications in this repo log through it, and neither has logging code beyond one config and one call.
- Two simultaneous runs of one application leave two separate sets of files.

## Constraints

- **Stdout is reserved:** MCP stdio servers carry their protocol on it, so the console writes to stderr.
- **Runs inside the monorepo:** a uv workspace package on Python 3.12 or newer.
- **Time budget:** Assumed: none fixed.
