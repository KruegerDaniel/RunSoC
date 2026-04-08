from pydantic import BaseModel, Field
from typing import List, Optional

class Task(BaseModel):
    id: str
    duration: int
    memory: int
    eligible_cores: List[str]

class Dependency(BaseModel):
    predecessor: str
    successor: str

class Communication(BaseModel):
    source: str
    target: str
    latency: int

class Core(BaseModel):
    id: str
    memory_budget: int

class ProblemInstance(BaseModel):
    tasks: List[Task]
    dependencies: List[Dependency] = []
    communications: List[Communication] = []
    cores: List[Core]
    memory_penalty_weight: int = 1