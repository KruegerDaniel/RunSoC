from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_period(self):
        if self.task_type == "periodic" and self.period <= 0:
            raise ValueError(f"Periodic task {self.id} must have a positive period")
        if self.task_type == "event" and self.period != 0:
            raise ValueError(f"Event task {self.id} must have a period of 0")
        return self

class Dependency(BaseModel):
    predecessor: str
    successor: str

class TaskChain(BaseModel):
    id: str
    root_task_id: str
    task_ids: List[str]

    period: int
    release_offset: int = 0
    deadline: Optional[int] = None
    instances: Optional[int] = None

    @model_validator(mode="after")
    def validate_chain(self):
        if self.period <= 0:
            raise ValueError(f"Task chain {self.id} must have a period > 0")
        if self.deadline is not None and self.deadline <= 0:
            raise ValueError(f"Task chain {self.id} must have a deadline > 0")
        return self

class Job(BaseModel):
    id: str
    task_id: str
    chain_id: str | None = None
    instance_index: int | None = None

    name: str
    task_type: str

    release_time: int
    absolute_deadline: int | None = None

    is_chain_root: bool = False

    duration: float
    memory: int
    eligible_cores: List[str] = Field(default_factory=list)
    required_domain: str = "general_purpose"
    notes: str = ""

class JobDependency(BaseModel):
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

class EvaluationMetadata(BaseModel):
    taskset_id: str | None = None
    platform_name: str | None = None
    platform_key: str | None = None
    source_file: str | None = None
    seed: int | None = None

class ProblemInstance(BaseModel):
    # Runnable templates
    tasks: List[Task] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    task_chains: List[TaskChain] = Field(default_factory=list)

    # Concrete schedulable instances
    jobs: List[Job] = Field(default_factory=list)
    job_dependencies: List[JobDependency] = Field(default_factory=list)

    communication_paths: List[CommunicationPath] = Field(default_factory=list)

    clusters: List[Cluster] = Field(default_factory=list)
    memory_nodes: List[MemoryNode] = Field(default_factory=list)
    cores: List[Core] = Field(default_factory=list)

    horizon: int

    max_chain_jitter: int | None = 0

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

    evaluation: EvaluationMetadata = Field(default_factory=EvaluationMetadata)
