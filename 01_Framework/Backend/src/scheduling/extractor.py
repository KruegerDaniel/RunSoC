from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult
from scheduling.metrics import (
    classify_bottleneck,
    compute_communication_penalty,
    compute_compute_pressure,
    compute_deadline_violation,
    compute_memory_penalty,
)
from utils.numerical_util import clean_num


def _as_dict_objective_breakdown(result: SolverResult) -> dict:
    breakdown = getattr(result, "objective_breakdown", None)

    if breakdown is None:
        return {}

    if hasattr(breakdown, "to_dict"):
        return breakdown.to_dict()

    if isinstance(breakdown, dict):
        return breakdown

    return {}


def _get_problem_evaluation(problem: ProblemInstance) -> dict:
    evaluation = getattr(problem, "evaluation", None)

    if evaluation is None:
        return {
            "taskset_id": None,
            "platform_name": None,
            "platform_key": None,
            "source_file": None,
            "seed": None,
        }

    if hasattr(evaluation, "model_dump"):
        return evaluation.model_dump()

    if isinstance(evaluation, dict):
        return evaluation

    return {
        "taskset_id": getattr(evaluation, "taskset_id", None),
        "platform_name": getattr(evaluation, "platform_name", None),
        "platform_key": getattr(evaluation, "platform_key", None),
        "source_file": getattr(evaluation, "source_file", None),
        "seed": getattr(evaluation, "seed", None),
    }


def _build_problem_context(problem: ProblemInstance) -> dict:
    return {
        "evaluation": _get_problem_evaluation(problem),
        "config": {
            "memory_penalty_scale": problem.memory_penalty_scale,
            "comms_penalty_weight": problem.comms_penalty_weight,
            "max_chain_jitter": problem.max_chain_jitter,
        },
        "platform": {
            "core_count": len(problem.cores),
            "cluster_count": len(problem.clusters),
            "memory_node_count": len(problem.memory_nodes),
        },
    }


def _build_summary(problem: ProblemInstance, scheduled_job_count: int) -> dict:
    return {
        "task_template_count": len(problem.tasks),
        "job_count": len(problem.jobs),
        "scheduled_job_count": scheduled_job_count,
        "task_chain_count": len(problem.task_chains),
        "dependency_template_count": len(problem.dependencies),
        "job_dependency_count": len(problem.job_dependencies),
        "core_count": len(problem.cores),
        "cluster_count": len(problem.clusters),
        "horizon": problem.horizon,
    }


def _sum_overflows(resource_entries: list[dict]) -> float:
    return clean_num(
        sum(
            float(entry.get("overflow") or 0.0)
            for entry in resource_entries
        )
    )


def _build_empty_resource_usage() -> dict:
    return {
        "core_memory": [],
        "cluster_memory": [],
    }


def build_solution_response(
    problem: ProblemInstance,
    result: SolverResult,
) -> dict:
    tasks_by_id = {t.id: t for t in problem.tasks}
    jobs_by_id = {j.id: j for j in problem.jobs}
    cores_by_id = {c.id: c for c in problem.cores}

    pred_map: dict[str, list[str]] = {}
    for dep in problem.job_dependencies:
        pred_map.setdefault(dep.successor, []).append(dep.predecessor)

    objective_breakdown = _as_dict_objective_breakdown(result)

    if not result.feasible:
        return {
            "solver": result.solver,
            "status": result.status,
            "feasible": False,
            "objective": None,
            "makespan": None,
            **_build_problem_context(problem),
            "summary": _build_summary(problem, scheduled_job_count=0),
            "objective_breakdown": {
                "memory_penalty": clean_num(objective_breakdown.get("memory_penalty", 0.0)),
                "communication_penalty": clean_num(objective_breakdown.get("communication_penalty", 0.0)),
                "deadline_penalty": clean_num(objective_breakdown.get("deadline_penalty", 0.0)),
                "compute_penalty": clean_num(objective_breakdown.get("compute_penalty", 0.0)),
                "constraint_violation_penalty": clean_num(
                    objective_breakdown.get("constraint_violation_penalty", 0.0)
                ),
                "other_penalty": clean_num(objective_breakdown.get("other_penalty", 0.0)),
            },
            "derived_metrics": {
                "compute_pressure": None,
                "deadline_violation": None,
                "total_memory_overflow_kb": None,
                "core_memory_overflow_kb": None,
                "cluster_memory_overflow_kb": None,
                "bottleneck": "unknown",
            },
            "resource_usage": _build_empty_resource_usage(),
            "schedule": [],
            "runtime_seconds": round(result.runtime_seconds, 4),
            "metadata": result.metadata or {},
        }

    schedule = []

    for job in problem.jobs:
        assigned_core = result.job_assignment.get(job.id)
        assigned_cluster = None
        duration_on_core = None

        if assigned_core is not None:
            core = cores_by_id[assigned_core]
            assigned_cluster = core.cluster_id
            duration_on_core = clean_num(job.duration * core.wcet_scale)

        predecessors = pred_map.get(job.id, [])

        pred_finishes = [
            result.finishes.get(pred)
            for pred in predecessors
            if result.finishes.get(pred) is not None
        ]

        eligible_time = max(
            [job.release_time, *pred_finishes],
            default=job.release_time,
        )

        source_task = tasks_by_id.get(job.task_id)

        schedule.append(
            {
                "job_id": job.id,
                "task_id": job.task_id,
                "chain_id": job.chain_id,
                "instance_index": job.instance_index,
                "job_name": job.name,
                "task_name": source_task.name if source_task is not None else job.name,
                "task_type": job.task_type,
                "is_chain_root": job.is_chain_root,
                "assigned_core": assigned_core,
                "assigned_cluster": assigned_cluster,
                "release_time": job.release_time,
                "absolute_deadline": job.absolute_deadline,
                "eligible_time": clean_num(eligible_time),
                "start_time": clean_num(result.starts.get(job.id)),
                "finish_time": clean_num(result.finishes.get(job.id)),
                "base_duration": clean_num(job.duration),
                "scheduled_duration": duration_on_core,
                "memory": job.memory,
                "required_domain": job.required_domain,
                "predecessors": predecessors,
                "notes": job.notes,
            }
        )

    schedule.sort(
        key=lambda item: (
            item["start_time"] if item["start_time"] is not None else float("inf"),
            item["assigned_core"] or "",
            item["job_id"],
        )
    )

    core_memory = []

    for core in problem.cores:
        assigned_jobs = sorted(
            job_id
            for job_id, core_id in result.job_assignment.items()
            if core_id == core.id
        )

        used = sum(jobs_by_id[job_id].memory for job_id in assigned_jobs)
        overflow = result.core_overflows.get(core.id, 0)

        core_memory.append(
            {
                "core_id": core.id,
                "core_name": core.name,
                "cluster_id": core.cluster_id,
                "budget": core.memory_budget,
                "used": clean_num(used),
                "overflow": clean_num(overflow),
                "assigned_jobs": assigned_jobs,
            }
        )

    cluster_memory = []

    for cluster in problem.clusters:
        cluster_core_ids = {
            core.id
            for core in problem.cores
            if core.cluster_id == cluster.id
        }

        assigned_jobs = sorted(
            job_id
            for job_id, core_id in result.job_assignment.items()
            if core_id in cluster_core_ids
        )

        used = sum(jobs_by_id[job_id].memory for job_id in assigned_jobs)
        overflow = result.cluster_overflows.get(cluster.id, 0)

        cluster_memory.append(
            {
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "budget": cluster.memory_budget,
                "used": clean_num(used),
                "overflow": clean_num(overflow),
                "assigned_jobs": assigned_jobs,
            }
        )

    core_memory_overflow_kb = _sum_overflows(core_memory)
    cluster_memory_overflow_kb = _sum_overflows(cluster_memory)
    total_memory_overflow_kb = clean_num(
        core_memory_overflow_kb + cluster_memory_overflow_kb
    )

    memory_penalty = objective_breakdown.get("memory_penalty")
    if memory_penalty is None:
        memory_penalty = compute_memory_penalty(
            problem=problem,
            core_overflows=result.core_overflows,
            cluster_overflows=result.cluster_overflows,
        )

    communication_penalty = objective_breakdown.get("communication_penalty")
    if communication_penalty is None:
        communication_penalty = compute_communication_penalty(
            problem=problem,
            job_assignment=result.job_assignment,
        )

    deadline_penalty = objective_breakdown.get("deadline_penalty")
    if deadline_penalty is None:
        deadline_penalty = compute_deadline_violation(
            problem=problem,
            finishes=result.finishes,
        )

    compute_pressure = compute_compute_pressure(
        problem=problem,
        starts=result.starts,
        finishes=result.finishes,
        makespan=result.makespan,
    )

    bottleneck = classify_bottleneck(
        memory_overflow_kb=total_memory_overflow_kb,
        communication_penalty=communication_penalty,
        deadline_violation=deadline_penalty,
        compute_pressure=compute_pressure,
    )

    objective_breakdown = {
        "memory_penalty": clean_num(memory_penalty),
        "communication_penalty": clean_num(communication_penalty),
        "deadline_penalty": clean_num(deadline_penalty),
        "compute_penalty": clean_num(objective_breakdown.get("compute_penalty", 0.0)),
        "constraint_violation_penalty": clean_num(
            objective_breakdown.get("constraint_violation_penalty", 0.0)
        ),
        "other_penalty": clean_num(objective_breakdown.get("other_penalty", 0.0)),
    }

    return {
        "solver": result.solver,
        "status": result.status,
        "feasible": True,
        "objective": clean_num(result.objective),
        "makespan": clean_num(result.makespan),
        **_build_problem_context(problem),
        "summary": _build_summary(problem, scheduled_job_count=len(schedule)),
        "objective_breakdown": objective_breakdown,
        "derived_metrics": {
            "compute_pressure": clean_num(compute_pressure),
            "deadline_violation": clean_num(deadline_penalty),
            "total_memory_overflow_kb": total_memory_overflow_kb,
            "core_memory_overflow_kb": core_memory_overflow_kb,
            "cluster_memory_overflow_kb": cluster_memory_overflow_kb,
            "bottleneck": bottleneck,
        },
        "resource_usage": {
            "core_memory": core_memory,
            "cluster_memory": cluster_memory,
        },
        "schedule": schedule,
        "runtime_seconds": round(result.runtime_seconds, 4),
        "metadata": result.metadata or {},
    }