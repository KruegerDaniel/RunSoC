from typing import Dict, Any


def normalize_runnables(runnables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Force numbers to ints, deps to list of str.
    """
    for name, props in runnables.items():
        for key in ['period', 'execution_time', 'criticality', 'affinity']:
            if key in props and props[key] not in (None, ''):
                props[key] = int(props[key])
        if 'deps' in props and isinstance(props['deps'], list):
            props['deps'] = [str(dep) for dep in props['deps']]
    return runnables


def to_main_tasks(runnables: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Convert frontend-style runnables into main_scheduler tasks.
    """
    tasks: Dict[str, Dict[str, Any]] = {}
    for name, props in runnables.items():
        r_type = props.get("type", "event")
        tasks[name] = {
            "type": r_type,
            "execution_time": int(props.get("execution_time", 0)),
            "period": int(props.get("period", 0)) if r_type == "periodic" else 0,
            "deps": props.get("deps", []) or [],
            # use priority if provided, else fall back to criticality, else 0
            "priority": int(props.get("priority", props.get("criticality", 0))),
        }
    return tasks
