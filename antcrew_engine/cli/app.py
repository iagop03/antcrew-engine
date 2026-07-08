"""antcrew-engine CLI — standalone entry point for the capability-driven engine.

Usage:
    antcrew-engine "Build a REST API" --tech Python --output ./my-api
    antcrew-engine --resume --output ./my-api
    antcrew-engine status ./my-api
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from antcrew_engine.engine import (
    Artifact, ArtifactId, ArtifactKind,
    CapabilityRegistry, Condition, ConditionId, Constraints,
    DesiredProjectState, EventLog, FilesystemStore, Goal, MemoryStore, Operator,
)
from antcrew_engine.capabilities import (
    Architect, BugFixer, CodeGenerator, CodeRegenerator, CodeReviewer,
    DependencyInstaller, DocGenerator, ReviewFixer, TaskPlanner, TestGenerator, TestRunner,
)
from antcrew_engine.capabilities.validators import (
    AllTasksCompletedValidator, CodeReviewedValidator, DependenciesInstalledValidator,
    DocumentationExistsValidator, TestsExistValidator, TestsPassValidator, artifact_validators,
)
from antcrew_engine.config import build_llm as _build_llm

app = typer.Typer(
    name="antcrew-engine",
    help="Capability-driven engine: autonomously builds software from a goal.",
    add_completion=False,
)
console = Console()

_MODEL_HELP = (
    "Model string: 'claude' (default), 'claude-haiku-4-5-20251001', "
    "'gpt-4o', 'ollama:llama3', 'groq:llama3-70b', 'gemini', 'simulated'."
)

_GOAL_META_REL = Path(".antcrew") / "goal.json"


# ---------------------------------------------------------------------------
# Registry / helpers (shared with engine_cmd.py shim)
# ---------------------------------------------------------------------------

def _parse_capability_config(
    config_file: "Optional[Path]",
) -> "tuple[dict[str, str], dict[str, bool]]":
    if config_file is None:
        return {}, {}
    try:
        import yaml as _yaml
        raw = _yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except ImportError:
        import json as _json
        raw = _json.loads(config_file.read_text(encoding="utf-8"))
    caps = raw.get("capabilities", {}) if isinstance(raw, dict) else {}
    models: dict[str, str] = {}
    caching: dict[str, bool] = {}
    for name, cfg in caps.items():
        if not isinstance(cfg, dict) or "model" not in cfg:
            continue
        models[name] = str(cfg["model"])
        if "prompt_caching" in cfg:
            caching[name] = bool(cfg["prompt_caching"])
    return models, caching


def _build_registry(
    llm,
    model_str: str = "claude",
    *,
    capability_models: "dict[str, str] | None" = None,
    capability_caching: "dict[str, bool] | None" = None,
    default_prompt_caching: bool = True,
    max_tasks: int = 12,
    parallel_workers: int = 5,
) -> CapabilityRegistry:
    cap_models  = capability_models  or {}
    cap_caching = capability_caching or {}

    def _llm(cap_name: str):
        cap_model = cap_models.get(cap_name, model_str)
        cap_pc    = cap_caching.get(cap_name, default_prompt_caching)
        if cap_model != model_str or cap_name in cap_caching:
            return _build_llm(cap_model, prompt_caching=cap_pc)
        return llm

    registry = CapabilityRegistry()
    registry.register(Architect(llm=_llm("architect")))
    registry.register(TaskPlanner(llm=_llm("task_planner"), max_tasks=max_tasks))
    registry.register(CodeGenerator(llm=_llm("code_generator"), parallel_workers=parallel_workers))
    registry.register(DependencyInstaller(llm=_llm("dependency_installer")))
    registry.register(TestGenerator(llm=_llm("test_generator")))
    registry.register(TestRunner())
    registry.register(BugFixer(llm=_llm("bug_fixer")))
    registry.register(CodeRegenerator(llm=_llm("code_regenerator")))
    registry.register(CodeReviewer(llm=_llm("code_reviewer")))
    registry.register(ReviewFixer(llm=_llm("review_fixer")))
    registry.register(DocGenerator(llm=_llm("doc_generator")))
    return registry


def _build_validators() -> list:
    return [
        *artifact_validators(
            ("requirements", "requirements_exists"),
            ("architecture", "architecture_exists"),
            ("task_graph",   "task_graph_exists"),
        ),
        AllTasksCompletedValidator(),
        DependenciesInstalledValidator(),
        TestsExistValidator(),
        TestsPassValidator(),
        CodeReviewedValidator(),
        DocumentationExistsValidator(),
    ]


def _build_goal(description, tech_stack, conditions, full) -> Goal:
    default_conditions = [
        ("requirements_exists",    "requirements document written"),
        ("architecture_exists",    "architecture designed"),
        ("task_graph_exists",      "tasks planned"),
        ("implementation_exists",  "all tasks implemented"),
        ("dependencies_installed", "project dependencies installed"),
        ("tests_exist",            "test suite written"),
        ("tests_pass",             "tests passing"),
        ("code_reviewed",          "code reviewed and approved"),
        ("documentation_exists",   "README.md written"),
    ] if full else [
        ("requirements_exists", "requirements document written"),
        ("architecture_exists", "architecture designed"),
        ("task_graph_exists",   "tasks planned"),
    ]

    if conditions:
        cond_set = frozenset(Condition(ConditionId(c.strip()), c.strip()) for c in conditions)
    else:
        cond_set = frozenset(Condition(ConditionId(cid), desc) for cid, desc in default_conditions)

    return Goal(
        description=description,
        desired_state=DesiredProjectState(cond_set),
        constraints=Constraints(tech_stack=tech_stack) if tech_stack else Constraints(),
    )


def _save_goal_meta(output, description, tech, conditions, full) -> None:
    meta = {"description": description, "tech": tech, "conditions": conditions, "full": full}
    meta_path = output / _GOAL_META_REL
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _load_goal_meta(output) -> "dict | None":
    meta_path = output / _GOAL_META_REL
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_output(store: MemoryStore, output_dir: Path) -> list[Path]:
    written: list[Path] = []
    for kind in (ArtifactKind.SOURCE, ArtifactKind.TEST,
                 ArtifactKind.DOCUMENTATION, ArtifactKind.CONFIG):
        for artifact in store.list(kind):
            file_path = artifact.metadata.get("file_path") or str(artifact.id)
            dest = output_dir / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = (artifact.content if isinstance(artifact.content, str)
                       else json.dumps(artifact.content, indent=2))
            dest.write_text(content, encoding="utf-8")
            written.append(dest)
    return written


def _print_summary(store, output_dir, written) -> None:
    table = Table(title="Engine Run Summary", show_header=True, header_style="bold dim")
    table.add_column("Artifact kind", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right")
    for kind in ArtifactKind:
        items = store.list(kind)
        if items:
            table.add_row(kind.value, str(len(items)))
    console.print()
    console.print(table)
    if output_dir and written:
        console.print(f"\n[green]Wrote {len(written)} file(s) to[/] [bold]{output_dir}[/]")
        for p in written[:10]:
            console.print(f"  [dim]{p.relative_to(output_dir)}[/]")
        if len(written) > 10:
            console.print(f"  [dim]... and {len(written) - 10} more[/]")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def run(
    goal_description: Optional[str] = typer.Argument(
        None, metavar="GOAL",
        help="Natural language goal. Optional when --resume is set.",
    ),
    model:       str           = typer.Option("claude",  "--model", "-m", help=_MODEL_HELP),
    config_file: Optional[Path] = typer.Option(None,     "--config",
                                               help="YAML with per-capability model overrides."),
    output:    Optional[Path] = typer.Option(None, "--output", "-o",
                                             help="Directory for artifacts (enables FilesystemStore)."),
    tech:      list[str] = typer.Option([], "--tech", "-t"),
    condition: list[str] = typer.Option([], "--condition", "-c"),
    full:      bool = typer.Option(True, "--full/--plan-only"),
    max_iter:  int  = typer.Option(50,   "--max-iter"),
    resume:    bool = typer.Option(False, "--resume/--no-resume"),
    fix_attempts: int = typer.Option(3,  "--fix-attempts"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost"),
    max_tasks: int = typer.Option(12, "--max-tasks"),
    parallel_workers: int = typer.Option(5, "--parallel-workers"),
    no_cache: bool = typer.Option(False, "--no-cache"),
) -> None:
    """Run the engine to build a software project from a goal."""
    if resume and output is not None:
        meta = _load_goal_meta(output)
        if goal_description is None:
            if meta is None:
                console.print("[red]--resume: no goal.json found in output directory.[/]")
                raise typer.Exit(code=1)
            goal_description = meta["description"]
            tech      = tech      or meta.get("tech", [])
            condition = condition or meta.get("conditions", [])
            full      = meta.get("full", full)
            console.print(f"[dim]Resuming:[/] {goal_description}")
    elif goal_description is None:
        console.print("[red]Provide a GOAL or use --resume with a prior --output dir.[/]")
        raise typer.Exit(code=1)

    prompt_caching = not no_cache
    llm  = _build_llm(model, prompt_caching=prompt_caching)
    cap_models, cap_caching = _parse_capability_config(config_file)
    goal = _build_goal(goal_description, tuple(tech), condition, full)
    store = FilesystemStore(output) if output is not None else MemoryStore()
    log  = EventLog()
    registry   = _build_registry(
        llm, model,
        capability_models=cap_models,
        capability_caching=cap_caching,
        default_prompt_caching=prompt_caching,
        max_tasks=max_tasks,
        parallel_workers=parallel_workers,
    )
    validators = _build_validators()
    operator   = Operator(
        registry, validators, log,
        max_iterations=max_iter,
        retry_limits={"test_runner": 1, "bug_fixer": fix_attempts, "code_reviewer": 2},
        total_limits={"code_regenerator": 2, "review_fixer": 3},
        max_cost_usd=max_cost,
    )

    resume_note = " [dim](resuming)[/dim]" if resume else ""
    console.print(Panel(
        f"[bold]{goal_description}[/]{resume_note}\n"
        + (f"[dim]Tech: {', '.join(tech)}[/]" if tech else ""),
        title="[cyan]antcrew-engine[/]",
        border_style="cyan",
    ))

    _run_cost  = {"total": 0.0}
    _run_cache = {"read": 0, "write": 0}

    def _on_dispatch(event) -> None:
        console.print(f"  [cyan]>[/] [bold]{event.capability_name}[/]")

    def _on_complete(event) -> None:
        ok = event.result is None or event.result.succeeded
        status = "[green]ok[/]" if ok else "[red]fail[/]"
        t  = event.result.execution_time if event.result else 0.0
        c  = event.result.cost_usd       if event.result else 0.0
        cr = event.result.cache_read_tokens  if event.result else 0
        cw = event.result.cache_write_tokens if event.result else 0
        _run_cost["total"]  += c
        _run_cache["read"]  += cr
        _run_cache["write"] += cw
        cost_str  = f" [dim]${c:.4f} ∑${_run_cost['total']:.4f}[/]" if c else ""
        cache_str = f" [blue]↓{cr:,}r ↑{cw:,}w[/]" if (cr or cw) else ""
        console.print(f"  {status} [dim]{event.capability_name}[/] ({t:.1f}s){cost_str}{cache_str}")

    def _on_satisfied(event) -> None:
        console.print(f"  [green]condition:[/] {event.condition_id}")

    log.subscribe("capability_dispatched", _on_dispatch)
    log.subscribe("capability_completed",  _on_complete)
    log.subscribe("condition_satisfied",   _on_satisfied)

    try:
        final_state = operator.run(store, goal)
    except Exception as exc:
        console.print(f"\n[red bold]Engine error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    if output is not None:
        _save_goal_meta(output, goal_description, list(tech), list(condition), full)

    written: list[Path] = []
    if output is not None and isinstance(store, MemoryStore):
        output.mkdir(parents=True, exist_ok=True)
        written = _write_output(store, output)

    _print_summary(store, output, written)
    total_r = _run_cache["read"]
    total_w = _run_cache["write"]
    if total_r or total_w:
        total_cache = total_r + total_w
        hit_pct = f" ({100 * total_r // total_cache}% hit)" if total_cache else ""
        console.print(
            f"[dim]Cache: [blue]{total_r:,}[/] tokens read, "
            f"[cyan]{total_w:,}[/] written{hit_pct}[/]"
        )
    console.print(f"\n[green bold]Done.[/] {len(final_state.satisfied)} condition(s) satisfied.")


@app.command()
def status(
    project_dir: Path = typer.Argument(..., metavar="DIR"),
) -> None:
    """Inspect the state of a project built by the engine."""
    if not project_dir.exists():
        console.print(f"[red]Directory not found:[/] {project_dir}")
        raise typer.Exit(code=1)

    store = FilesystemStore(project_dir)
    manifest_path = project_dir / ".antcrew" / "manifest.json"
    if not manifest_path.exists():
        console.print(f"[yellow]No engine manifest found in {project_dir}[/]")
        raise typer.Exit(code=1)

    meta = _load_goal_meta(project_dir)
    if meta:
        console.print(Panel(
            f"[bold]{meta['description']}[/]\n"
            + (f"[dim]Tech: {', '.join(meta.get('tech', []))}[/]" if meta.get("tech") else ""),
            title="[cyan]Goal[/]",
            border_style="cyan",
        ))

    art_table = Table(title="Artifacts", show_header=True, header_style="bold dim")
    art_table.add_column("Kind",  style="cyan", no_wrap=True)
    art_table.add_column("ID",    style="white")
    art_table.add_column("Size",  justify="right", style="dim")
    total = 0
    for kind in ArtifactKind:
        for art in store.list(kind):
            content = art.content
            size = (f"{len(content)} chars" if isinstance(content, str)
                    else f"{len(json.dumps(content))} chars")
            art_table.add_row(kind.value, str(art.id), size)
            total += 1
    if total == 0:
        console.print("[yellow]Store is empty.[/]")
        raise typer.Exit()
    console.print(); console.print(art_table)

    validators = _build_validators()
    cond_table = Table(title="Conditions", show_header=True, header_style="bold dim")
    cond_table.add_column("Condition", style="white", no_wrap=True)
    cond_table.add_column("Status",    justify="center")
    cond_table.add_column("Details",   style="dim")
    for v in validators:
        result = v.validate(store)
        icon   = "[green]PASS[/]" if result.satisfied else "[red]FAIL[/]"
        detail = ", ".join(f"{k}={val}" for k, val in (result.observations or {}).items())
        cond_table.add_row(str(result.condition_id), icon, detail[:60])
    console.print(); console.print(cond_table)
    console.print(f"\n[dim]{total} artifact(s) in {project_dir}[/]")
