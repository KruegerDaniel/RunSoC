from typing import List, Literal

from pydantic import BaseModel, Field


class Task(BaseModel):
    id: str
    name: str
    task_type: Literal["event", "periodic"]
    period: int = 0  # Only relevant info for periodic tasks. Not used in scheduler
    min_start: int = 0 # Earliest schedulable time for task
    duration: float
    memory: int
    eligible_cores: List[str]
    required_domain: str = "general_purpose"
    notes: str = ""

class Dependency(BaseModel):
    predecessor: str
    successor: str

# Only for explicitly defined communication paths
class CommunicationPath(BaseModel):
    source: str # core
    target: str # core
    penalty: int = 0
    notes: str = ""

class Core(BaseModel):
    id: str
    name: str
    cluster_id: str
    wcet_scale: float = 1.0
    execution_domain: str = "general_purpose"
    supported_task_types: List[Literal["event", "periodic"]]
    memory_budget: int
    notes: str = ""

class Cluster(BaseModel):
    id: str
    name: str
    type: str = "application"
    memory_budget: int
    memory_type: str = "cache"
    memory_level: str = "L3"
    notes: str = ""

class MemoryNode(BaseModel):
    id: str
    name: str
    type: str = "dram"
    scope: str = "system"
    accessible_by: List[str]
    capacity: int
    notes: str = ""

class ProblemInstance(BaseModel):
    tasks: List[Task] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    communication_paths: List[CommunicationPath] = Field(default_factory=list)
    clusters: List[Cluster] = Field(default_factory=list)
    # memory_nodes currently unused.
    memory_nodes: List[MemoryNode] = Field(default_factory=list)
    cores: List[Core] = Field(default_factory=list)

    memory_penalty_scale: dict = Field(
        default_factory=lambda: {
            "core_overflow_scale": 1,
            "cluster_overflow_scale": 1,
        }
    )

    comms_penalty_weight: dict = Field(
        default_factory=lambda: {
            "intra_core_weight": 0,
            "inter_core_weight": 8,
            "inter_cluster_weight": 15
        }
    )

