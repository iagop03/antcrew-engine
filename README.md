# antcrew-engine

Capability-driven autonomous project execution engine — **Layer 2** of the [antcrew](https://github.com/iagop03/antcrew) stack.

The engine iterates an `EngineLoop` over a natural-language goal, dispatching modular `Capability` executors until every condition in the desired project state is satisfied. No LangGraph dependency — designed to be embedded directly or wrapped by antcrew (Layer 1).

## When to use antcrew-engine vs antcrew

**Use antcrew-engine (Layer 2)** when you want a fully autonomous loop that builds or modifies code without a fixed pipeline of named roles. The `EngineLoop` is goal-directed — it reads the current artifact state, picks the cheapest capability that closes the gap toward the desired conditions, and repeats. The set of steps is not known in advance; it emerges from what's already been done. This is the right model for brownfield work (`--from-dir`), resume runs, and any task where the pipeline structure shouldn't be hardcoded.

**Use antcrew (Layer 1)** when you want a structured pipeline of named agents (Business Analyst → PM → Backend Dev → QA → Reviewer) orchestrated with LangGraph, with explicit human-in-the-loop between roles, project sessions across multiple runs, and semantic memory. Layer 1 depends on Layer 2 — all its capabilities are re-exported from `antcrew_engine`.

## Architecture

```
Goal + Constraints
       │
       ▼
  EngineLoop ─── CapabilityRegistry
       │              │
       │    ┌─────────┴──────────────────────────────┐
       │    │  Architect   TaskPlanner   CodeGenerator │
       │    │  TestRunner  BugFixer      HitlReviewer  │
       │    │  CodeReviewer  DocGenerator  ...         │
       │    └─────────────────────────────────────────┘
       │
       ▼
  ArtifactStore  (MemoryStore | FilesystemStore | MultiRepoStore)
```

Each capability reads from and writes to the store. The `EngineLoop` picks the cheapest applicable capability until the `DesiredProjectState` is reached.

## Install

```bash
pip install antcrew-engine
# with Anthropic support:
pip install "antcrew-engine[anthropic]"
# all model providers:
pip install "antcrew-engine[all]"
```

## Quick start — CLI

```bash
# Build a REST API, write output to ./my-api
antcrew-engine "Build a FastAPI REST API with user authentication" \
  --tech Python --output ./my-api

# Load an existing project (skips planning, jumps to coding/testing)
antcrew-engine "Add docstrings to all public functions" \
  --from-dir ./my-project --output ./my-project

# Multi-repo routing (write to different repos by file prefix)
antcrew-engine "Build a full-stack app" \
  --repo backend:/repos/api --repo frontend:/repos/ui \
  --route src/api/:backend --route src/ui/:frontend

# Resume a prior run
antcrew-engine --resume --output ./my-api

# Inspect an existing output directory
antcrew-engine status ./my-api
```

## Quick start — Python API

```python
from antcrew_engine import (
    Operator, MemoryStore, Goal, DesiredProjectState, Constraints,
    Condition, ConditionId, CapabilityRegistry, EventLog, build_llm,
    Architect, TaskPlanner, CodeGenerator, TestGenerator, TestRunner,
    BugFixer, CodeReviewer, DocGenerator, DependencyInstaller,
)

llm = build_llm("claude")   # or "gpt-4o", "groq:llama3-70b", "simulated"

registry = CapabilityRegistry()
registry.register(Architect(llm=llm))
registry.register(TaskPlanner(llm=llm))
registry.register(CodeGenerator(llm=llm))
registry.register(TestGenerator(llm=llm))
registry.register(TestRunner())
registry.register(BugFixer(llm=llm))
registry.register(CodeReviewer(llm=llm))
registry.register(DocGenerator(llm=llm))
registry.register(DependencyInstaller(llm=llm))

store = MemoryStore()

goal = Goal(
    description="Build a CLI tool that converts Markdown to HTML",
    desired_state=DesiredProjectState(frozenset([
        Condition(ConditionId("requirements_exists"), "requirements written"),
        Condition(ConditionId("architecture_exists"), "architecture designed"),
        Condition(ConditionId("task_graph_exists"),   "tasks planned"),
        Condition(ConditionId("implementation_exists"), "code written"),
        Condition(ConditionId("tests_pass"),           "tests passing"),
        Condition(ConditionId("documentation_exists"), "README written"),
    ])),
    constraints=Constraints(tech_stack=("Python",)),
)

event_log = EventLog()
operator  = Operator(registry, [], event_log, max_iterations=40)
state     = operator.run(store, goal)

print("Success:", state.is_complete)
for artifact in store.list():
    print(f"  {artifact.id}: {artifact.kind.value}")
```

## Multi-repo store

Route artifact writes to different filesystem roots by file-path prefix:

```python
from antcrew_engine import MultiRepoStore

store = MultiRepoStore(
    repos={
        "backend":  "/repos/api",
        "frontend": "/repos/ui",
        "shared":   "/repos/shared",
    },
    routes={
        "src/api/": "backend",
        "src/ui/":  "frontend",
    },
    default="shared",
)
```

## Capabilities

| Capability | Description |
|---|---|
| `Architect` | Writes requirements + architecture documents |
| `TaskPlanner` | Breaks architecture into a task graph |
| `CodeGenerator` | Implements tasks in parallel |
| `CodeRegenerator` | Regenerates code after a bad review |
| `TestGenerator` | Writes a pytest test suite |
| `TestRunner` | Runs pytest, produces a test report |
| `BugFixer` | Reads the traceback, patches failing files |
| `CodeReviewer` | Reviews code, produces an approval or rejection |
| `ReviewFixer` | Applies reviewer feedback to source files |
| `DependencyInstaller` | Infers requirements.txt and installs a venv |
| `DocGenerator` | Writes README.md |
| `HitlReviewer` | Pauses for human approval before proceeding |
| `SpecExtractor` | Extracts a structured spec from a free-form description |

## Model support

Pass a model string to `build_llm()`:

| String | Provider |
|---|---|
| `"claude"` | Anthropic claude-sonnet (default) |
| `"claude-haiku-4-5-20251001"` | Anthropic Haiku (cheap/fast) |
| `"gpt-4o"` | OpenAI |
| `"groq:llama3-70b-8192"` | Groq |
| `"ollama:llama3"` | Ollama (local) |
| `"gemini"` | Google Gemini |
| `"simulated"` | Deterministic stub (tests / CI) |

## License

MIT
