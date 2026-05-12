from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ObjectiveBreakdown:
    memory_penalty: float = 0.0
    communication_penalty: float = 0.0
    deadline_penalty: float = 0.0
    compute_penalty: float = 0.0
    constraint_violation_penalty: float = 0.0
    other_penalty: float = 0.0

    def to_dict(self) -> dict:
        return {
            "memory_penalty": self.memory_penalty,
            "communication_penalty": self.communication_penalty,
            "deadline_penalty": self.deadline_penalty,
            "compute_penalty": self.compute_penalty,
            "constraint_violation_penalty": self.constraint_violation_penalty,
            "other_penalty": self.other_penalty,
        }


@dataclass
class SolverResult:
    solver: str
    status: str
    feasible: bool
    objective: Optional[float]
    makespan: Optional[float]

    job_assignment: Dict[str, Optional[str]]

    starts: Dict[str, Optional[float]]
    finishes: Dict[str, Optional[float]]

    core_overflows: Dict[str, Optional[float]]
    cluster_overflows: Dict[str, Optional[float]]

    raw_status: Optional[object]
    runtime_seconds: float
    metadata: Optional[dict] = field(default_factory=dict)


    objective_breakdown: ObjectiveBreakdown = field(default_factory=ObjectiveBreakdown)