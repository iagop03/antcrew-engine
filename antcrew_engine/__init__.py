"""antcrew_engine — capability-driven project execution engine (Layer 2).

The engine autonomously builds software by iterating an Operator loop over a
goal until the project reaches a desired state.  It has no dependency on
LangGraph or the supervised multi-agent teams in antcrew (Layer 1).

Quick start::

    from antcrew_engine.engine import Operator, MemoryStore, Goal, DesiredProjectState
    from antcrew_engine.engine import Condition, ConditionId, Constraints
    from antcrew_engine.capabilities import Architect, TaskPlanner, CodeGenerator
    from antcrew_engine.config import build_llm

    llm   = build_llm("claude")
    store = MemoryStore()
    goal  = Goal("build a REST API", DesiredProjectState(...), Constraints())
    op    = Operator(registry, validators, log)
    state = op.run(store, goal)

CLI entry point (installed as ``antcrew-engine``)::

    antcrew-engine "Build a REST API" --tech Python --output ./my-api
"""
from antcrew_engine.engine import (
    Artifact, ArtifactId, ArtifactKind, ArtifactDelta, EMPTY_DELTA,
    ArtifactStore, MemoryStore, FilesystemStore, MultiRepoStore,
    Condition, ConditionId, DesiredProjectState, Constraints, Goal,
    ProjectState,
    CapabilityDescriptor, CapabilityResult, Executor,
    ValidatorResult, Validator,
    CapabilityRegistry,
    EventLog,
    Operator, OperatorError,
    CapabilitySelector, CheapestFirst, FirstMatch, MostProductive, PrioritySelector,
    EventBusBridge,
)
from antcrew_engine.capabilities import (
    Architect, TaskPlanner, CodeGenerator, CodeRegenerator,
    BugFixer, CodeReviewer, DependencyInstaller, DocGenerator,
    HitlReviewer, ReviewFixer, SpecExtractor, TestGenerator, TestRunner,
)
from antcrew_engine.config import build_llm

__version__ = "0.2.0"

__all__ = [
    # engine
    "Artifact", "ArtifactId", "ArtifactKind", "ArtifactDelta", "EMPTY_DELTA",
    "ArtifactStore", "MemoryStore", "FilesystemStore", "MultiRepoStore",
    "Condition", "ConditionId", "DesiredProjectState", "Constraints", "Goal",
    "ProjectState",
    "CapabilityDescriptor", "CapabilityResult", "Executor",
    "ValidatorResult", "Validator",
    "CapabilityRegistry",
    "EventLog",
    "Operator", "OperatorError",
    "CapabilitySelector", "CheapestFirst", "FirstMatch", "MostProductive", "PrioritySelector",
    "EventBusBridge",
    # capabilities
    "Architect", "TaskPlanner", "CodeGenerator", "CodeRegenerator",
    "BugFixer", "CodeReviewer", "DependencyInstaller", "DocGenerator",
    "HitlReviewer", "ReviewFixer", "SpecExtractor", "TestGenerator", "TestRunner",
    # config
    "build_llm",
]
