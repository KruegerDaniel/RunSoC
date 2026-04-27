from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class SolverResult:
    solver: str
    status: str
    feasible: bool
    objective: Optional[float]
    makespan: Optional[float]

    assignment: Dict[str, Optional[str]]

    starts: Dict[str, Optional[float]]
    finishes: Dict[str, Optional[float]]

    core_overflows: Dict[str, Optional[int]]
    cluster_overflows: Dict[str, Optional[int]]

    raw_status: Optional[object]
    runtime_seconds: Optional[float]
    metadata: Optional[dict]
