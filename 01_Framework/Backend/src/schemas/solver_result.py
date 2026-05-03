from dataclasses import dataclass, field
from typing import Dict, Optional


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