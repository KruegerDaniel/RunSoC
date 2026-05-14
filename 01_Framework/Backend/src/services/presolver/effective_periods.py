from collections import deque
from schemas.schemas import ProblemInstance


def calculate_effective_periods(problem: ProblemInstance) -> dict[str, float]:
    """
    Propagates the period from root tasks down to dependent tasks.
    Returns a dictionary of {task_id: effective_period_in_us}
    """
    effective_periods = {}
    successors = {t.id: [] for t in problem.tasks}

    for dep in problem.dependencies:
        successors[dep.predecessor].append(dep.successor)

    # Find roots (tasks with period > 0)
    queue = deque([t for t in problem.tasks if t.period > 0])

    for root in queue:
        effective_periods[root.id] = float(root.period)

    # BFS to propagate period to children
    visited = set(effective_periods.keys())

    while queue:
        current = queue.popleft()
        current_period = effective_periods[current.id]

        for succ_id in successors.get(current.id, []):
            if succ_id not in visited:
                effective_periods[succ_id] = current_period
                visited.add(succ_id)
                succ_task = next(t for t in problem.tasks if t.id == succ_id)
                queue.append(succ_task)

    return effective_periods