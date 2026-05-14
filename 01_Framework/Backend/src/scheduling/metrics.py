from typing import Optional

from schemas.schemas import ProblemInstance
from utils.numerical_util import clean_num


def safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_memory_penalty(
    problem: ProblemInstance,
    core_overflows: dict[str, Optional[float]],
    cluster_overflows: dict[str, Optional[float]],
) -> float:
    core_scale = safe_float(
        problem.memory_penalty_scale.get("core_overflow_scale", 1),
        default=1.0,
    )
    cluster_scale = safe_float(
        problem.memory_penalty_scale.get("cluster_overflow_scale", 1),
        default=1.0,
    )

    core_overflow_sum = sum(safe_float(v) for v in core_overflows.values())
    cluster_overflow_sum = sum(safe_float(v) for v in cluster_overflows.values())

    return clean_num(
        core_scale * core_overflow_sum
        + cluster_scale * cluster_overflow_sum
    )


def compute_communication_penalty(
    problem: ProblemInstance,
    job_assignment: dict[str, Optional[str]],
) -> float:
    cores_by_id = {core.id: core for core in problem.cores}

    intra_core_weight = safe_float(
        problem.comms_penalty_weight.get("intra_core_weight", 0),
        default=0.0,
    )
    inter_core_weight = safe_float(
        problem.comms_penalty_weight.get("inter_core_weight", 8),
        default=8.0,
    )
    inter_cluster_weight = safe_float(
        problem.comms_penalty_weight.get("inter_cluster_weight", 15),
        default=15.0,
    )

    total = 0.0

    for dep in problem.job_dependencies:
        pred_core_id = job_assignment.get(dep.predecessor)
        succ_core_id = job_assignment.get(dep.successor)

        if pred_core_id is None or succ_core_id is None:
            continue

        pred_core = cores_by_id.get(pred_core_id)
        succ_core = cores_by_id.get(succ_core_id)

        if pred_core is None or succ_core is None:
            continue

        if pred_core_id == succ_core_id:
            total += intra_core_weight
        elif pred_core.cluster_id == succ_core.cluster_id:
            total += inter_core_weight
        else:
            total += inter_cluster_weight

    return clean_num(total)


def compute_deadline_violation(
    problem: ProblemInstance,
    finishes: dict[str, Optional[float]],
) -> float:
    total = 0.0

    for job in problem.jobs:
        if job.absolute_deadline is None:
            continue

        finish = finishes.get(job.id)
        if finish is None:
            continue

        total += max(0.0, float(finish) - float(job.absolute_deadline))

    return clean_num(total)


def compute_compute_pressure(
    problem: ProblemInstance,
    starts: dict[str, Optional[float]],
    finishes: dict[str, Optional[float]],
    makespan: Optional[float],
) -> Optional[float]:
    if makespan is None or makespan <= 0:
        return None

    total_duration = 0.0

    for job in problem.jobs:
        start = starts.get(job.id)
        finish = finishes.get(job.id)

        if start is None or finish is None:
            continue

        total_duration += max(0.0, float(finish) - float(start))

    return clean_num(total_duration / max(float(makespan), 1.0))


def classify_bottleneck(
    memory_overflow_kb: float,
    communication_penalty: float,
    deadline_violation: float,
    compute_pressure: Optional[float],
) -> str:
    if deadline_violation > 0:
        return "deadline"

    if memory_overflow_kb > 0:
        return "memory"

    if communication_penalty > 0:
        return "communication"

    if compute_pressure is not None and compute_pressure >= 0.85:
        return "compute"

    return "none"