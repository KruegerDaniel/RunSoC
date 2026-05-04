import logging
from math import lcm

from schemas.schemas import Task, Job, JobDependency, TaskChain, Dependency

logger = logging.getLogger(__name__)


def _derive_horizon(
        data: dict,
        task_chains: list[TaskChain],
        max_hyperperiod: int = 50_000,
) -> int:
    explicit_horizon = data.get("horizon")

    if explicit_horizon is not None:
        if explicit_horizon <= 0:
            raise ValueError("horizon must be > 0")
        return explicit_horizon

    periods = [chain.period for chain in task_chains]
    if not periods:
        return 0

    h = 1
    for period in periods:
        h = lcm(h, period)
        if h > max_hyperperiod:
            logger.warning(
                "Derived hyperperiod exceeded cap; using horizon=%d",
                max_hyperperiod,
            )
            return max_hyperperiod

    return h


def _expand_jobs(
        tasks: list[Task],
        dependencies: list[Dependency],
        task_chains: list[TaskChain],
        horizon: int,
) -> tuple[list[Job], list[JobDependency]]:
    tasks_by_id = {t.id: t for t in tasks}

    jobs: list[Job] = []
    job_dependencies: list[JobDependency] = []

    chained_task_ids: set[str] = set()

    for chain in task_chains:
        chain_jobs, chain_job_deps = _expand_chain_jobs(
            chain=chain,
            tasks_by_id=tasks_by_id,
            dependencies=dependencies,
            horizon=horizon,
        )

        jobs.extend(chain_jobs)
        job_dependencies.extend(chain_job_deps)
        chained_task_ids.update(chain.task_ids)

    standalone_jobs = _expand_standalone_periodic_jobs(
        tasks=tasks,
        chained_task_ids=chained_task_ids,
        horizon=horizon,
    )
    jobs.extend(standalone_jobs)

    return jobs, job_dependencies


def _expand_chain_jobs(
        chain: TaskChain,
        tasks_by_id: dict[str, Task],
        dependencies: list[Dependency],
        horizon: int,
) -> tuple[list[Job], list[JobDependency]]:
    deadline = chain.deadline if chain.deadline is not None else chain.period

    if chain.instances is not None:
        num_instances = chain.instances
    else:
        num_instances = max(
            0,
            (horizon - chain.release_offset + chain.period - 1) // chain.period,
        )

    chain_task_set = set(chain.task_ids)

    jobs: list[Job] = []
    job_dependencies: list[JobDependency] = []

    for k in range(num_instances):
        release_time = chain.release_offset + k * chain.period
        absolute_deadline = release_time + deadline

        if release_time >= horizon:
            continue

        for task_id in chain.task_ids:
            template = tasks_by_id[task_id]

            is_root = task_id == chain.root_task_id
            job_id = _job_id(task_id=task_id, chain_id=chain.id, k=k)

            jobs.append(
                Job(
                    id=job_id,
                    task_id=task_id,
                    chain_id=chain.id,
                    instance_index=k,
                    name=f"{template.name}__{chain.id}__k{k}",
                    task_type=template.task_type,
                    release_time=release_time,
                    absolute_deadline=absolute_deadline,
                    is_chain_root=is_root,
                    duration=template.duration,
                    memory=template.memory,
                    eligible_cores=list(template.eligible_cores),
                    required_domain=template.required_domain,
                    notes=template.notes,
                )
            )

        for dep in dependencies:
            if dep.predecessor in chain_task_set and dep.successor in chain_task_set:
                job_dependencies.append(
                    JobDependency(
                        predecessor=_job_id(dep.predecessor, chain.id, k),
                        successor=_job_id(dep.successor, chain.id, k),
                    )
                )

    return jobs, job_dependencies


def _expand_standalone_periodic_jobs(
        tasks: list[Task],
        chained_task_ids: set[str],
        horizon: int,
) -> list[Job]:
    jobs: list[Job] = []

    for task in tasks:
        if task.id in chained_task_ids:
            continue

        if task.task_type != "periodic":
            continue

        num_instances = max(0, (horizon + task.period - 1) // task.period)

        for k in range(num_instances):
            release_time = k * task.period
            if release_time >= horizon:
                continue

            jobs.append(
                Job(
                    id=f"{task.id}__k{k}",
                    task_id=task.id,
                    chain_id=None,
                    instance_index=k,
                    name=f"{task.name}__k{k}",
                    task_type=task.task_type,
                    release_time=release_time,
                    absolute_deadline=release_time + task.period,
                    is_chain_root=True,
                    duration=task.duration,
                    memory=task.memory,
                    eligible_cores=list(task.eligible_cores),
                    required_domain=task.required_domain,
                    notes=task.notes,
                )
            )

    return jobs


def _job_id(task_id: str, chain_id: str, k: int) -> str:
    return f"{task_id}__{chain_id}__k{k}"
