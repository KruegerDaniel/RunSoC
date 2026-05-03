from schemas.schemas import Job, TaskChain, Task


def _validate_cluster_core_count(raw_cluster: dict) -> None:
    declared_num_cores = raw_cluster.get("numCores")
    if declared_num_cores is None:
        return

    expected_per_cluster = sum(
        raw_core.get("count", 1)
        for raw_core in raw_cluster.get("cores", [])
    )

    if declared_num_cores != expected_per_cluster:
        raise ValueError(
            f"Cluster {raw_cluster.get('name')}[{raw_cluster.get('id')}]: "
            f"numCores={declared_num_cores} does not match expanded "
            f"per-cluster core count={expected_per_cluster}"
        )


def _validate_jobs_have_eligible_cores(jobs: list[Job]) -> None:
    bad_jobs = [job.id for job in jobs if not job.eligible_cores]

    if bad_jobs:
        sample = bad_jobs[:10]
        raise ValueError(
            f"{len(bad_jobs)} jobs have no eligible cores. Sample: {sample}"
        )


def _validate_task_chains(
        chains: list[TaskChain],
        tasks_by_id: dict[str, Task],
) -> None:
    for chain in chains:
        if chain.root_task_id not in tasks_by_id:
            raise ValueError(
                f"TaskChain {chain.id} references unknown root {chain.root_task_id}"
            )

        root = tasks_by_id[chain.root_task_id]

        if root.task_type != "periodic":
            raise ValueError(
                f"TaskChain {chain.id} root {root.id} must be periodic"
            )

        if root.period != chain.period:
            raise ValueError(
                f"TaskChain {chain.id} period={chain.period} does not match "
                f"root task {root.id} period={root.period}"
            )

        if chain.root_task_id not in chain.task_ids:
            raise ValueError(
                f"TaskChain {chain.id} root_task_id must be included in task_ids"
            )

        for task_id in chain.task_ids:
            if task_id not in tasks_by_id:
                raise ValueError(
                    f"TaskChain {chain.id} references unknown task {task_id}"
                )
