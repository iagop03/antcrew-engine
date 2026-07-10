# Changelog

All notable changes to antcrew-engine are documented here.

## [0.3.4] — 2026-07-10

### Security
- **`DependencyInstaller`: full sandbox for `pip install`** — when `ANTCREW_SANDBOX=auto|required` and Docker is available, the capability now skips the host-side venv entirely and stores `docker_mode: True` in `venv_config`. `TestRunner` then runs a single container (`docker run --rm`) that executes `pip install -r requirements.txt && pytest` sequentially — both steps are isolated from the host. Malicious `setup.py` post-install hooks and test code can no longer touch the host filesystem or processes.
- **`sandbox.use_docker()`** — new public helper that returns `True` when the current configuration would route execution through Docker; used by both capabilities to branch consistently.
- **`sandbox.run_with_install()`** — new function that composes `pip install` and the test command into a single `/bin/sh -c "pip install … && pytest …"` Docker invocation. Network is intentionally open (pip needs it); the entire session is contained inside Docker.

### Changed
- `TestRunner._resolve_python()` returns `"python"` when `venv_config.docker_mode` is `True` — the Docker image provides its own interpreter, no host venv path needed.
- `_run_in_tempdir` (MemoryStore path) now accepts `requirements_content` and writes it to the temp dir before calling `run_with_install()`, so the MemoryStore path gets the same isolation as the FilesystemStore path.

---

## [0.3.3] — 2026-07-10

### Fixed
- `__version__` dynamic read via `importlib.metadata` now actually shipped in the published wheel — 0.3.2 on PyPI still contained the hardcoded string `"0.2.0"`; 0.3.3 is the first release where `antcrew_engine.__version__` matches the installed version at runtime.

---

## [0.3.2] — 2026-07-09

### Fixed
- `__version__` now reads dynamically from installed package metadata so it always matches the installed release.
- CI: `ANTCREW_SANDBOX=none` env var prevents test-runner from launching Docker on CI runners where the host Python path doesn't exist inside the container.
- `pypa/gh-action-pypi-publish` configured with `skip_existing: true` so workflow re-runs don't fail if a file was already uploaded.

### Changed
- Publish workflow uses `PYPI_API_TOKEN` secret instead of OIDC Trusted Publishing.

---

## [0.3.1] — 2026-07-09

### Fixed
- `build_llm`: raises `ValueError` for unrecognised model strings before attempting any API call — previously fell through to `AnthropicModel` and raised `EnvironmentError: ANTHROPIC_API_KEY not set` for non-Anthropic model names.
- `GroqModel`: lazy-imported so CI environments without the `groq` package don't fail on import.
- Test assertions corrected: SpyLLM captures the `system` prompt (where architecture is injected) rather than the `user` message.

---

## [0.3.0] — 2026-07-09

### Added
- **Docker sandbox (escalón 0)** — `TestRunner` can run generated tests inside a temporary Docker container (`ANTCREW_SANDBOX=docker`). Falls back to direct subprocess when Docker is unavailable. Controlled via `ANTCREW_SANDBOX` env var (`auto` | `docker` | `none`).

### Changed
- `Operator` → `EngineLoop`, `OperatorDecision` → `EngineDecision`, `OperatorError` → `EngineLoopError`. Old names re-exported for backward compatibility.
- Diff preview now works correctly for `MultiRepoStore` with `--from-dir`.

---

## [0.2.0] — 2026-07-09

### Added
- **MultiRepoStore** — routes artifact writes to different `FilesystemStore` roots by `file_path` prefix; longest prefix wins; `read/list/has` search all repos transparently. Exported from `antcrew_engine`, `antcrew_engine.engine`, and `antcrew` root.
- **Cache hit metrics** — `AnthropicModel._record_usage()` tracks `cache_read_tokens` / `cache_write_tokens` per call. `get_usage_summary()` now returns `total_cache_read_tokens` and `total_cache_write_tokens`. `CapabilityResult` carries `cache_read_tokens: int` and `cache_write_tokens: int`.
- **`EventBusBridge` cache fields** — `agent.end` payload now includes `cache_read_tokens` and `cache_write_tokens` for platform dashboards and cost attribution.
- **`--from-dir` CLI flag** — `antcrew-engine run --from-dir <path>` loads an existing codebase into the store and writes stub planning artifacts so the engine skips Architect/TaskPlanner and jumps directly to the requested capability.
- **`--repo` / `--route` CLI flags** — multi-repo routing directly from the CLI. `--repo name:path` (repeatable) + `--route prefix:name` (repeatable) builds a `MultiRepoStore` automatically.
- **`--resume` CLI flag** — reloads goal metadata and artifacts from a prior `FilesystemStore` run.
- **Cache summary in CLI output** — `_on_complete` prints `↓Xr ↑Xw` cache indicator per capability; final summary shows aggregate cache hit rate.
- **`_ensure_conftest`** (TestRunner) — writes a root `conftest.py` that adds the project dir to `sys.path`; skipped if the user already has one. Idempotent.
- **`PYTHONPATH` injection** (TestRunner) — both the filesystem and temp-dir execution paths now set `PYTHONPATH=<root>` in the subprocess environment.
- **README.md** — full usage documentation: CLI flags, Python API quick-start, multi-repo example, capability table, model support table.
- **Unit tests**:
  - `tests/engine/test_multi_repo_store.py` — routing by prefix, read across repos, `list()` deduplication, `apply()`, `stores()` accessor, `_load_existing_codebase`, `_ensure_conftest` (55 tests total in the test suite)
  - `tests/capabilities/test_dependency_installer.py` — `_find_existing_requirements`, `_resolve_venv_path`, `_python_bin/_pip_bin`, `_ensure_venv`, `_install` (all via subprocess mock)
  - `tests/cli/test_cli_helpers.py` — `_build_store` store-type selection and bad-spec validation; `_load_existing_codebase` file-type loading, skip-dir logic, metadata; smoke tests for `run` and `status` commands with `--model simulated`

### Fixed
- **TestRunner**: `_run_on_filesystem` no longer calls `_ensure_init_files` on the test directory — pytest prefers test dirs without `__init__.py`. Only source packages get `__init__.py` injection.

### Changed
- `_build_store` helper extracted from the `run` command to make store construction independently testable.

---

## [0.1.0] — 2026-06-20

Initial release — antcrew-engine extracted from the antcrew monorepo as a standalone Layer 2 package.

### Included
- `Operator` loop: observe → decide → dispatch → validate, until `DesiredProjectState` is reached
- `CapabilityRegistry` with pluggable executors
- `ArtifactStore` protocol: `MemoryStore`, `FilesystemStore`
- Capabilities: `Architect`, `TaskPlanner`, `CodeGenerator`, `CodeRegenerator`, `TestGenerator`, `TestRunner`, `BugFixer`, `CodeReviewer`, `ReviewFixer`, `DependencyInstaller`, `DocGenerator`, `HitlReviewer`, `SpecExtractor`
- Model adapters: `AnthropicModel`, `OpenAIModel`, `GroqModel`, `GeminiModel`, `OllamaModel`, `SimulatedLLM` (test stub)
- `EventLog` + `EventBusBridge` for platform integration
- CLI entry point `antcrew-engine` with `run` and `status` commands
- Validators: `artifact_validators`, `AllTasksCompleted`, `TestsExist`, `TestsPass`, `CodeReviewed`, `DocumentationExists`, `DependenciesInstalled`
