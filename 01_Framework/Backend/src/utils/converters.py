from typing import Dict, Any


def normalize_runnables(runnables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Normalize frontend runnables:
    - force numeric fields to int
    - normalize `dependencies` -> `deps` (list[str]) containing *IDs*
    """
    for key, props in runnables.items():
        # Normalize numeric fields
        for num_key in ['period', 'execution_time', 'criticality', 'affinity', 'priority']:
            if num_key in props and props[num_key] not in (None, ''):
                props[num_key] = int(props[num_key])

        if 'dependencies' in props and isinstance(props['dependencies'], list):
            props['deps'] = [str(dep) for dep in props['dependencies']]

        # If deps already exists, make sure they are strings
        if 'deps' in props and isinstance(props['deps'], list):
            props['deps'] = [str(dep) for dep in props['deps']]

        # id to string
        if 'id' in props and props['id'] not in (None, ''):
            props['id'] = str(props['id'])

    return runnables


def to_main_tasks(runnables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Convert frontend-style runnables into main_scheduler tasks.

    Dependencies are expressed as *IDs* (e.g. "1"), and this function resolves
    them to the correct runnable using the `id` field, *not* the `name`.

    The keys of the returned `tasks` dict are whatever keys you used in the
    `runnables` dict (e.g. "Task1", "R1", etc.), but deps are mapped so that
    each ID points to the correct key, even if names are duplicated.
    """
    tasks: Dict[str, Dict[str, Any]] = {}

    #runnable-id -> runnable-key
    id_to_key: Dict[str, str] = {}
    for key, props in runnables.items():
        rid = props.get("id")
        if rid is not None:
            id_to_key[str(rid)] = key

    # dependency resolution
    for key, props in runnables.items():
        r_type = props.get("type", "event")

        raw_deps = props.get("deps", []) or []
        resolved_deps = []

        for dep in raw_deps:
            dep_id = str(dep)

            if dep_id in id_to_key:
                resolved_deps.append(id_to_key[dep_id])
            else:
                resolved_deps.append(dep_id)

        tasks[key] = {
            "type": r_type,
            "execution_time": int(props.get("execution_time", 0)),
            "period": int(props.get("period", 0)) if r_type == "periodic" else 0,
            "deps": resolved_deps,
            # use priority if provided, else fall back to criticality, else 0
            "priority": int(props.get("priority", props.get("criticality", 0))),
            "id": props.get("id"),
            "name": props.get("name"),
        }

    # catch broken dependencies early
    for t_name, t_props in tasks.items():
        for d in t_props["deps"]:
            if d not in tasks:
                raise ValueError(f"Unknown dependency {d!r} for task {t_name!r}")

    return tasks

