"""Lab Knowledge Graph — 14 entity types for the knowledge graph.

Spec: docs/specs/cross-graph-nodes.md
Design doc: section 4 (Lab Knowledge Graph)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.schemas import (
    DeviceInterfaceType,
    DeviceStatus,
    FileReference,
    HypothesisStatus,
    MemberRole,
    QualityLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """Base for all knowledge graph entities."""

    node_id: str = Field(default_factory=_uuid)
    node_type: str = ""  # Auto-set by subclasses
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    created_by: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, _context: Any) -> None:
        if not self.node_type:
            # Derive from class name: SessionNode → "session"
            name = type(self).__name__
            if name.endswith("Node"):
                name = name[:-4]
            self.node_type = name.lower()


# ---------------------------------------------------------------------------
# 14 Entity Types
# ---------------------------------------------------------------------------


class PersonNode(GraphNode):
    """People — who, role, expertise, affiliation."""

    name: str
    role: MemberRole | None = None
    affiliation: str | None = None
    expertise: list[str] = Field(default_factory=list)
    email: str | None = None


class ProtocolNode(GraphNode):
    """Protocols — how to do things, version history, pitfalls."""

    name: str
    version: str = "1.0"
    steps: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    parent_id: str | None = None  # Previous version


class ProjectNode(GraphNode):
    """Top-level project grouping experiments."""

    name: str
    description: str = ""
    pi_id: str | None = None  # PersonNode reference


class ExperimentNode(GraphNode):
    """Experiments — cohort/study arm within a project."""

    name: str
    project_id: str | None = None  # ProjectNode reference
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class SampleNode(GraphNode):
    """Generic sample — any physical or biological specimen.

    Domain-agnostic replacement for SubjectNode.  Domain plugins subclass this
    to add domain-specific fields (e.g. AnimalSampleNode).
    """

    label: str
    sample_type: str = ""  # e.g. "animal", "cell_line", "tissue", "reagent"
    properties: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None  # Parent SampleNode reference


class SubjectNode(GraphNode):
    """Subjects — animals: genotype, age, sex, surgical history.

    .. deprecated::
        Use :class:`SampleNode` (or domain-specific subclass) instead.
        Kept for backwards compatibility.
    """

    subject_label: str
    species: str = ""
    genotype: str | None = None
    sex: str | None = None
    date_of_birth: datetime | None = None
    surgical_history: list[str] = Field(default_factory=list)
    experiment_id: str | None = None  # ExperimentNode reference


class SessionNode(GraphNode):
    """Sessions — one recording day: date, rig, operator."""

    session_date: datetime
    rig_id: str | None = None  # DeviceNode reference
    operator_id: str | None = None  # PersonNode reference
    experiment_id: str | None = None  # ExperimentNode reference
    subject_id: str | None = None  # SubjectNode reference
    duration_seconds: float | None = None
    notes: str = ""


class TrialNode(GraphNode):
    """Trials — behavioral events within a session."""

    session_id: str  # SessionNode reference
    trial_number: int
    start_time: float  # Seconds from session start
    end_time: float | None = None
    outcome: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class RecordingNode(GraphNode):
    """Recordings — data files: video, ephys, imaging."""

    session_id: str  # SessionNode reference
    file: FileReference
    modality: str  # "video", "ephys", "calcium_imaging", etc.
    device_id: str | None = None  # DeviceNode reference
    duration_seconds: float | None = None
    quality: QualityLevel = QualityLevel.UNKNOWN


class AnalysisNode(GraphNode):
    """Analyses — computed outputs: pose tracks, spike sorts, calcium traces."""

    recording_id: str | None = None  # RecordingNode reference
    session_id: str | None = None  # SessionNode reference
    pipeline: str  # e.g. "sam_behavior", "kilosort3", "suite2p"
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_files: list[FileReference] = Field(default_factory=list)
    quality: QualityLevel = QualityLevel.UNKNOWN


class FindingNode(GraphNode):
    """Findings — conclusions, statistical results."""

    summary: str
    analysis_ids: list[str] = Field(default_factory=list)  # AnalysisNode refs
    hypothesis_id: str | None = None
    statistical_results: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None  # 0-1
    status: HypothesisStatus = HypothesisStatus.PROPOSED


class DecisionNode(GraphNode):
    """Decisions — why something was changed."""

    summary: str
    rationale: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    decided_by: str | None = None  # PersonNode reference


class FailureNode(GraphNode):
    """Failures — what didn't work and why."""

    summary: str
    category: str = ""  # "hardware", "protocol", "analysis", "software"
    root_cause: str = ""
    resolution: str = ""
    session_id: str | None = None


class DeviceNode(GraphNode):
    """Devices — equipment: status, calibration history, quirks."""

    name: str
    device_type: str  # "two_photon", "camera", "qpcr", etc.
    model: str = ""
    manufacturer: str = ""
    location: str = ""
    interface_type: DeviceInterfaceType = DeviceInterfaceType.FILE_BASED
    status: DeviceStatus = DeviceStatus.OFFLINE
    capabilities: list[str] = Field(default_factory=list)
    watch_path: Path | None = None  # For file-based devices


class LiteratureNode(GraphNode):
    """Literature — papers read, relevance to which experiment."""

    title: str
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    year: int | None = None
    relevance: str = ""
    experiment_ids: list[str] = Field(default_factory=list)


class AssetNode(GraphNode):
    """Assets — code, models, figures, datasets: where they live."""

    name: str
    asset_type: str  # "code", "model", "figure", "dataset"
    file: FileReference | None = None
    url: str | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

NODE_TYPES: dict[str, type[GraphNode]] = {
    "person": PersonNode,
    "protocol": ProtocolNode,
    "project": ProjectNode,
    "experiment": ExperimentNode,
    "sample": SampleNode,
    "subject": SubjectNode,  # deprecated alias
    "session": SessionNode,
    "trial": TrialNode,
    "recording": RecordingNode,
    "analysis": AnalysisNode,
    "finding": FindingNode,
    "decision": DecisionNode,
    "failure": FailureNode,
    "device": DeviceNode,
    "literature": LiteratureNode,
    "asset": AssetNode,
}


def get_node_type(type_name: str) -> type[GraphNode]:
    """Look up a node class by its type name string."""
    try:
        return NODE_TYPES[type_name]
    except KeyError:
        available = ", ".join(sorted(NODE_TYPES))
        raise KeyError(f"Unknown node type {type_name!r}. Available: {available}") from None
