# Changelog

All notable changes to antcrew-engine are documented here.

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
