import logging
from collections import defaultdict

from schemas.schemas import Task, Dependency, Core

logger = logging.getLogger(__name__)


def _parse_task_templates(
        data: dict,
) -> tuple[list[Task], list[Dependency]]:
    raw_tasks = data.get("tasks", [])

    if raw_tasks and isinstance(raw_tasks[0], dict) and "tasks" in raw_tasks[0]:
        raise ValueError(
            "Invalid tasks shape. Expected 'tasks' to be a flat list of runnable "
            "objects, not [{'tasks': [...]}]."
        )

    tasks: list[Task] = []
    dependencies: list[Dependency] = []

    seen_task_ids: set[str] = set()

    for raw_task in raw_tasks:
        task = _parse_task(raw_task)

        if task.id in seen_task_ids:
            raise ValueError(f"Duplicate task id: {task.id}")

        seen_task_ids.add(task.id)
        tasks.append(task)

    for raw_task in raw_tasks:
        task_id = raw_task.get("id")
        for predecessor in raw_task.get("dependencies", []):
            if predecessor not in seen_task_ids:
                raise ValueError(
                    f"Task {task_id} depends on unknown task {predecessor}"
                )

            dependencies.append(
                Dependency(
                    predecessor=predecessor,
                    successor=task_id,
                )
            )

    return tasks, dependencies


def _parse_task(raw_task: dict) -> Task:
    period = raw_task.get("period", 0)
    task_type = raw_task.get(
        "taskType",
        "periodic" if period > 0 else "event",
    )

    return Task(
        id=raw_task.get("id"),
        name=raw_task.get("name", raw_task.get("id")),
        required_domain=raw_task.get("requiredDomain", "general_purpose"),
        task_type=task_type,
        duration=raw_task.get("wcet", raw_task.get("duration")),
        period=period,
        memory=raw_task.get("memoryUsageKB", raw_task.get("memory", 0)),
        eligible_cores=list(raw_task.get("eligibleCores", raw_task.get("eligible_cores", []))),
        notes=raw_task.get("notes", ""),
    )


def _map_tasks_to_domain_cores(
        tasks: list[Task],
        cores: list[Core],
        strict_domain_check: bool = False,
) -> list[Task]:
    core_domain_map = defaultdict(list)

    for core in cores:
        core_domain_map[core.execution_domain].append(core)

    core_domains = set(core_domain_map.keys())
    task_domains = {task.required_domain for task in tasks}

    missing_domains = task_domains - core_domains

    if missing_domains:
        if strict_domain_check:
            raise ValueError(
                f"Task domains {missing_domains} are not present in core domains {core_domains}"
            )

        logger.warning(
            "Task domains %s are not present in core domains %s. "
            "Falling back to general_purpose where possible.",
            missing_domains,
            core_domains,
        )

    for task in tasks:
        if task.required_domain not in core_domain_map:
            task.required_domain = "general_purpose"

        compatible_cores = [
            core.id
            for core in core_domain_map.get(task.required_domain, [])
            if task.task_type in core.supported_task_types
        ]

        task.eligible_cores = list(
            dict.fromkeys(
                [
                    *task.eligible_cores,
                    *compatible_cores,
                ]
            )
        )

    return tasks
