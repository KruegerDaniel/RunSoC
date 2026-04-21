from typing import List, Literal

from pydantic import BaseModel


class Task(BaseModel):
    id: str
    name: str
    task_type: Literal["event", "periodic"]
    period: int = 0  # Only relevant for periodic tasks
    duration: int
    memory: int
    eligible_cores: List[str]
    required_domain: Literal["general_purpose", "safety", "none"] = "none"
    notes: str = ""

class Dependency(BaseModel):
    predecessor: str
    successor: str

class Communication(BaseModel):
    source: str
    target: str
    scope: Literal["cross_core", "cross_cluster"] = "cross_cluster"
    penalty: int = 0


class Core(BaseModel):
    id: str
    name: str
    cluster_id: str
    wcet_scale: int
    execution_domain: Literal["general_purpose", "safety"]
    supported_task_types: List[Literal["event", "periodic"]]
    memory_budget: int
    notes: str = ""

class Cluster(BaseModel):
    id: str
    name: str
    execution_domain: Literal["general_purpose", "safety"]
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


class ProblemInstance(BaseModel):
    tasks: List[Task] = []
    dependencies: List[Dependency] = []
    communications: List[Communication] = []
    clusters: List[Cluster] = []
    memory_nodes: List[MemoryNode] = []
    cores: List[Core] = []

    memory_penalty_scale: dict = {
        "inter_core_scale": 1,
        "inter_cluster_scale": 1,
    }
    comms_penalty_weight: dict = {
        "intra_core_weight": 0,
        "inter_core_weight": 8,
        "inter_cluster_weight": 15,
        "inter_app_weight": 100
    }

