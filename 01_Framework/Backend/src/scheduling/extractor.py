from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult
from utils.numerical_util import clean_num


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

    if not result.feasible:
        return {
            "solver": result.solver,
            "status": result.status,
            "feasible": False,
            "objective": None,
            "makespan": None,
            "summary": {
                "task_template_count": len(problem.tasks),
                "job_count": len(problem.jobs),
                "scheduled_job_count": 0,
                "task_chain_count": len(problem.task_chains),
                "dependency_template_count": len(problem.dependencies),
                "job_dependency_count": len(problem.job_dependencies),
                "core_count": len(problem.cores),
                "cluster_count": len(problem.clusters),
            },
            "resource_usage": {
                "core_memory": [],
                "cluster_memory": [],
            },
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
                "base_duration": job.duration,
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

    return {
        "solver": result.solver,
        "status": result.status,
        "feasible": True,
        "objective": clean_num(result.objective),
        "makespan": clean_num(result.makespan),
        "summary": {
            "task_template_count": len(problem.tasks),
            "job_count": len(problem.jobs),
            "scheduled_job_count": len(schedule),
            "task_chain_count": len(problem.task_chains),
            "dependency_template_count": len(problem.dependencies),
            "job_dependency_count": len(problem.job_dependencies),
            "core_count": len(problem.cores),
            "cluster_count": len(problem.clusters),
        },
        "resource_usage": {
            "core_memory": core_memory,
            "cluster_memory": cluster_memory,
        },
        "schedule": schedule,
        "runtime_seconds": round(result.runtime_seconds, 4),
        "metadata": result.metadata or {},
    }