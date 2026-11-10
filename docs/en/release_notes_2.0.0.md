# Release Notes — Temporal Boost 2.0.0

## 🚀 Major Changes

### Project Restructure

- All Temporal-related logic is now under `temporal_boost/temporal/` (client, config, runtime, worker).
- New `workers/` package with dedicated ASGI workers (uvicorn, hypercorn, granian) and Temporal worker.
- Deprecated and internal modules removed (`connect.py`, `core.py`, `logger.py`, `schemas.py`, `tracing.py`, old `worker.py`).
- Examples updated to reflect the new structure.

### Configuration via Environment Variables

- All client and worker configuration is now handled via environment variables (see `temporal_boost/temporal/config.py`).
- No more direct passing of endpoint, namespace, or logger config to `BoostApp` — use env vars instead.

### New Builders and Extensibility

- `TemporalClientBuilder`, `TemporalWorkerBuilder`, and runtime creation helpers for advanced customization.
- Flexible runtime and client configuration for advanced use cases.

### ASGI Worker Registry

- Support for multiple ASGI worker types (uvicorn, hypercorn, granian) with auto-detection.
- Easy integration of FastAPI or any ASGI app as a worker.

### DevOps and Tooling

- Updated dependencies, new pre-commit hooks, VSCode tasks, and improved development workflow.
- Poetry 2.x support.

### Tests Removed

- All test files and fixtures have been removed for this release. (Tests will be reworked in future versions.)

---

## ⚠️ Breaking Changes

- Old API for `BoostApp` initialization and worker registration is no longer supported.
- All configuration must now be provided via environment variables or new builder classes.
- Internal worker for documentation is deprecated/removed.
- All test-related files and fixtures are removed from the repository.

---

## 🛠 Migration Guide

1. **Update Imports**
   - Use new modules: `temporal_boost.temporal` and `temporal_boost.workers`.

2. **Configuration**
   - Move all configuration (endpoint, namespace, TLS, metrics, etc.) to environment variables.
   - See `temporal_boost/temporal/config.py` for all available options.

3. **Worker Registration**
   - Replace old worker registration with the new builder-based approach:

     ```python
     app.add_worker("worker_1", "queue_1", activities=[...], workflows=[...])
     ```

   - For ASGI apps, use:

     ```python
     app.add_asgi_worker("asgi_worker", fastapi_app, "0.0.0.0", 8000, worker_type="auto")
     ```

4. **Remove Internal Worker Usage**
   - The internal documentation worker is no longer available.

5. **Update Examples**
   - See the updated `examples/` directory and documentation for new usage patterns.

---

## 🆕 New Features

- Environment-based configuration for all core settings.
- Pluggable ASGI worker types (uvicorn, hypercorn, granian) with auto-detection.
- Improved modularity and extensibility for advanced users.
- Cleaner, more maintainable codebase.
