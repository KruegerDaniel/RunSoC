from collections import deque, defaultdict

from mappers.validators import _validate_task_chains
from schemas.schemas import TaskChain, Task, Dependency


def _parse_task_chains(
        data: dict,
        tasks: list[Task],
        dependencies: list[Dependency],
) -> list[TaskChain]:
    raw_chains = data.get("taskChains", data.get("task_chains", []))

    tasks_by_id = {t.id: t for t in tasks}

    if raw_chains:
        chains = [
            _parse_task_chain(raw_chain, tasks_by_id)
            for raw_chain in raw_chains
        ]
    else:
        chains = _infer_task_chains_from_periodic_roots(
            tasks=tasks,
            dependencies=dependencies,
        )

    _validate_task_chains(chains, tasks_by_id)

    return chains


def _parse_task_chain(
        raw_chain: dict,
        tasks_by_id: dict[str, Task],
) -> TaskChain:
    root_task_id = raw_chain.get("rootTaskId", raw_chain.get("root_task_id"))
    task_ids = raw_chain.get("taskIds", raw_chain.get("task_ids", []))

    root = tasks_by_id.get(root_task_id)
    if root is None:
        raise ValueError(f"TaskChain references unknown root task {root_task_id}")

    return TaskChain(
        id=raw_chain.get("id"),
        root_task_id=root_task_id,
        task_ids=task_ids,
        period=raw_chain.get("period", root.period),
        release_offset=raw_chain.get("releaseOffset", raw_chain.get("release_offset", 0)),
        deadline=raw_chain.get("deadline"),
        instances=raw_chain.get("instances"),
    )


def _infer_task_chains_from_periodic_roots(
        tasks: list[Task],
        dependencies: list[Dependency],
) -> list[TaskChain]:
    """
    If the request does not include taskChains, infer one chain from each
    periodic root and all reachable successors.
    """
    adj = defaultdict(list)

    for dep in dependencies:
        adj[dep.predecessor].append(dep.successor)

    chains: list[TaskChain] = []

    for root in tasks:
        if root.task_type != "periodic":
            continue

        reachable = _reachable_from(root.id, adj)

        chains.append(
            TaskChain(
                id=f"chain_{root.id}",
                root_task_id=root.id,
                task_ids=reachable,
                period=root.period,
                release_offset=0,
                deadline=root.period,
                instances=None,
            )
        )

    return chains


def _reachable_from(
        root_id: str,
        adj: dict[str, list[str]],
) -> list[str]:
    visited: set[str] = set()
    ordered: list[str] = []

    queue = deque([root_id])
    visited.add(root_id)

    while queue:
        current = queue.popleft()
        ordered.append(current)

        for successor in adj[current]:
            if successor not in visited:
                visited.add(successor)
                queue.append(successor)

    return ordered

