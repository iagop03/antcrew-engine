"""antcrew.engine — capability-driven project execution engine.

The engine builds software by iterating over a goal until the project
reaches a desired state.  It never assumes a fixed pipeline of agents
or roles — it discovers what to do next from the artifact state.

Public API
----------
Types:
    Artifact, ArtifactId, ArtifactKind, ArtifactDelta, EMPTY_DELTA
    ArtifactStore, MemoryStore
    Condition, ConditionId, DesiredProjectState, Constraints, Goal
    ProjectState
    CapabilityDescriptor, CapabilityResult, Executor
    ValidatorResult, Validator
    CapabilityRegistry
    Event, EventLog  (+ all Event subclasses)
    EngineLoop, EngineLoopError
    HitlReviewRequest, HitlDecision  (HITL contract)

Entry point:
    EngineLoop.run(store, goal) → ProjectState
"""
from .artifact import (
    Artifact,
    ArtifactDelta,
    ArtifactId,
    ArtifactKind,
    EMPTY_DELTA,
)
from .capability import CapabilityDescriptor, CapabilityResult, Executor
from .events import (
    CapabilityCompleted,
    CapabilityDispatched,
    ConditionInvalidated,
    ConditionSatisfied,
    EngineError,
    EngineFinished,
    EngineStarted,
    Event,
    EventLog,
    EngineDecision,
    StateObserved,
)
from .goal import Condition, ConditionId, Constraints, DesiredProjectState, Goal
from .operator import EngineLoop, EngineLoopError
from .registry import CapabilityRegistry
from .selector import (
    CapabilitySelector, CheapestFirst, FirstMatch, MostProductive, PrioritySelector,
)
from .state import ProjectState
from .store import ArtifactStore, MemoryStore, FilesystemStore, MultiRepoStore
from .validator import Validator, ValidatorResult
from .bus_bridge import EventBusBridge
from . import sandbox
from .hitl import (
    HitlReviewRequest, HitlDecision,
    HitlRequestedPayload, HitlResolvedPayload,
)

__all__ = [
    # artifact
    "Artifact", "ArtifactId", "ArtifactKind", "ArtifactDelta", "EMPTY_DELTA",
    # store
    "ArtifactStore", "MemoryStore", "FilesystemStore", "MultiRepoStore",
    # goal
    "Condition", "ConditionId", "DesiredProjectState", "Constraints", "Goal",
    # state
    "ProjectState",
    # capability
    "CapabilityDescriptor", "CapabilityResult", "Executor",
    # validator
    "Validator", "ValidatorResult",
    # registry
    "CapabilityRegistry",
    # events
    "Event", "EventLog",
    "EngineStarted", "EngineFinished", "EngineError",
    "StateObserved", "CapabilityDispatched", "CapabilityCompleted",
    "ConditionSatisfied", "ConditionInvalidated", "EngineDecision",
    # operator
    "EngineLoop", "EngineLoopError",
    # selector
    "CapabilitySelector", "CheapestFirst", "FirstMatch", "MostProductive", "PrioritySelector",
    # platform bridge
    "EventBusBridge",
    # sandbox
    "sandbox",
    # hitl contract
    "HitlReviewRequest", "HitlDecision",
    "HitlRequestedPayload", "HitlResolvedPayload",
]
