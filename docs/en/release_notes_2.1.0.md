# Release Notes — Temporal Boost 2.1.0 {#release-notes-temporal-boost-210}

Temporal Boost 2.1.0 collects the changes delivered after 2.0.2. The release focuses on worker lifecycle safety, predictable CRON and process behavior, clearer configuration rules, complete metrics, and a rebuilt multilingual documentation portal.

## Highlights {#highlights}

- Worker failures now reach the application coordinator and the command-line process with their original status.
- Temporal, ASGI, FastStream, and custom workers share an explicit managed shutdown contract.
- CRON registration uses stable workflow IDs and validates incomplete configurations before connecting.
- Prometheus metrics are exposed per runtime and per process with preserved telemetry configuration.
- Configuration precedence, `None`, zero, and post-initialization changes are handled explicitly.
- The project now has a comprehensive English and Russian Zensical portal with strict builds, browser checks, and rollback artifacts.

## Worker lifecycle and reliability {#worker-lifecycle}

### Failure propagation and cleanup {#failure-propagation}

- Worker thread and async failures are propagated to the coordinator instead of being logged and lost.
- Startup failures clean up resources that were already created, including partially initialized Temporal workers.
- Cleanup failures cannot hide the original lifecycle error, and repeated stop requests are safe.
- Graceful shutdown uses `TEMPORAL_GRACEFUL_SHUTDOWN_TIMEOUT` for Temporal SDK workers. A zero value requests immediate shutdown; negative values are rejected.

### Managed shutdown {#managed-shutdown}

- Temporal, FastStream, and built-in ASGI workers now wait for their own lifecycle cleanup and support repeated runs safely.
- Custom workers can participate through `request_stop()` or `AsyncBoostWorker`; unsupported workers are rejected clearly.
- Lifecycle state prevents concurrent runs, rejects unsafe configuration changes, and allows configuration again after a complete stop.

## CRON workers {#cron-workers}

- CRON workers receive a stable default workflow ID derived from their task queue and worker name, or an explicit `cron_workflow_id`.
- Concurrent starts reuse an active workflow and reject a closed workflow instead of creating a duplicate chain.
- `cron <name>` registers or resumes the server-side chain; `run <name>` and `run all` only consume task queues.
- `cron_schedule` and `cron_runner` must be supplied together or omitted together. Empty schedules, partial pairs, and direct CRON calls on ordinary workers fail before connecting.
- Existing deployments that used random CRON UUIDs need the documented duplicate-chain migration procedure.

## ASGI, FastStream, and process execution {#asgi-faststream-processes}

- Uvicorn, Hypercorn, and Granian now expose consistent startup, lifespan, stop, and error behavior.
- External multiprocess ASGI execution rejects configurations that would bind the same server more than once. Help and safe non-ASGI commands remain available.
- FastStream workers manage broker startup and shutdown, preserve lifecycle errors, and support coordinator-driven stopping.
- The process runner supervises every child, stops peers after a failure, reaps process handles, and preserves nonzero exit statuses.
- The CLI now preserves explicit command exit codes and reports unexpected worker completion as failure.

## Configuration and extensibility {#configuration-and-extensibility}

- Pydantic converter overrides preserve explicit boolean values, including `False`.
- Environment defaults are captured at import time; explicit application, client, and worker settings follow documented precedence rules.
- `None` means “inherit” only where documented. Zero remains valid for ratios and shutdown grace periods, while worker counts must be positive.
- Runtime configuration is fixed after initialization; unsupported changes are rejected without mutating the existing builder.
- Custom worker registration has a consistent contract, unique names, reserved command checks, and a documented async shutdown pattern.
- Application import diagnostics distinguish a missing target module from a missing dependency, syntax error, or application initialization failure.

## Metrics and telemetry {#metrics-and-telemetry}

- Each Temporal runtime can expose its own Prometheus endpoint, including multiple workers in multiple processes.
- Metrics endpoints must be distinct; a bind conflict preserves the original telemetry configuration and fails instead of silently disabling metrics.
- SDK metrics are not aggregated through `PROMETHEUS_MULTIPROC_DIR`; scrape every runtime endpoint or use an external collector.
- Metrics examples and deployment guidance now cover endpoint allocation, process topology, and health checks.

## Documentation and tooling {#documentation-and-tooling}

- The documentation was expanded with configuration, lifecycle, CRON, metrics, custom-worker, FastStream, and troubleshooting guidance.
- The portal migrated from the old single-locale MkDocs setup to a multilingual Zensical portal with English and Russian routes, Temporal branding, and preserved legacy URLs.
- Documentation builds are isolated in `tools/docs`, run strict portal and route checks, install a pinned browser, and verify generated pages with browser tests.
- Main-branch publication uses a verified artifact and updates the legacy `gh-pages` branch; successful artifacts can be restored without rebuilding.
- CI, examples, tests, packaging, and dependency management were updated around uv and the supported Python versions.

## Security and dependency updates {#security-and-dependencies}

- The locked runtime and documentation dependencies were updated to remove all Dependabot-reported vulnerable versions.
- Updates cover transitive packages used by FastAPI, ASGI servers, metrics, test tooling, documentation tooling, and pre-commit.
- The release adds focused unit, integration, lifecycle, process, metrics, and browser coverage for the new behavior.

## Migration notes {#migration-notes}

- Review CRON workers created before 2.1.0 and remove verified duplicate chains before adopting stable IDs.
- Do not start ASGI workers through multiple external processes unless each process has a distinct server responsibility.
- Give custom workers a managed stop implementation and ensure worker names do not use reserved CLI commands.
- Set environment variables before importing `temporal_boost`; use explicit constructor or builder settings when configuration must differ after import.
- Scrape each configured metrics endpoint and allocate a unique endpoint to every runtime.
