#!/usr/bin/env python3
"""
RunSoC 2.0 evaluation analysis.

Expected project layout
-----------------------

output/
  generated_tasksets/
    taskset_10_001.json
    taskset_10_002.json
    taskset_25_001.json
    ...
  solutions/
    taskset_10_001/
      CPSAT_solution.json
      CBC_solution.json
      GA_solution.json
    taskset_10_002/
      CPSAT_solution.json
      CBC_solution.json
      GA_solution.json

Generated analyses
------------------

1. Runtime vs. task count, one line per solver.
1b. Runtime vs. job count, one line per solver.
2. Objective gap to best-known solution, one boxplot per solver.
3. Feasibility rate vs. task count, one line per solver.
4. Objective decomposition, stacked bars for memory vs. communication penalty.
5. Platform comparison, objective and memory overflow across Renesas / NVIDIA / TI.
6. Bottleneck heatmap, showing whether each run is memory-, communication-, compute-, or deadline-limited.

Usage
-----

Command line:

    python evaluation_analysis.py \
      --output-root ./output \
      --analysis-dir ./analysis_results

Optional:

    python evaluation_analysis.py \
      --output-root ./output \
      --analysis-dir ./analysis_results \
      --target-sizes-only

From Python:

    from pathlib import Path
    from evaluation_analysis import run_analysis

    df, agg = run_analysis(
        output_root=Path("./output"),
        analysis_dir=Path("./analysis_results"),
        target_sizes_only=False,
    )
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import pandas as pd


TARGET_TASK_SIZES = [10, 25, 50, 100, 250, 500]

SOLVER_ORDER = ["CPSAT", "CBC", "GA"]
BOTTLENECK_ORDER = ["memory", "communication", "compute", "deadline", "none", "unknown"]


# ---------------------------------------------------------------------
# Basic IO
# ---------------------------------------------------------------------


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_solution_files(output_root: Path) -> Iterable[Path]:
    """
    Finds files like:
        output/solutions/taskset_10_001/CPSAT_solution.json
        output/solutions/taskset_10_001/CBC_solution.json
        output/solutions/taskset_10_001/GA_solution.json
    """
    solutions_dir = output_root / "solutions"

    if not solutions_dir.exists():
        raise FileNotFoundError(f"Solutions directory does not exist: {solutions_dir}")

    yield from sorted(solutions_dir.glob("taskset_*/*_solution.json"))


# ---------------------------------------------------------------------
# Safe extraction helpers
# ---------------------------------------------------------------------


def get_nested(data: Dict[str, Any], path: Sequence[str], default: Any = None) -> Any:
    cur: Any = data

    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]

    return cur


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(parsed) or math.isinf(parsed):
        return None

    return parsed


def as_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "feasible", "optimal"}
    return False


def normalize_solver_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"

    s = str(value).strip().upper()

    aliases = {
        "CP-SAT": "CPSAT",
        "CP_SAT": "CPSAT",
        "ORTOOLS": "CPSAT",
        "OR-TOOLS": "CPSAT",
        "GOOGLE OR-TOOLS CP-SAT": "CPSAT",
        "COIN-OR CBC": "CBC",
        "COINOR CBC": "CBC",
        "GENETIC ALGORITHM": "GA",
        "GENETIC": "GA",
    }

    return aliases.get(s, s)


def ordered_unique(values: Sequence[Any], preferred: Sequence[Any]) -> List[Any]:
    present = [v for v in preferred if v in set(values)]
    remaining = sorted(v for v in set(values) if v not in set(preferred))
    return present + remaining


# ---------------------------------------------------------------------
# Taskset metadata
# ---------------------------------------------------------------------


def parse_taskset_id_from_solution_path(solution_path: Path) -> str:
    """
    Example:
        output/solutions/taskset_10_001/CPSAT_solution.json
    Returns:
        taskset_10_001
    """
    return solution_path.parent.name


def parse_solver_from_solution_path(solution_path: Path) -> str:
    """
    Example:
        CPSAT_solution.json -> CPSAT
        CBC_solution.json   -> CBC
        GA_solution.json    -> GA
    """
    name = solution_path.stem

    if name.endswith("_solution"):
        name = name[: -len("_solution")]

    return normalize_solver_name(name)


def parse_taskset_parts(taskset_id: str) -> Dict[str, Optional[str]]:
    """
    Supports both legacy and platform-prefixed taskset IDs.

    Legacy:
        taskset_10_001

    Multi-platform:
        taskset_nvidia_10_001
        taskset_renesas_25_010
        taskset_ti_100_003
    """
    platform_match = re.match(r"taskset_([A-Za-z0-9-]+)_(\d+)_(.+)$", taskset_id)
    if platform_match:
        return {
            "platform_key_from_id": platform_match.group(1),
            "task_count_from_id": platform_match.group(2),
            "taskset_run_id": platform_match.group(3),
        }

    legacy_match = re.match(r"taskset_(\d+)_(.+)$", taskset_id)
    if legacy_match:
        return {
            "platform_key_from_id": None,
            "task_count_from_id": legacy_match.group(1),
            "taskset_run_id": legacy_match.group(2),
        }

    return {
        "platform_key_from_id": None,
        "task_count_from_id": None,
        "taskset_run_id": None,
    }


def parse_platform_key_from_taskset_id(taskset_id: str) -> Optional[str]:
    return parse_taskset_parts(taskset_id)["platform_key_from_id"]


def parse_task_count_from_taskset_id(taskset_id: str) -> Optional[int]:
    raw = parse_taskset_parts(taskset_id)["task_count_from_id"]
    return int(raw) if raw is not None else None


def parse_taskset_run_id(taskset_id: str) -> Optional[str]:
    return parse_taskset_parts(taskset_id)["taskset_run_id"]

def get_generated_taskset_path(output_root: Path, taskset_id: str) -> Path:
    return output_root / "generated_tasksets" / f"{taskset_id}.json"


def normalize_platform_name(platform_name: Any) -> str:
    """
    Maps concrete platform identifiers to paper-level platform names.
    The original value is retained separately in platform_name.
    """
    if platform_name is None:
        return "UNKNOWN"

    raw = str(platform_name).strip()
    s = raw.lower()

    if "renesas" in s or "rcar" in s or "r-car" in s:
        return "Renesas"
    if "nvidia" in s or "jetson" in s or "orin" in s:
        return "NVIDIA"
    if "ti" in s or "tda4" in s or "texas" in s:
        return "TI"

    return raw


def extract_input_taskset_metadata(output_root: Path, taskset_id: str) -> Dict[str, Any]:
    """
    Reads output/generated_tasksets/taskset_X_YYY.json when available.
    Useful as a fallback if solver output is missing summary fields.
    """
    path = get_generated_taskset_path(output_root, taskset_id)

    metadata: Dict[str, Any] = {
        "input_taskset_file": str(path),
        "input_taskset_exists": path.exists(),
        "input_task_count": None,
        "platform_name": None,
        "platform_group": "UNKNOWN",
        "input_num_cores": None,
        "input_num_clusters": None,
        "input_task_memory_kb_sum": None,
        "input_task_wcet_sum": None,
        "input_dependency_count": None,
    }

    if not path.exists():
        return metadata

    try:
        taskset = load_json(path)
    except Exception:
        return metadata

    tasks = taskset.get("tasks", [])
    platform = taskset.get("platform", {}) or {}

    if isinstance(tasks, list):
        total_memory = sum(as_float(t.get("memoryUsageKB")) or 0.0 for t in tasks if isinstance(t, dict))
        total_wcet = sum(as_float(t.get("wcet")) or 0.0 for t in tasks if isinstance(t, dict))
        dependency_count = sum(
            len(t.get("dependencies", []))
            for t in tasks
            if isinstance(t, dict) and isinstance(t.get("dependencies", []), list)
        )
    else:
        total_memory = None
        total_wcet = None
        dependency_count = None

    platform_name = platform.get("name")

    metadata.update(
        {
            "input_task_count": len(tasks) if isinstance(tasks, list) else None,
            "platform_name": platform_name,
            "platform_group": normalize_platform_name(platform_name),
            "input_num_cores": platform.get("numCores"),
            "input_num_clusters": platform.get("numClusters"),
            "input_task_memory_kb_sum": total_memory,
            "input_task_wcet_sum": total_wcet,
            "input_dependency_count": dependency_count,
        }
    )

    return metadata


# ---------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------


def extract_runtime_seconds(result: Dict[str, Any]) -> Optional[float]:
    """
    Runtime priority:
    1. top-level runtime_seconds
    2. metadata.runtime_seconds
    3. metadata.wall_time
    4. metadata.solve_time
    """
    candidates = [
        result.get("runtime_seconds"),
        get_nested(result, ["metadata", "runtime_seconds"]),
        get_nested(result, ["metadata", "wall_time"]),
        get_nested(result, ["metadata", "solve_time"]),
    ]

    for value in candidates:
        parsed = as_float(value)

        if parsed is not None:
            return parsed

    return None


def extract_best_objective_bound(result: Dict[str, Any]) -> Optional[float]:
    """
    Handles CP-SAT scaled metadata.

    Example:
        objective = 27.78
        metadata.best_objective_bound = 2778.0
        metadata.time_scale = 100

    In that case the bound is converted to 27.78.
    """
    raw_bound = as_float(get_nested(result, ["metadata", "best_objective_bound"]))

    if raw_bound is None:
        return None

    objective = as_float(result.get("objective"))
    time_scale = as_float(get_nested(result, ["metadata", "time_scale"]))

    if objective is not None and time_scale not in (None, 0):
        scaled_back = raw_bound / time_scale

        raw_gap = abs(raw_bound - objective)
        scaled_gap = abs(scaled_back - objective)

        if scaled_gap < raw_gap:
            return scaled_back

    return raw_bound


def sum_overflow(resource_entries: Any) -> float:
    if not isinstance(resource_entries, list):
        return 0.0

    total = 0.0
    for entry in resource_entries:
        if not isinstance(entry, dict):
            continue
        total += as_float(entry.get("overflow")) or 0.0
    return total


def sum_memory_used(resource_entries: Any) -> float:
    if not isinstance(resource_entries, list):
        return 0.0

    total = 0.0
    for entry in resource_entries:
        if not isinstance(entry, dict):
            continue
        total += as_float(entry.get("used")) or 0.0
    return total


def count_violating_memory_nodes(resource_entries: Any) -> int:
    if not isinstance(resource_entries, list):
        return 0

    count = 0
    for entry in resource_entries:
        if not isinstance(entry, dict):
            continue
        if (as_float(entry.get("overflow")) or 0.0) > 0:
            count += 1
    return count


def extract_memory_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    core_memory = get_nested(result, ["resource_usage", "core_memory"], [])
    cluster_memory = get_nested(result, ["resource_usage", "cluster_memory"], [])

    core_overflow = sum_overflow(core_memory)
    cluster_overflow = sum_overflow(cluster_memory)

    return {
        "core_memory_used_kb": sum_memory_used(core_memory),
        "cluster_memory_used_kb": sum_memory_used(cluster_memory),
        "core_memory_overflow_kb": core_overflow,
        "cluster_memory_overflow_kb": cluster_overflow,
        "total_memory_overflow_kb": core_overflow + cluster_overflow,
        "core_memory_overflow_nodes": count_violating_memory_nodes(core_memory),
        "cluster_memory_overflow_nodes": count_violating_memory_nodes(cluster_memory),
    }


def infer_communication_cost(result: Dict[str, Any]) -> Optional[float]:
    """
    Prefer explicit communication costs. Fall back to a schedule-based estimate:
    every predecessor edge crossing cores or clusters contributes one unit count.

    This fallback is deliberately a count, not the weighted objective penalty,
    because the input generator can vary communication weights.
    """
    explicit_candidates = [
        get_nested(result, ["communication_cost"]),
        get_nested(result, ["comm_cost"]),
        get_nested(result, ["metadata", "comm_cost"]),
        get_nested(result, ["metadata", "communication_cost"]),
        get_nested(result, ["summary", "communication_cost"]),
    ]

    for value in explicit_candidates:
        parsed = as_float(value)
        if parsed is not None:
            return parsed

    schedule = result.get("schedule", [])
    if not isinstance(schedule, list):
        return None

    by_job_id = {
        str(job.get("job_id")): job
        for job in schedule
        if isinstance(job, dict) and job.get("job_id") is not None
    }

    if not by_job_id:
        return None

    crossings = 0.0
    for job in by_job_id.values():
        predecessors = job.get("predecessors", [])
        if not isinstance(predecessors, list):
            continue

        for pred_id in predecessors:
            pred = by_job_id.get(str(pred_id))
            if not isinstance(pred, dict):
                continue

            if pred.get("assigned_cluster") != job.get("assigned_cluster"):
                crossings += 1.0
            elif pred.get("assigned_core") != job.get("assigned_core"):
                crossings += 1.0

    return crossings


def infer_deadline_violation(result: Dict[str, Any]) -> Optional[float]:
    metadata = result.get("metadata", {}) or {}

    explicit_candidates = [
        get_nested(result, ["deadline_violation"]),
        get_nested(metadata, ["deadline_violation"]),
        get_nested(metadata, ["strict_chain_violation"]),
        get_nested(metadata, ["constraint_violation"]),
    ]

    for value in explicit_candidates:
        parsed = as_float(value)
        if parsed is not None:
            return parsed

    schedule = result.get("schedule", [])
    if not isinstance(schedule, list):
        return None

    total_lateness = 0.0
    seen = False
    for job in schedule:
        if not isinstance(job, dict):
            continue
        finish = as_float(job.get("finish_time"))
        deadline = as_float(job.get("absolute_deadline"))
        if finish is None or deadline is None:
            continue
        seen = True
        total_lateness += max(0.0, finish - deadline)

    return total_lateness if seen else None


def infer_compute_pressure(result: Dict[str, Any]) -> Optional[float]:
    """
    Estimate compute pressure as total scheduled duration divided by makespan.
    This is intentionally simple and solver-agnostic.
    """
    schedule = result.get("schedule", [])
    makespan = as_float(result.get("makespan"))

    if not isinstance(schedule, list) or not schedule or makespan in (None, 0):
        return None

    total_duration = 0.0
    seen = False
    for job in schedule:
        if not isinstance(job, dict):
            continue
        duration = as_float(job.get("scheduled_duration"))
        if duration is None:
            start = as_float(job.get("start_time"))
            finish = as_float(job.get("finish_time"))
            if start is not None and finish is not None:
                duration = max(0.0, finish - start)
        if duration is not None:
            total_duration += duration
            seen = True

    if not seen:
        return None

    return total_duration / max(makespan, 1.0)


def infer_memory_penalty(result: Dict[str, Any]) -> Optional[float]:
    """
    Prefer explicit memory penalties. Otherwise compute an unweighted/partly
    weighted overflow proxy from resource_usage and config-style scales when
    available in the result.
    """
    explicit_candidates = [
        get_nested(result, ["memory_penalty"]),
        get_nested(result, ["summary", "memory_penalty"]),
        get_nested(result, ["metadata", "memory_penalty"]),
    ]

    for value in explicit_candidates:
        parsed = as_float(value)
        if parsed is not None:
            return parsed

    core_scale = as_float(get_nested(result, ["config", "memoryPenaltyScale", "coreOverflowScale"]))
    cluster_scale = as_float(get_nested(result, ["config", "memoryPenaltyScale", "clusterOverflowScale"]))

    if core_scale is None:
        core_scale = 1.0
    if cluster_scale is None:
        cluster_scale = 1.0

    core_overflow = sum_overflow(get_nested(result, ["resource_usage", "core_memory"], []))
    cluster_overflow = sum_overflow(get_nested(result, ["resource_usage", "cluster_memory"], []))

    if core_overflow == 0.0 and cluster_overflow == 0.0:
        return 0.0

    return core_scale * core_overflow + cluster_scale * cluster_overflow


def compute_gap_to_bound(
    objective: Optional[float],
    best_objective_bound: Optional[float],
) -> Optional[float]:
    """
    Solver-internal bound gap, mainly useful for CP-SAT/CBC when bound data exists.

        gap = abs(objective - best_objective_bound) / max(abs(objective), 1)
    """
    if objective is None or best_objective_bound is None:
        return None

    return abs(objective - best_objective_bound) / max(abs(objective), 1.0)


def classify_bottleneck(record: Dict[str, Any]) -> str:
    """
    Classifies a run using observable solver-output signals.

    Priority is intentional:
      1. Deadline violation is a hard real-time failure.
      2. Memory overflow is directly represented in resource_usage.
      3. Communication pressure is inferred from explicit/derived comm cost.
      4. Compute pressure is inferred from schedule duration / makespan.
    """
    deadline_violation = as_float(record.get("deadline_violation")) or 0.0
    memory_overflow = as_float(record.get("total_memory_overflow_kb")) or 0.0
    comm_penalty = as_float(record.get("communication_penalty"))
    compute_pressure = as_float(record.get("compute_pressure"))

    if deadline_violation > 0:
        return "deadline"
    if memory_overflow > 0:
        return "memory"
    if comm_penalty is not None and comm_penalty > 0:
        return "communication"
    if compute_pressure is not None and compute_pressure >= 0.85:
        return "compute"
    if any(v is not None for v in [comm_penalty, compute_pressure]) or memory_overflow == 0:
        return "none"
    return "unknown"


def extract_record(output_root: Path, solution_path: Path, result: Dict[str, Any]) -> Dict[str, Any]:
    metadata = result.get("metadata", {}) or {}
    summary = result.get("summary", {}) or {}

    taskset_id = parse_taskset_id_from_solution_path(solution_path)
    taskset_run_id = parse_taskset_run_id(taskset_id)
    platform_key_from_id = parse_platform_key_from_taskset_id(taskset_id)

    solver_from_file = parse_solver_from_solution_path(solution_path)
    solver_from_json = normalize_solver_name(result.get("solver"))

    solver = solver_from_json if solver_from_json != "UNKNOWN" else solver_from_file

    task_count_from_id = parse_task_count_from_taskset_id(taskset_id)
    input_metadata = extract_input_taskset_metadata(output_root, taskset_id)

    task_template_count = as_int(summary.get("task_template_count"))
    if task_template_count is None:
        task_template_count = as_int(input_metadata.get("input_task_count"))
    if task_template_count is None:
        task_template_count = task_count_from_id

    objective = as_float(result.get("objective"))
    best_objective_bound = extract_best_objective_bound(result)

    memory_metrics = extract_memory_metrics(result)
    communication_penalty = infer_communication_cost(result)
    memory_penalty = infer_memory_penalty(result)
    deadline_violation = infer_deadline_violation(result)
    compute_pressure = infer_compute_pressure(result)

    record: Dict[str, Any] = {
        "taskset_id": taskset_id,
        "taskset_run_id": taskset_run_id,
        "platform_key_from_id": platform_key_from_id,
        "task_count_from_id": task_count_from_id,
        "solver": solver,
        "solver_from_file": solver_from_file,
        "solver_from_json": solver_from_json,
        "solution_file": str(solution_path),
        **input_metadata,

        "status": result.get("status"),
        "feasible": bool_like(result.get("feasible", False)),
        "objective": objective,
        "best_objective_bound": best_objective_bound,
        "bound_gap": compute_gap_to_bound(objective, best_objective_bound),
        "makespan": as_float(result.get("makespan")),
        "runtime_seconds": extract_runtime_seconds(result),

        "task_template_count": task_template_count,
        "job_count": as_int(summary.get("job_count")),
        "scheduled_job_count": as_int(summary.get("scheduled_job_count")),
        "task_chain_count": as_int(summary.get("task_chain_count")),
        "dependency_template_count": as_int(summary.get("dependency_template_count")),
        "job_dependency_count": as_int(summary.get("job_dependency_count")),
        "core_count": as_int(summary.get("core_count")),
        "cluster_count": as_int(summary.get("cluster_count")),

        "memory_penalty": memory_penalty,
        "communication_penalty": communication_penalty,
        "deadline_violation": deadline_violation,
        "compute_pressure": compute_pressure,
        **memory_metrics,

        # CP-SAT metadata
        "num_conflicts": as_int(metadata.get("num_conflicts")),
        "num_branches": as_int(metadata.get("num_branches")),
        "wall_time": as_float(metadata.get("wall_time")),
        "time_scale": as_float(metadata.get("time_scale")),
        "scaled_objective": as_float(metadata.get("scaled_objective")),

        # CBC metadata
        "metadata_runtime_seconds": as_float(metadata.get("runtime_seconds")),
        "model_building_seconds": as_float(metadata.get("model_building_seconds")),
        "solve_time": as_float(metadata.get("solve_time")),

        # GA metadata
        "ga_fitness": as_float(metadata.get("fitness")),
        "ga_comm_cost": as_float(metadata.get("comm_cost")),
        "ga_strict_chain_violation": as_float(metadata.get("strict_chain_violation")),
        "ga_precedence_violation": as_float(metadata.get("precedence_violation")),
        "ga_core_overlap_violation": as_float(metadata.get("core_overlap_violation"))
        or as_float(metadata.get("same_core_overlap_violation")),
        "ga_constraint_violation": as_float(metadata.get("constraint_violation")),
        "ga_constraint_violation_cost": as_float(metadata.get("constraint_violation_cost")),
        "ga_generations_completed": as_int(
            get_nested(metadata, ["ga_metadata", "generations_completed"])
        ),
    }

    record["bottleneck"] = classify_bottleneck(record)

    return record


def add_best_known_objective_gap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds best-known objective per taskset/platform and each solver's relative gap.

    The best-known solution is computed across all feasible solver outputs for the
    same taskset_id. This is the cross-solver metric requested for boxplots.
    """
    out = df.copy()

    feasible_obj = out[out["feasible"] & out["objective"].notna()].copy()
    if feasible_obj.empty:
        out["best_known_objective"] = pd.NA
        out["objective_gap_to_best_known"] = pd.NA
        out["objective_gap_percent_to_best_known"] = pd.NA
        return out

    best = (
        feasible_obj.groupby("taskset_id", dropna=False)["objective"]
        .min()
        .rename("best_known_objective")
        .reset_index()
    )

    out = out.merge(best, on="taskset_id", how="left")
    denominator = out["best_known_objective"].abs().clip(lower=1.0)
    out["objective_gap_to_best_known"] = (
        out["objective"] - out["best_known_objective"]
    ) / denominator
    out.loc[out["objective"].isna() | out["best_known_objective"].isna(), "objective_gap_to_best_known"] = pd.NA
    out["objective_gap_percent_to_best_known"] = 100.0 * out["objective_gap_to_best_known"]

    return out


def load_results(output_root: Path) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []

    for solution_path in iter_solution_files(output_root):
        try:
            result = load_json(solution_path)
            records.append(extract_record(output_root, solution_path, result))
        except Exception as exc:
            print(f"WARNING: failed to parse {solution_path}: {exc}")

    if not records:
        raise RuntimeError(f"No solution JSON files found under {output_root / 'solutions'}")

    df = pd.DataFrame(records)
    df = add_best_known_objective_gap(df)
    df["is_target_task_size"] = df["task_template_count"].isin(TARGET_TASK_SIZES)

    return df


# ---------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------


def aggregate_evaluation(df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["solver", "task_template_count"]

    agg = (
        df.groupby(group_cols, dropna=False)
        .agg(
            runs=("solution_file", "count"),
            feasible_rate=("feasible", "mean"),
            runtime_mean=("runtime_seconds", "mean"),
            runtime_median=("runtime_seconds", "median"),
            runtime_std=("runtime_seconds", "std"),
            runtime_min=("runtime_seconds", "min"),
            runtime_max=("runtime_seconds", "max"),
            objective_mean=("objective", "mean"),
            objective_median=("objective", "median"),
            best_known_objective_median=("best_known_objective", "median"),
            objective_gap_to_best_known_mean=("objective_gap_to_best_known", "mean"),
            objective_gap_to_best_known_median=("objective_gap_to_best_known", "median"),
            bound_gap_mean=("bound_gap", "mean"),
            bound_gap_median=("bound_gap", "median"),
            makespan_mean=("makespan", "mean"),
            makespan_median=("makespan", "median"),
            job_count_mean=("job_count", "mean"),
            job_count_median=("job_count", "median"),
            memory_penalty_median=("memory_penalty", "median"),
            communication_penalty_median=("communication_penalty", "median"),
            total_memory_overflow_kb_median=("total_memory_overflow_kb", "median"),
            core_memory_overflow_kb_median=("core_memory_overflow_kb", "median"),
            cluster_memory_overflow_kb_median=("cluster_memory_overflow_kb", "median"),
            deadline_violation_median=("deadline_violation", "median"),
            compute_pressure_median=("compute_pressure", "median"),
            num_conflicts_mean=("num_conflicts", "mean"),
            num_conflicts_median=("num_conflicts", "median"),
            num_branches_mean=("num_branches", "mean"),
            num_branches_median=("num_branches", "median"),
        )
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )

    return agg


def aggregate_platform_comparison(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["platform_group", "solver"], dropna=False)
        .agg(
            runs=("solution_file", "count"),
            feasible_rate=("feasible", "mean"),
            objective_median=("objective", "median"),
            objective_mean=("objective", "mean"),
            total_memory_overflow_kb_median=("total_memory_overflow_kb", "median"),
            total_memory_overflow_kb_mean=("total_memory_overflow_kb", "mean"),
            core_memory_overflow_kb_median=("core_memory_overflow_kb", "median"),
            cluster_memory_overflow_kb_median=("cluster_memory_overflow_kb", "median"),
            runtime_median=("runtime_seconds", "median"),
        )
        .reset_index()
        .sort_values(["platform_group", "solver"])
    )


def aggregate_bottlenecks(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["solver", "task_template_count", "bottleneck"], dropna=False)
        .size()
        .rename("runs")
        .reset_index()
        .sort_values(["solver", "task_template_count", "bottleneck"])
    )


# ---------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------


def ensure_analysis_dir(analysis_dir: Path) -> None:
    analysis_dir.mkdir(parents=True, exist_ok=True)


def save_current_plot(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def prepare_runtime_plot_df(df: pd.DataFrame) -> pd.DataFrame:
    plot_df = df.copy()
    plot_df = plot_df.dropna(subset=["solver", "runtime_seconds"])
    plot_df = plot_df[plot_df["runtime_seconds"] > 0]
    return plot_df


# ---------------------------------------------------------------------
# Requested plots
# ---------------------------------------------------------------------


def save_runtime_vs_task_count(df: pd.DataFrame, analysis_dir: Path) -> Path:
    plot_df = prepare_runtime_plot_df(df).dropna(subset=["task_template_count"])
    path = analysis_dir / "01_runtime_vs_task_count.png"

    if plot_df.empty:
        print("WARNING: no runtime data available; skipping runtime plot.")
        return path

    plt.figure(figsize=(8, 5))

    solver_order = ordered_unique(plot_df["solver"].dropna().unique().tolist(), SOLVER_ORDER)
    for solver in solver_order:
        sdf = plot_df[plot_df["solver"] == solver]
        grouped = (
            sdf.groupby("task_template_count")
            .agg(runtime_seconds=("runtime_seconds", "median"))
            .reset_index()
            .sort_values("task_template_count")
        )

        plt.plot(
            grouped["task_template_count"],
            grouped["runtime_seconds"],
            marker="o",
            label=solver,
        )

    plt.yscale("log")
    plt.xlabel("Number of task templates")
    plt.ylabel("Runtime seconds, log scale")
    plt.title("Solver runtime vs. task count")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    save_current_plot(path)
    return path

def save_runtime_vs_job_count(df: pd.DataFrame, analysis_dir: Path) -> Path:
    """
    Runtime vs. scheduled job count, one line per solver.

    Prefer scheduled_job_count because it reflects the realized expanded schedule.
    Fall back to job_count when scheduled_job_count is unavailable.
    """
    plot_df = prepare_runtime_plot_df(df).copy()
    path = analysis_dir / "01b_runtime_vs_job_count.png"

    if plot_df.empty:
        print("WARNING: no runtime data available; skipping job-vs-runtime plot.")
        return path

    plot_df["runtime_job_count"] = plot_df["scheduled_job_count"]
    plot_df.loc[plot_df["runtime_job_count"].isna(), "runtime_job_count"] = plot_df["job_count"]

    plot_df = plot_df.dropna(subset=["runtime_job_count"])
    plot_df = plot_df[plot_df["runtime_job_count"] > 0]

    if plot_df.empty:
        print("WARNING: no job-count data available; skipping job-vs-runtime plot.")
        return path

    plt.figure(figsize=(8, 5))

    solver_order = ordered_unique(plot_df["solver"].dropna().unique().tolist(), SOLVER_ORDER)
    for solver in solver_order:
        sdf = plot_df[plot_df["solver"] == solver]
        grouped = (
            sdf.groupby("runtime_job_count")
            .agg(runtime_seconds=("runtime_seconds", "median"))
            .reset_index()
            .sort_values("runtime_job_count")
        )

        plt.plot(
            grouped["runtime_job_count"],
            grouped["runtime_seconds"],
            marker="o",
            label=solver,
        )

    plt.yscale("log")
    plt.xlabel("Number of scheduled jobs")
    plt.ylabel("Runtime seconds, log scale")
    plt.title("Solver runtime vs. job count")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    save_current_plot(path)
    return path

def save_objective_gap_boxplot(df: pd.DataFrame, analysis_dir: Path) -> Path:
    plot_df = df.dropna(subset=["solver", "objective_gap_percent_to_best_known"]).copy()
    path = analysis_dir / "02_objective_gap_to_best_known_boxplot.png"

    if plot_df.empty:
        print("WARNING: no objective-gap data available; skipping gap boxplot.")
        return path

    solver_order = ordered_unique(plot_df["solver"].dropna().unique().tolist(), SOLVER_ORDER)
    data = [
        plot_df.loc[plot_df["solver"] == solver, "objective_gap_percent_to_best_known"].astype(float).values
        for solver in solver_order
    ]

    plt.figure(figsize=(8, 5))
    plt.boxplot(data, labels=solver_order, showmeans=True)
    plt.axhline(0, linestyle="--", linewidth=0.8)
    plt.xlabel("Solver")
    plt.ylabel("Objective gap to best-known solution (%)")
    plt.title("Objective gap to best-known solution by solver")
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5)
    save_current_plot(path)
    return path


def save_feasibility_rate_vs_task_count(df: pd.DataFrame, analysis_dir: Path) -> Path:
    plot_df = df.dropna(subset=["solver", "task_template_count"]).copy()
    path = analysis_dir / "03_feasibility_rate_vs_task_count.png"

    if plot_df.empty:
        print("WARNING: no feasibility data available; skipping feasibility plot.")
        return path

    grouped = (
        plot_df.groupby(["solver", "task_template_count"])
        .agg(feasibility_rate=("feasible", "mean"))
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )

    plt.figure(figsize=(8, 5))

    solver_order = ordered_unique(grouped["solver"].dropna().unique().tolist(), SOLVER_ORDER)
    for solver in solver_order:
        sdf = grouped[grouped["solver"] == solver]
        plt.plot(
            sdf["task_template_count"],
            sdf["feasibility_rate"],
            marker="o",
            label=solver,
        )

    plt.ylim(-0.05, 1.05)
    plt.xlabel("Number of task templates")
    plt.ylabel("Feasibility rate")
    plt.title("Feasibility rate vs. task count")
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.legend()
    save_current_plot(path)
    return path


def save_objective_decomposition(df: pd.DataFrame, analysis_dir: Path) -> Path:
    """
    Stacked bars for median memory penalty vs. communication penalty.
    Bars are grouped by solver and task count.
    """
    plot_df = df.dropna(subset=["solver", "task_template_count"]).copy()
    path = analysis_dir / "04_objective_decomposition_memory_vs_communication.png"

    if plot_df.empty:
        print("WARNING: no decomposition data available; skipping decomposition plot.")
        return path

    grouped = (
        plot_df.groupby(["solver", "task_template_count"])
        .agg(
            memory_penalty=("memory_penalty", "median"),
            communication_penalty=("communication_penalty", "median"),
        )
        .reset_index()
        .sort_values(["task_template_count", "solver"])
    )

    if grouped[["memory_penalty", "communication_penalty"]].fillna(0).sum().sum() == 0:
        print("WARNING: objective decomposition is all zero; plot will still be written.")

    grouped["label"] = grouped["task_template_count"].astype(str) + " / " + grouped["solver"].astype(str)
    x = list(range(len(grouped)))

    memory_values = grouped["memory_penalty"].fillna(0.0).astype(float).values
    comm_values = grouped["communication_penalty"].fillna(0.0).astype(float).values

    plt.figure(figsize=(max(10, len(grouped) * 0.45), 5.5))
    plt.bar(x, memory_values, label="Memory penalty")
    plt.bar(x, comm_values, bottom=memory_values, label="Communication penalty")
    plt.xticks(x, grouped["label"], rotation=60, ha="right")
    plt.xlabel("Task count / solver")
    plt.ylabel("Penalty contribution, median")
    plt.title("Objective decomposition: memory vs. communication penalty")
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5)
    plt.legend()
    save_current_plot(path)
    return path


def save_platform_comparison(df: pd.DataFrame, analysis_dir: Path) -> Path:
    """
    Platform comparison with two vertically stacked axes:
      - median objective
      - median total memory overflow
    """
    plot_df = df.dropna(subset=["platform_group", "solver"]).copy()
    path = analysis_dir / "05_platform_comparison_objective_memory_overflow.png"

    if plot_df.empty:
        print("WARNING: no platform data available; skipping platform comparison plot.")
        return path

    grouped = (
        plot_df.groupby(["platform_group", "solver"])
        .agg(
            objective=("objective", "median"),
            total_memory_overflow_kb=("total_memory_overflow_kb", "median"),
        )
        .reset_index()
    )

    platform_order = ordered_unique(
        grouped["platform_group"].dropna().unique().tolist(),
        ["Renesas", "NVIDIA", "TI"],
    )
    solver_order = ordered_unique(grouped["solver"].dropna().unique().tolist(), SOLVER_ORDER)

    pivot_obj = grouped.pivot(index="platform_group", columns="solver", values="objective").reindex(platform_order)
    pivot_mem = grouped.pivot(index="platform_group", columns="solver", values="total_memory_overflow_kb").reindex(platform_order)
    pivot_obj = pivot_obj.reindex(columns=solver_order)
    pivot_mem = pivot_mem.reindex(columns=solver_order)

    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    pivot_obj.plot(kind="bar", ax=axes[0])
    axes[0].set_ylabel("Median objective")
    axes[0].set_title("Platform comparison: objective")
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.5)
    axes[0].legend(title="Solver")

    pivot_mem.plot(kind="bar", ax=axes[1])
    axes[1].set_ylabel("Median memory overflow, KB")
    axes[1].set_title("Platform comparison: memory overflow")
    axes[1].grid(True, axis="y", linestyle="--", linewidth=0.5)
    axes[1].legend(title="Solver")
    axes[1].set_xlabel("Platform")

    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close(fig)
    return path


def save_bottleneck_heatmap(df: pd.DataFrame, analysis_dir: Path) -> Path:
    """
    Heatmap cell value: dominant bottleneck class for each solver/task-count pair.
    Also writes a companion CSV with the run counts per class.
    """
    plot_df = df.dropna(subset=["solver", "task_template_count", "bottleneck"]).copy()
    path = analysis_dir / "06_bottleneck_heatmap.png"
    csv_path = analysis_dir / "bottleneck_counts.csv"

    if plot_df.empty:
        print("WARNING: no bottleneck data available; skipping bottleneck heatmap.")
        return path

    counts = (
        plot_df.groupby(["solver", "task_template_count", "bottleneck"])
        .size()
        .rename("runs")
        .reset_index()
    )
    counts.to_csv(csv_path, index=False)

    dominant = (
        counts.sort_values(["solver", "task_template_count", "runs"], ascending=[True, True, False])
        .drop_duplicates(["solver", "task_template_count"])
        .copy()
    )

    task_counts = sorted(plot_df["task_template_count"].dropna().astype(int).unique())
    solver_order = ordered_unique(plot_df["solver"].dropna().unique().tolist(), SOLVER_ORDER)

    code_map = {name: idx for idx, name in enumerate(BOTTLENECK_ORDER)}
    matrix: List[List[float]] = []
    labels: List[List[str]] = []

    for solver in solver_order:
        row: List[float] = []
        label_row: List[str] = []
        for task_count in task_counts:
            match = dominant[
                (dominant["solver"] == solver)
                & (dominant["task_template_count"].astype(int) == int(task_count))
            ]
            if match.empty:
                row.append(float("nan"))
                label_row.append("")
            else:
                bottleneck = str(match.iloc[0]["bottleneck"])
                runs = int(match.iloc[0]["runs"])
                row.append(float(code_map.get(bottleneck, code_map["unknown"])))
                label_row.append(f"{bottleneck}\n({runs})")
        matrix.append(row)
        labels.append(label_row)

    plt.figure(figsize=(max(8, len(task_counts) * 0.8), max(3.5, len(solver_order) * 0.8)))
    plt.imshow(matrix, aspect="auto", interpolation="nearest")
    plt.xticks(range(len(task_counts)), task_counts)
    plt.yticks(range(len(solver_order)), solver_order)
    plt.xlabel("Number of task templates")
    plt.ylabel("Solver")
    plt.title("Dominant bottleneck heatmap")

    cbar = plt.colorbar(ticks=list(code_map.values()))
    cbar.ax.set_yticklabels(BOTTLENECK_ORDER)

    for i, row in enumerate(labels):
        for j, text in enumerate(row):
            if text:
                plt.text(j, i, text, ha="center", va="center", fontsize=8)

    save_current_plot(path)
    return path


def save_all_plots(df: pd.DataFrame, analysis_dir: Path) -> List[Path]:
    paths = [
        save_runtime_vs_task_count(df, analysis_dir),
        save_runtime_vs_job_count(df, analysis_dir),
        save_objective_gap_boxplot(df, analysis_dir),
        save_feasibility_rate_vs_task_count(df, analysis_dir),
        save_objective_decomposition(df, analysis_dir),
        save_platform_comparison(df, analysis_dir),
        save_bottleneck_heatmap(df, analysis_dir),
    ]
    return paths


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


def print_summary(df: pd.DataFrame, agg: pd.DataFrame, platform_agg: pd.DataFrame) -> None:
    print("\n=== Loaded solution files ===")
    print(len(df))

    print("\n=== Solvers ===")
    print(", ".join(sorted(df["solver"].dropna().unique())))

    print("\n=== Task template counts ===")
    counts = sorted(df["task_template_count"].dropna().astype(int).unique())
    print(counts)

    print("\n=== Platforms ===")
    platform_cols = ["platform_group", "platform_name"]
    print(df[platform_cols].drop_duplicates().sort_values(platform_cols).to_string(index=False))

    print("\n=== Missing generated input files ===")
    missing = df[~df["input_taskset_exists"]]["taskset_id"].drop_duplicates().tolist()
    if missing:
        for taskset_id in missing:
            print(f"  - {taskset_id}")
    else:
        print("None")

    print("\n=== Aggregated evaluation summary ===")
    display_cols = [
        "solver",
        "task_template_count",
        "runs",
        "feasible_rate",
        "runtime_median",
        "objective_median",
        "best_known_objective_median",
        "objective_gap_to_best_known_median",
        "memory_penalty_median",
        "communication_penalty_median",
        "total_memory_overflow_kb_median",
        "bound_gap_median",
        "num_conflicts_median",
        "num_branches_median",
    ]
    available_cols = [c for c in display_cols if c in agg.columns]
    print(agg[available_cols].to_string(index=False))

    print("\n=== Platform comparison summary ===")
    platform_display_cols = [
        "platform_group",
        "solver",
        "runs",
        "feasible_rate",
        "objective_median",
        "total_memory_overflow_kb_median",
        "runtime_median",
    ]
    available_platform_cols = [c for c in platform_display_cols if c in platform_agg.columns]
    print(platform_agg[available_platform_cols].to_string(index=False))


# ---------------------------------------------------------------------
# Public callable API
# ---------------------------------------------------------------------


def run_analysis(
    output_root: Path,
    analysis_dir: Path,
    target_sizes_only: bool = False,
    write_outputs: bool = True,
    make_plots: bool = True,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Callable entry point for notebooks or other Python scripts.

    Parameters
    ----------
    output_root:
        Root directory containing generated_tasksets/ and solutions/.
    analysis_dir:
        Directory where CSV summaries and plots are written.
    target_sizes_only:
        If true, keep only TARGET_TASK_SIZES.
    write_outputs:
        If true, write raw and aggregated CSV files.
    make_plots:
        If true, write the six requested PNG plots.
    verbose:
        If true, print summaries and written paths.

    Returns
    -------
    df:
        One row per solver result JSON.
    agg:
        Aggregated solver x task-count summary.
    """
    output_root = Path(output_root)
    analysis_dir = Path(analysis_dir)

    if not output_root.exists():
        raise FileNotFoundError(f"Output root does not exist: {output_root}")

    ensure_analysis_dir(analysis_dir)

    df = load_results(output_root)

    if target_sizes_only:
        df = df[df["task_template_count"].isin(TARGET_TASK_SIZES)].copy()

    agg = aggregate_evaluation(df)
    platform_agg = aggregate_platform_comparison(df)
    bottleneck_agg = aggregate_bottlenecks(df)

    written_paths: List[Path] = []

    if write_outputs:
        raw_csv = analysis_dir / "evaluation_raw_results.csv"
        agg_csv = analysis_dir / "evaluation_aggregated_summary.csv"
        platform_csv = analysis_dir / "platform_comparison_summary.csv"
        bottleneck_csv = analysis_dir / "bottleneck_summary.csv"

        df.to_csv(raw_csv, index=False)
        agg.to_csv(agg_csv, index=False)
        platform_agg.to_csv(platform_csv, index=False)
        bottleneck_agg.to_csv(bottleneck_csv, index=False)
        written_paths.extend([raw_csv, agg_csv, platform_csv, bottleneck_csv])

    if make_plots:
        written_paths.extend(save_all_plots(df, analysis_dir))

    if verbose:
        print_summary(df, agg, platform_agg)
        print("\n=== Written outputs ===")
        for path in written_paths:
            print(path)

    return df, agg


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze RunSoC 2.0 solver outputs from output/solutions layout."
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Root output directory containing generated_tasksets/ and solutions/.",
    )

    parser.add_argument(
        "--analysis-dir",
        type=Path,
        required=True,
        help="Directory where CSV summaries and plots will be written.",
    )

    parser.add_argument(
        "--target-sizes-only",
        action="store_true",
        help="Keep only task sizes 10, 25, 50, 100, 250, and 500.",
    )

    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Write CSV outputs only; skip PNG plot generation.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress printed summaries.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_analysis(
        output_root=args.output_root,
        analysis_dir=args.analysis_dir,
        target_sizes_only=args.target_sizes_only,
        write_outputs=True,
        make_plots=not args.no_plots,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
