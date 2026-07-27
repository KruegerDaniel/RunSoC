#!/usr/bin/env python3
"""
RunSoC 2.0 thesis-grade results analysis.

This script is intended to replace a minimal plotting-only evaluation script with a
results pipeline that is defensible for a thesis chapter.  It keeps every attempted
run in the denominator, separates solver status accounting from solution-quality
analysis, reconstructs objective components only when explicit solver output is
missing, and computes task-chain locality/latency metrics.

Expected project layout
-----------------------

The script supports the original layout:

    output/
      generated_tasksets/
        taskset_renesas_10_001.json
        taskset_nvidia_10_001.json
        taskset_ti_10_001.json
        taskset_10_001.json
      solutions/
        taskset_renesas_10_001/
          CPSAT_solution.json
          CBC_solution.json
          GA_solution.json

It also supports an optional manifest file.  A manifest is strongly recommended for
final thesis runs because it preserves solver attempts that never produced solution
files, such as presolve rejections, API errors, or timeouts without output.

Manifest columns / JSON keys recognized
---------------------------------------

    taskset_id, solver, platform, task_count, run_id, status, feasible,
    runtime_seconds, solution_file, input_taskset_file, error_message

CSV, JSON array, and JSONL manifests are supported.

Generated outputs
-----------------

CSV files:
    evaluation_raw_results.csv
    evaluation_aggregated_summary.csv
    status_counts.csv
    objective_components_summary.csv
    platform_comparison_summary.csv
    platform_paired_summary.csv
    platform_pair_coverage.csv
    chain_locality_summary.csv
    chain_locality_details.csv
    communication_edges_summary.csv
    bottleneck_summary.csv
    data_quality_report.csv

Figures:
    01_runtime_vs_task_count.png
    01b_runtime_vs_job_count.png
    02_status_distribution_vs_task_count.png
    03_feasibility_rate_vs_task_count.png
    04_objective_gap_to_best_known_boxplot.png
    05_objective_decomposition.png
    06_platform_paired_objective_memory.png
    07_chain_locality_rates.png
    08_chain_latency_vs_task_count.png
    09_dominant_bottleneck_heatmap.png

Example usage
-------------

    python run_soc_results_analysis.py \
      --output-root ./output \
      --analysis-dir ./analysis_results \
      --expected-solvers CPSAT CBC GA \
      --target-sizes 10 50 100 200 500 1000 \
      --solver-timeout 1000

With an explicit manifest:

    python run_soc_results_analysis.py \
      --output-root ./output \
      --analysis-dir ./analysis_results \
      --manifest ./output/run_manifest.csv

From Python:

    from pathlib import Path
    from run_soc_results_analysis import run_analysis

    df, agg = run_analysis(
        output_root=Path("./output"),
        analysis_dir=Path("./analysis_results"),
    )
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_TARGET_TASK_SIZES = [10, 50, 100, 200, 500, 1000]
DEFAULT_SOLVER_ORDER = ["CPSAT", "CBC", "GA"]
DEFAULT_PLATFORM_ORDER = ["Renesas", "NVIDIA", "TI"]

# Thesis experiment defaults.  They are used only when neither the solution JSON nor
# the input JSON exposes these values.
DEFAULT_CORE_OVERFLOW_SCALE = 1.0
DEFAULT_CLUSTER_OVERFLOW_SCALE = 2.0
DEFAULT_COMM_SAME_CORE = 0.0
DEFAULT_COMM_SAME_CLUSTER = 8.0
DEFAULT_COMM_INTER_CLUSTER = 15.0

STATUS_ORDER = [
    "OPTIMAL",
    "FEASIBLE",
    "TIMEOUT_FEASIBLE",
    "TIMEOUT_NO_SOLUTION",
    "INFEASIBLE",
    "PRESOLVE_REJECTED",
    "ERROR",
    "MISSING_SOLUTION",
    "UNKNOWN",
]

BOTTLENECK_ORDER = ["memory", "communication", "compute", "deadline", "none", "unknown"]

TITLE_FONTSIZE = 17
AXIS_LABEL_FONTSIZE = 14
TICK_LABEL_FONTSIZE = 12
LEGEND_FONTSIZE = 11
ANNOTATION_FONTSIZE = 9


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TaskInfo:
    task_id: str
    name: Optional[str] = None
    period: Optional[float] = None
    wcet: Optional[float] = None
    memory_kb: float = 0.0
    required_domain: Optional[str] = None
    task_type: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class CoreInfo:
    core_id: str
    cluster_id: Optional[str] = None
    name: Optional[str] = None
    memory_budget_kb: Optional[float] = None
    wcet_scale: Optional[float] = None


@dataclass
class ClusterInfo:
    cluster_id: str
    name: Optional[str] = None
    memory_budget_kb: Optional[float] = None


@dataclass
class ChainInfo:
    chain_id: str
    task_ids: List[str]
    deadline: Optional[float] = None
    period: Optional[float] = None
    release_offset: Optional[float] = None
    source: str = "explicit"


@dataclass
class InputMetadata:
    path: Optional[Path]
    exists: bool
    taskset_id: str
    task_count: Optional[int] = None
    task_count_from_id: Optional[int] = None
    run_id: Optional[str] = None
    platform_key_from_id: Optional[str] = None
    platform_name: Optional[str] = None
    platform_group: str = "UNKNOWN"
    base_workload_key: Optional[str] = None
    num_cores: Optional[int] = None
    num_clusters: Optional[int] = None
    total_task_memory_kb: Optional[float] = None
    total_task_wcet: Optional[float] = None
    dependency_count: Optional[int] = None
    tasks: Dict[str, TaskInfo] = field(default_factory=dict)
    cores: Dict[str, CoreInfo] = field(default_factory=dict)
    clusters: Dict[str, ClusterInfo] = field(default_factory=dict)
    chains: List[ChainInfo] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobInfo:
    job_id: str
    task_id: Optional[str]
    start: Optional[float]
    finish: Optional[float]
    duration: Optional[float]
    core_id: Optional[str]
    cluster_id: Optional[str]
    release: Optional[float]
    deadline: Optional[float]
    predecessors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic safe access helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if isinstance(value, dict):
        return value
    return {"_root": value}


def load_json_any(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def get_nested(data: Mapping[str, Any], path: Sequence[str], default: Any = None) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return cur


def first_present(data: Mapping[str, Any], paths: Sequence[Sequence[str]], default: Any = None) -> Any:
    for path in paths:
        value = get_nested(data, path, None)
        if value is not None:
            return value
    return default


def first_key(data: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
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
    if isinstance(value, bool):
        return int(value)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def bool_like(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "yes", "y", "1", "feasible", "optimal", "ok", "success"}:
            return True
        if s in {"false", "no", "n", "0", "infeasible", "error", "failed", "failure"}:
            return False
    return None


def normalized_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def median_or_none(values: Sequence[float]) -> Optional[float]:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return None
    return float(statistics.median(clean))


def p95_or_none(values: Sequence[float]) -> Optional[float]:
    clean = sorted(v for v in values if v is not None and not math.isnan(v))
    if not clean:
        return None
    if len(clean) == 1:
        return float(clean[0])
    # Inclusive empirical percentile.
    idx = int(math.ceil(0.95 * len(clean))) - 1
    idx = max(0, min(idx, len(clean) - 1))
    return float(clean[idx])


def ordered_unique(values: Sequence[Any], preferred: Sequence[Any]) -> List[Any]:
    value_set = set(values)
    out = [v for v in preferred if v in value_set]
    out.extend(sorted(v for v in value_set if v not in set(preferred)))
    return out


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_current_plot(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


# ---------------------------------------------------------------------------
# Naming normalization
# ---------------------------------------------------------------------------


def normalize_solver_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    s = str(value).strip().upper().replace(" ", " ")
    aliases = {
        "CP-SAT": "CPSAT",
        "CP_SAT": "CPSAT",
        "CP SAT": "CPSAT",
        "ORTOOLS": "CPSAT",
        "OR-TOOLS": "CPSAT",
        "GOOGLE OR-TOOLS CP-SAT": "CPSAT",
        "GOOGLE ORTOOLS CPSAT": "CPSAT",
        "CBC": "CBC",
        "COIN-OR CBC": "CBC",
        "COINOR CBC": "CBC",
        "COIN-OR BRANCH AND CUT": "CBC",
        "COIN-OR BRANCH-AND-CUT": "CBC",
        "GA": "GA",
        "GENETIC ALGORITHM": "GA",
        "GENETIC": "GA",
    }
    return aliases.get(s, s)


def normalize_platform_name(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    raw = str(value).strip()
    s = raw.lower()
    if "renesas" in s or "rcar" in s or "r-car" in s:
        return "Renesas"
    if "nvidia" in s or "jetson" in s or "orin" in s:
        return "NVIDIA"
    if s == "ti" or "tda4" in s or "texas" in s or "texas instruments" in s:
        return "TI"
    return raw if raw else "UNKNOWN"


def parse_taskset_parts(taskset_id: str) -> Dict[str, Optional[str]]:
    """Supports legacy and platform-prefixed identifiers.

    Examples
    --------
    taskset_10_001            -> platform=None, size=10, run=001
    taskset_nvidia_10_001     -> platform=nvidia, size=10, run=001
    taskset_renesas_100_seed3 -> platform=renesas, size=100, run=seed3
    """
    taskset_id = str(taskset_id)

    platform_match = re.match(r"^taskset_([A-Za-z][A-Za-z0-9-]*)_(\d+)_(.+)$", taskset_id)
    if platform_match:
        return {
            "platform_key_from_id": platform_match.group(1),
            "task_count_from_id": platform_match.group(2),
            "taskset_run_id": platform_match.group(3),
        }

    legacy_match = re.match(r"^taskset_(\d+)_(.+)$", taskset_id)
    if legacy_match:
        return {
            "platform_key_from_id": None,
            "task_count_from_id": legacy_match.group(1),
            "taskset_run_id": legacy_match.group(2),
        }

    return {"platform_key_from_id": None, "task_count_from_id": None, "taskset_run_id": None}


def base_workload_key(taskset_id: str, task_count: Optional[int] = None, run_id: Optional[str] = None) -> str:
    parts = parse_taskset_parts(taskset_id)
    count = task_count if task_count is not None else as_int(parts.get("task_count_from_id"))
    run = run_id if run_id is not None else parts.get("taskset_run_id")
    if count is not None and run is not None:
        return f"taskset_{count}_{run}"
    return taskset_id


def parse_solver_from_solution_path(path: Path) -> str:
    name = path.stem
    for suffix in ["_solution", "-solution", ".solution"]:
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return normalize_solver_name(name)


def parse_taskset_id_from_solution_path(path: Path) -> str:
    return path.parent.name


def get_generated_taskset_path(output_root: Path, taskset_id: str) -> Path:
    return output_root / "generated_tasksets" / f"{taskset_id}.json"


# ---------------------------------------------------------------------------
# Manifest loading and solution discovery
# ---------------------------------------------------------------------------


def iter_solution_files(output_root: Path) -> Iterator[Path]:
    solutions_dir = output_root / "solutions"
    if not solutions_dir.exists():
        return iter(())
    # Include solution-like files.  Non-solution status JSONs can be linked from a manifest.
    return iter(sorted(solutions_dir.glob("taskset_*/*_solution.json")))


def find_manifest(output_root: Path) -> Optional[Path]:
    candidates = [
        output_root / "run_manifest.csv",
        output_root / "run_manifest.json",
        output_root / "run_manifest.jsonl",
        output_root / "experiment_manifest.csv",
        output_root / "experiment_manifest.json",
        output_root / "experiment_manifest.jsonl",
        output_root / "manifest.csv",
        output_root / "manifest.json",
        output_root / "manifest.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Manifest does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        data = load_json_any(path)
        if isinstance(data, dict):
            for key in ["runs", "records", "attempts", "results"]:
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError(f"JSON manifest must contain a list or a dict with a list field: {path}")
        return pd.DataFrame(data)
    if suffix == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return pd.DataFrame(rows)
    raise ValueError(f"Unsupported manifest format: {path}")


def build_inferred_manifest(output_root: Path, expected_solvers: Sequence[str]) -> pd.DataFrame:
    """Infer attempted runs from generated tasksets and found solution files.

    This is not as reliable as an explicit manifest because presolve failures that did
    not emit any solution/status file are only represented as missing solver outputs.
    Still, it prevents silent denominator shrinkage when one solver file is absent.
    """
    rows: List[Dict[str, Any]] = []
    generated_dir = output_root / "generated_tasksets"

    taskset_ids: set[str] = set()
    if generated_dir.exists():
        taskset_ids.update(p.stem for p in generated_dir.glob("taskset_*.json"))

    for solution_path in iter_solution_files(output_root):
        taskset_ids.add(parse_taskset_id_from_solution_path(solution_path))

    found_solution_by_key: Dict[Tuple[str, str], Path] = {}
    for solution_path in iter_solution_files(output_root):
        taskset_id = parse_taskset_id_from_solution_path(solution_path)
        solver = parse_solver_from_solution_path(solution_path)
        found_solution_by_key[(taskset_id, solver)] = solution_path

    solvers = [normalize_solver_name(s) for s in expected_solvers]

    for taskset_id in sorted(taskset_ids):
        # If a taskset has a solution from an unexpected solver, include it too.
        observed_solvers = sorted(s for (tid, s), _path in found_solution_by_key.items() if tid == taskset_id)
        all_solvers = ordered_unique(observed_solvers + solvers, solvers)
        for solver in all_solvers:
            path = found_solution_by_key.get((taskset_id, solver))
            rows.append(
                {
                    "taskset_id": taskset_id,
                    "solver": solver,
                    "solution_file": str(path) if path else None,
                    "manifest_status": None if path else "MISSING_SOLUTION",
                    "manifest_source": "inferred",
                }
            )

    return pd.DataFrame(rows)


def normalize_manifest_columns(df: pd.DataFrame, manifest_path: Optional[Path]) -> pd.DataFrame:
    if df.empty:
        return df

    rename_candidates = {
        "task_set_id": "taskset_id",
        "taskset": "taskset_id",
        "instance_id": "taskset_id",
        "instance": "taskset_id",
        "solver_name": "solver",
        "solver_key": "solver",
        "platform_name": "platform",
        "platform_group": "platform",
        "task_size": "task_count",
        "size": "task_count",
        "run": "run_id",
        "seed": "run_id",
        "path": "solution_file",
        "solution_path": "solution_file",
        "result_file": "solution_file",
        "input_file": "input_taskset_file",
        "generated_taskset_file": "input_taskset_file",
        "runtime": "runtime_seconds",
        "wall_time": "runtime_seconds",
        "error": "error_message",
        "message": "error_message",
    }
    renamed = {}
    for col in df.columns:
        canonical = rename_candidates.get(col, col)
        renamed[col] = canonical
    out = df.rename(columns=renamed).copy()

    if "solver" in out.columns:
        out["solver"] = out["solver"].map(normalize_solver_name)
    if "taskset_id" in out.columns:
        out["taskset_id"] = out["taskset_id"].astype(str)
    if "manifest_source" not in out.columns:
        out["manifest_source"] = str(manifest_path) if manifest_path is not None else "inferred"

    return out


# ---------------------------------------------------------------------------
# Input taskset parsing
# ---------------------------------------------------------------------------


def coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    return []


def id_as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def extract_task_id(obj: Mapping[str, Any]) -> Optional[str]:
    return id_as_str(
        first_key(
            obj,
            [
                "id",
                "task_id",
                "taskId",
                "taskTemplateId",
                "task_template_id",
                "runnable_id",
                "runnableId",
                "name",
            ],
        )
    )


def extract_dependencies(obj: Mapping[str, Any]) -> List[str]:
    raw = first_key(
        obj,
        [
            "dependencies",
            "predecessors",
            "dependsOn",
            "depends_on",
            "inputDependencies",
            "input_dependencies",
        ],
        [],
    )
    deps: List[str] = []
    for dep in coerce_list(raw):
        if isinstance(dep, Mapping):
            candidate = first_key(dep, ["id", "task_id", "taskId", "source", "from", "predecessor", "predecessor_id"])
        else:
            candidate = dep
        dep_id = id_as_str(candidate)
        if dep_id is not None:
            deps.append(dep_id)
    return deps


def parse_tasks(raw: Mapping[str, Any]) -> Dict[str, TaskInfo]:
    raw_tasks = first_key(raw, ["tasks", "runnables", "taskTemplates", "task_templates", "softwareTasks"], [])
    tasks: Dict[str, TaskInfo] = {}
    for idx, item in enumerate(coerce_list(raw_tasks)):
        if not isinstance(item, Mapping):
            continue
        task_id = extract_task_id(item) or f"task_{idx}"
        wcet = as_float(first_key(item, ["wcet", "WCET", "baseWcet", "base_wcet", "duration", "executionTime", "execution_time"]))
        period = as_float(first_key(item, ["period", "activationPeriod", "activation_period", "period_us", "periodUs"]))
        memory = as_float(first_key(item, ["memoryUsageKB", "memory_usage_kb", "memoryKB", "memory_kb", "memory", "memoryDemandKB"])) or 0.0
        tasks[task_id] = TaskInfo(
            task_id=task_id,
            name=id_as_str(first_key(item, ["name", "label"])) if first_key(item, ["name", "label"]) is not None else None,
            period=period,
            wcet=wcet,
            memory_kb=memory,
            required_domain=id_as_str(first_key(item, ["requiredExecutionDomain", "required_domain", "executionDomain", "execution_domain", "domain"])),
            task_type=id_as_str(first_key(item, ["taskType", "task_type", "type"])),
            dependencies=extract_dependencies(item),
        )

    # Also support top-level dependency arrays with edges.
    raw_edges = first_key(raw, ["dependencies", "edges", "dependencyEdges", "taskDependencies"], [])
    for edge in coerce_list(raw_edges):
        if not isinstance(edge, Mapping):
            continue
        src = id_as_str(first_key(edge, ["source", "from", "predecessor", "predecessor_id", "src"]));
        dst = id_as_str(first_key(edge, ["target", "to", "successor", "successor_id", "dst"]));
        if src and dst:
            if dst not in tasks:
                tasks[dst] = TaskInfo(task_id=dst)
            if src not in tasks[dst].dependencies:
                tasks[dst].dependencies.append(src)

    return tasks


def parse_platform(raw: Mapping[str, Any]) -> Tuple[Dict[str, CoreInfo], Dict[str, ClusterInfo], Optional[str], str]:
    platform = raw.get("platform") if isinstance(raw.get("platform"), Mapping) else raw
    assert isinstance(platform, Mapping)

    platform_name = id_as_str(first_key(platform, ["name", "platformName", "platform_name", "id"]))
    platform_group = normalize_platform_name(platform_name)

    cores: Dict[str, CoreInfo] = {}
    clusters: Dict[str, ClusterInfo] = {}

    # Cluster templates/instances may contain nested cores.
    raw_clusters = first_key(platform, ["clusters", "clusterTemplates", "cluster_templates"], [])
    for cidx, cobj in enumerate(coerce_list(raw_clusters)):
        if not isinstance(cobj, Mapping):
            continue
        count = as_int(first_key(cobj, ["count", "numInstances", "instances"])) or 1
        base_cluster_id = id_as_str(first_key(cobj, ["id", "cluster_id", "clusterId", "name"])) or f"cluster_{cidx}"
        cluster_mem = as_float(first_key(cobj, ["memoryBudgetKB", "memory_budget_kb", "memoryKB", "memory_kb", "memoryBudget", "localMemoryKB"]))
        for rep in range(count):
            cluster_id = base_cluster_id if count == 1 else f"{base_cluster_id}_{rep}"
            clusters[cluster_id] = ClusterInfo(
                cluster_id=cluster_id,
                name=id_as_str(first_key(cobj, ["name", "label"])) or cluster_id,
                memory_budget_kb=cluster_mem,
            )

            raw_cores = first_key(cobj, ["cores", "coreTemplates", "core_templates", "processingElements"], [])
            for kidx, kobj in enumerate(coerce_list(raw_cores)):
                if not isinstance(kobj, Mapping):
                    continue
                core_count = as_int(first_key(kobj, ["count", "numInstances", "instances"])) or 1
                base_core_id = id_as_str(first_key(kobj, ["id", "core_id", "coreId", "name"])) or f"{cluster_id}_core_{kidx}"
                core_mem = as_float(first_key(kobj, ["memoryBudgetKB", "memory_budget_kb", "memoryKB", "memory_kb", "memoryBudget", "localMemoryKB"]))
                scale = as_float(first_key(kobj, ["wcetScalingFactor", "wcet_scale", "wcetScale", "speedFactor", "scalingFactor"]))
                for crep in range(core_count):
                    core_id = base_core_id if core_count == 1 and count == 1 else f"{base_core_id}_{rep}_{crep}"
                    cores[core_id] = CoreInfo(
                        core_id=core_id,
                        cluster_id=cluster_id,
                        name=id_as_str(first_key(kobj, ["name", "label"])) or core_id,
                        memory_budget_kb=core_mem,
                        wcet_scale=scale,
                    )

    # Some JSON files may keep cores as a separate top-level/platform list.
    raw_cores = first_key(platform, ["cores", "coreTemplates", "core_templates", "processingElements"], [])
    for idx, cobj in enumerate(coerce_list(raw_cores)):
        if not isinstance(cobj, Mapping):
            continue
        count = as_int(first_key(cobj, ["count", "numInstances", "instances"])) or 1
        base_core_id = id_as_str(first_key(cobj, ["id", "core_id", "coreId", "name"])) or f"core_{idx}"
        cluster_id = id_as_str(first_key(cobj, ["cluster", "cluster_id", "clusterId", "clusterName"]))
        if cluster_id and cluster_id not in clusters:
            clusters[cluster_id] = ClusterInfo(cluster_id=cluster_id, name=cluster_id)
        core_mem = as_float(first_key(cobj, ["memoryBudgetKB", "memory_budget_kb", "memoryKB", "memory_kb", "memoryBudget", "localMemoryKB"]))
        scale = as_float(first_key(cobj, ["wcetScalingFactor", "wcet_scale", "wcetScale", "speedFactor", "scalingFactor"]))
        for rep in range(count):
            core_id = base_core_id if count == 1 else f"{base_core_id}_{rep}"
            cores[core_id] = CoreInfo(core_id=core_id, cluster_id=cluster_id, name=core_id, memory_budget_kb=core_mem, wcet_scale=scale)

    return cores, clusters, platform_name, platform_group


def extract_chain_tasks(chain_obj: Mapping[str, Any]) -> List[str]:
    raw = first_key(
        chain_obj,
        [
            "tasks",
            "taskIds",
            "task_ids",
            "runnables",
            "runnableIds",
            "members",
            "sequence",
            "taskSequence",
            "chain",
        ],
        [],
    )
    task_ids: List[str] = []
    for elem in coerce_list(raw):
        if isinstance(elem, Mapping):
            candidate = extract_task_id(elem) or id_as_str(first_key(elem, ["task", "task_id", "taskId", "id"]))
        else:
            candidate = id_as_str(elem)
        if candidate:
            task_ids.append(candidate)
    return task_ids


def infer_chains_from_dependencies(tasks: Dict[str, TaskInfo]) -> List[ChainInfo]:
    successors: Dict[str, List[str]] = defaultdict(list)
    indegree: Counter[str] = Counter()
    for tid in tasks:
        indegree[tid] += 0
    for dst, task in tasks.items():
        for src in task.dependencies:
            if src in tasks:
                successors[src].append(dst)
                indegree[dst] += 1

    chains: List[ChainInfo] = []
    seen_edges: set[Tuple[str, str]] = set()
    roots = [tid for tid in tasks if indegree[tid] == 0 and successors.get(tid)]

    def add_path(path: List[str]) -> None:
        if len(path) >= 2:
            cid = f"inferred_chain_{len(chains) + 1:04d}"
            root_period = tasks.get(path[0]).period if tasks.get(path[0]) else None
            chains.append(ChainInfo(chain_id=cid, task_ids=path, period=root_period, source="inferred_dependencies"))

    # Follow maximal non-branching paths.  Branches are represented as separate paths.
    for root in roots:
        stack: List[Tuple[str, List[str]]] = [(root, [root])]
        while stack:
            node, path = stack.pop()
            succs = [s for s in successors.get(node, []) if s not in path]
            if not succs:
                add_path(path)
                continue
            if len(succs) == 1:
                edge = (node, succs[0])
                seen_edges.add(edge)
                stack.append((succs[0], path + [succs[0]]))
            else:
                for succ in succs:
                    seen_edges.add((node, succ))
                    stack.append((succ, path + [succ]))

    # Cover remaining edges in cyclic/ambiguous cases by single-edge chains.
    for src, succs in successors.items():
        for dst in succs:
            if (src, dst) not in seen_edges:
                add_path([src, dst])

    return chains


def parse_chains(raw: Mapping[str, Any], tasks: Dict[str, TaskInfo]) -> List[ChainInfo]:
    raw_chains = first_key(raw, ["taskChains", "task_chains", "chains", "causeEffectChains", "cause_effect_chains"], [])
    chains: List[ChainInfo] = []
    for idx, chain_obj in enumerate(coerce_list(raw_chains)):
        if not isinstance(chain_obj, Mapping):
            continue
        task_ids = extract_chain_tasks(chain_obj)
        if len(task_ids) < 2:
            continue
        chain_id = id_as_str(first_key(chain_obj, ["id", "chain_id", "chainId", "name"])) or f"chain_{idx + 1:04d}"
        deadline = as_float(first_key(chain_obj, ["deadline", "maxLatency", "max_latency", "latencyBound", "latency_bound", "endToEndDeadline"]))
        period = as_float(first_key(chain_obj, ["period", "activationPeriod", "activation_period"]))
        release_offset = as_float(first_key(chain_obj, ["releaseOffset", "release_offset", "offset"]))
        chains.append(ChainInfo(chain_id=chain_id, task_ids=task_ids, deadline=deadline, period=period, release_offset=release_offset, source="explicit"))

    if chains:
        return chains
    return infer_chains_from_dependencies(tasks)


def extract_config(raw: Mapping[str, Any]) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    for source in [raw.get("config"), raw.get("configuration"), raw.get("solverConfig"), raw.get("optimizationConfig")]:
        if isinstance(source, Mapping):
            config.update(source)
    return config


def extract_input_metadata(output_root: Path, taskset_id: str, explicit_input_file: Optional[Any] = None) -> InputMetadata:
    parts = parse_taskset_parts(taskset_id)
    task_count_from_id = as_int(parts.get("task_count_from_id"))
    run_id = parts.get("taskset_run_id")
    platform_key_from_id = parts.get("platform_key_from_id")

    path: Optional[Path]
    if explicit_input_file and str(explicit_input_file).strip():
        candidate = Path(str(explicit_input_file))
        path = candidate if candidate.is_absolute() else output_root / candidate
    else:
        path = get_generated_taskset_path(output_root, taskset_id)

    metadata = InputMetadata(
        path=path,
        exists=bool(path and path.exists()),
        taskset_id=taskset_id,
        task_count_from_id=task_count_from_id,
        run_id=run_id,
        platform_key_from_id=platform_key_from_id,
        base_workload_key=base_workload_key(taskset_id, task_count_from_id, run_id),
    )

    if not path or not path.exists():
        metadata.platform_group = normalize_platform_name(platform_key_from_id)
        return metadata

    try:
        raw = load_json(path)
    except Exception:
        metadata.platform_group = normalize_platform_name(platform_key_from_id)
        return metadata

    tasks = parse_tasks(raw)
    cores, clusters, platform_name, platform_group = parse_platform(raw)
    chains = parse_chains(raw, tasks)
    config = extract_config(raw)

    dependency_count = sum(len(t.dependencies) for t in tasks.values())
    metadata.raw = raw
    metadata.tasks = tasks
    metadata.cores = cores
    metadata.clusters = clusters
    metadata.chains = chains
    metadata.config = config
    metadata.task_count = len(tasks) if tasks else task_count_from_id
    metadata.platform_name = platform_name or platform_key_from_id
    metadata.platform_group = platform_group if platform_group != "UNKNOWN" else normalize_platform_name(platform_key_from_id)
    metadata.num_cores = len(cores) if cores else as_int(first_present(raw, [["platform", "numCores"], ["numCores"]]))
    metadata.num_clusters = len(clusters) if clusters else as_int(first_present(raw, [["platform", "numClusters"], ["numClusters"]]))
    metadata.total_task_memory_kb = sum(t.memory_kb for t in tasks.values()) if tasks else None
    metadata.total_task_wcet = sum(t.wcet or 0.0 for t in tasks.values()) if tasks else None
    metadata.dependency_count = dependency_count
    metadata.base_workload_key = base_workload_key(taskset_id, metadata.task_count or task_count_from_id, run_id)
    return metadata


# ---------------------------------------------------------------------------
# Status and runtime extraction
# ---------------------------------------------------------------------------


def extract_runtime_seconds(result: Mapping[str, Any], manifest_row: Optional[Mapping[str, Any]] = None) -> Optional[float]:
    candidates: List[Any] = []
    if manifest_row is not None:
        candidates.append(manifest_row.get("runtime_seconds"))
    candidates.extend(
        [
            result.get("runtime_seconds"),
            result.get("runtime"),
            result.get("wall_time"),
            get_nested(result, ["metadata", "runtime_seconds"]),
            get_nested(result, ["metadata", "wall_time"]),
            get_nested(result, ["metadata", "solve_time"]),
            get_nested(result, ["metadata", "solver_time"]),
            get_nested(result, ["summary", "runtime_seconds"]),
        ]
    )
    for candidate in candidates:
        value = as_float(candidate)
        if value is not None:
            return value
    return None


def raw_status_text(result: Mapping[str, Any], manifest_row: Optional[Mapping[str, Any]] = None) -> str:
    candidates: List[Any] = []
    if manifest_row is not None:
        candidates.extend([manifest_row.get("manifest_status"), manifest_row.get("status")])
    candidates.extend(
        [
            result.get("status"),
            result.get("solver_status"),
            result.get("termination_status"),
            get_nested(result, ["metadata", "status"]),
            get_nested(result, ["summary", "status"]),
            result.get("error"),
            result.get("message"),
        ]
    )
    for candidate in candidates:
        s = normalized_string(candidate)
        if s:
            return s
    return ""


def schedule_list(result: Mapping[str, Any]) -> List[Any]:
    for key in ["schedule", "jobs", "scheduled_jobs", "jobSchedule", "job_schedule"]:
        value = result.get(key)
        if isinstance(value, list):
            return value
    summary_schedule = get_nested(result, ["summary", "schedule"])
    if isinstance(summary_schedule, list):
        return summary_schedule
    return []


def explicit_feasible_value(result: Mapping[str, Any], manifest_row: Optional[Mapping[str, Any]] = None) -> Optional[bool]:
    candidates: List[Any] = []
    if manifest_row is not None:
        candidates.append(manifest_row.get("feasible"))
    candidates.extend([result.get("feasible"), get_nested(result, ["summary", "feasible"]), get_nested(result, ["metadata", "feasible"])])
    for candidate in candidates:
        parsed = bool_like(candidate)
        if parsed is not None:
            return parsed
    return None


def normalize_run_status(
    result: Mapping[str, Any],
    manifest_row: Optional[Mapping[str, Any]] = None,
    runtime_seconds: Optional[float] = None,
    solver_timeout: Optional[float] = None,
) -> str:
    text = raw_status_text(result, manifest_row).strip()
    s = text.upper().replace("-", "_").replace(" ", "_")
    explicit_feasible = explicit_feasible_value(result, manifest_row)
    has_schedule = len(schedule_list(result)) > 0

    if s in {"MISSING_SOLUTION", "MISSING", "NO_SOLUTION_FILE"}:
        return "MISSING_SOLUTION"
    if "PRESOLVE" in s and any(token in s for token in ["FAIL", "FAILED", "REJECT", "INFEAS", "ERROR"]):
        return "PRESOLVE_REJECTED"
    if "TIME" in s and any(token in s for token in ["LIMIT", "OUT", "TIMEOUT"]):
        if explicit_feasible is True or has_schedule:
            return "TIMEOUT_FEASIBLE"
        return "TIMEOUT_NO_SOLUTION"
    if "OPTIMAL" in s:
        return "OPTIMAL"
    if "FEASIBLE" in s and "INFEASIBLE" not in s:
        return "FEASIBLE"
    if "INFEASIBLE" in s or "NO_FEASIBLE" in s:
        return "INFEASIBLE"
    if "ERROR" in s or "EXCEPTION" in s or "FAILED" in s or "FAILURE" in s:
        return "ERROR"

    if explicit_feasible is True:
        # A run may have hit a timeout but still produced an incumbent.
        if solver_timeout is not None and runtime_seconds is not None and runtime_seconds >= 0.995 * solver_timeout:
            return "TIMEOUT_FEASIBLE"
        return "FEASIBLE"
    if explicit_feasible is False:
        if solver_timeout is not None and runtime_seconds is not None and runtime_seconds >= 0.995 * solver_timeout:
            return "TIMEOUT_NO_SOLUTION"
        return "INFEASIBLE"
    if has_schedule:
        if solver_timeout is not None and runtime_seconds is not None and runtime_seconds >= 0.995 * solver_timeout:
            return "TIMEOUT_FEASIBLE"
        return "FEASIBLE"

    if manifest_row is not None and normalized_string(manifest_row.get("solution_file")) == "":
        return "MISSING_SOLUTION"

    return "UNKNOWN"


def status_is_feasible(status: str) -> bool:
    return status in {"OPTIMAL", "FEASIBLE", "TIMEOUT_FEASIBLE"}


def status_is_attempted(status: str) -> bool:
    return status != "MISSING_SOLUTION"


def status_is_timeout(status: str) -> bool:
    return status in {"TIMEOUT_FEASIBLE", "TIMEOUT_NO_SOLUTION"}


# ---------------------------------------------------------------------------
# Objective and component extraction
# ---------------------------------------------------------------------------


def extract_numeric_candidate(result: Mapping[str, Any], paths: Sequence[Sequence[str]]) -> Optional[float]:
    for path in paths:
        value = get_nested(result, path)
        parsed = as_float(value)
        if parsed is not None:
            return parsed
    return None


def extract_objective(result: Mapping[str, Any]) -> Optional[float]:
    return extract_numeric_candidate(
        result,
        [
            ["objective"],
            ["objective_value"],
            ["total_objective"],
            ["summary", "objective"],
            ["metadata", "objective"],
            ["metadata", "fitness"],
        ],
    )


def extract_best_bound(result: Mapping[str, Any], objective: Optional[float]) -> Optional[float]:
    raw_bound = extract_numeric_candidate(
        result,
        [
            ["best_objective_bound"],
            ["objective_bound"],
            ["metadata", "best_objective_bound"],
            ["metadata", "objective_bound"],
            ["summary", "best_objective_bound"],
        ],
    )
    if raw_bound is None:
        return None

    time_scale = extract_numeric_candidate(result, [["metadata", "time_scale"], ["time_scale"]])
    if objective is not None and time_scale not in (None, 0):
        scaled = raw_bound / time_scale
        if abs(scaled - objective) < abs(raw_bound - objective):
            return scaled
    return raw_bound


def extract_config_scales(result: Mapping[str, Any], input_meta: InputMetadata) -> Dict[str, float]:
    combined: Dict[str, Any] = {}
    combined.update(input_meta.config or {})
    for source in [result.get("config"), result.get("configuration"), result.get("solver_config"), result.get("metadata")]:
        if isinstance(source, Mapping):
            combined.update(source)

    def get_value(keys: Sequence[str], default: float) -> float:
        for key in keys:
            value = combined.get(key)
            parsed = as_float(value)
            if parsed is not None:
                return parsed
        # Nested memoryPenaltyScale can appear in camelCase/lowercase variants.
        for parent in ["memoryPenaltyScale", "memory_penalty_scale", "memoryPenalty", "memory_penalty"]:
            nested = combined.get(parent)
            if isinstance(nested, Mapping):
                for key in keys:
                    parsed = as_float(nested.get(key))
                    if parsed is not None:
                        return parsed
        for parent in ["communicationPenalty", "communication_penalty", "communication", "commPenalty", "comm_penalty"]:
            nested = combined.get(parent)
            if isinstance(nested, Mapping):
                for key in keys:
                    parsed = as_float(nested.get(key))
                    if parsed is not None:
                        return parsed
        return default

    return {
        "core_overflow_scale": get_value(["coreOverflowScale", "core_overflow_scale", "core", "coreMemoryScale"], DEFAULT_CORE_OVERFLOW_SCALE),
        "cluster_overflow_scale": get_value(["clusterOverflowScale", "cluster_overflow_scale", "cluster", "clusterMemoryScale"], DEFAULT_CLUSTER_OVERFLOW_SCALE),
        "comm_same_core": get_value(["intraCorePenalty", "sameCorePenalty", "intra_core", "same_core", "intraCoreCommunicationPenalty"], DEFAULT_COMM_SAME_CORE),
        "comm_same_cluster": get_value(["interCorePenalty", "sameClusterPenalty", "inter_core", "same_cluster", "interCoreCommunicationPenalty"], DEFAULT_COMM_SAME_CLUSTER),
        "comm_inter_cluster": get_value(["interClusterPenalty", "inter_cluster", "interClusterCommunicationPenalty"], DEFAULT_COMM_INTER_CLUSTER),
    }


def sum_resource(entries: Any, key: str) -> float:
    if not isinstance(entries, list):
        return 0.0
    total = 0.0
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        total += as_float(entry.get(key)) or 0.0
    return total


def count_resource_violations(entries: Any) -> int:
    if not isinstance(entries, list):
        return 0
    return sum(1 for entry in entries if isinstance(entry, Mapping) and (as_float(entry.get("overflow")) or 0.0) > 0)


def parse_job(job: Mapping[str, Any], input_meta: InputMetadata) -> Optional[JobInfo]:
    job_id = id_as_str(first_key(job, ["job_id", "jobId", "id", "name"]))
    if not job_id:
        return None
    task_id = id_as_str(first_key(job, ["task_id", "taskId", "taskTemplateId", "task_template_id", "runnable_id", "runnableId", "template_id", "templateId", "task"]))
    start = as_float(first_key(job, ["start_time", "start", "startTime", "scheduled_start", "scheduledStart"]))
    finish = as_float(first_key(job, ["finish_time", "finish", "finishTime", "end", "end_time", "endTime", "scheduled_finish", "scheduledFinish"]))
    duration = as_float(first_key(job, ["scheduled_duration", "duration", "execution_time", "executionTime"]))
    if duration is None and start is not None and finish is not None:
        duration = max(0.0, finish - start)
    core_id = id_as_str(first_key(job, ["assigned_core", "assignedCore", "core_id", "coreId", "core", "processor", "pe"]))
    cluster_id = id_as_str(first_key(job, ["assigned_cluster", "assignedCluster", "cluster_id", "clusterId", "cluster"]))
    if cluster_id is None and core_id in input_meta.cores:
        cluster_id = input_meta.cores[core_id].cluster_id
    release = as_float(first_key(job, ["release_time", "release", "releaseTime", "absolute_release", "absoluteRelease"]))
    deadline = as_float(first_key(job, ["absolute_deadline", "deadline", "deadline_time", "deadlineTime", "absDeadline"]))
    preds_raw = first_key(job, ["predecessors", "predecessor_jobs", "predecessorJobs", "dependencies"], [])
    preds: List[str] = []
    for pred in coerce_list(preds_raw):
        if isinstance(pred, Mapping):
            pred_id = id_as_str(first_key(pred, ["job_id", "jobId", "id", "predecessor", "source", "from"]))
        else:
            pred_id = id_as_str(pred)
        if pred_id:
            preds.append(pred_id)
    return JobInfo(job_id=job_id, task_id=task_id, start=start, finish=finish, duration=duration, core_id=core_id, cluster_id=cluster_id, release=release, deadline=deadline, predecessors=preds)


def parse_schedule(result: Mapping[str, Any], input_meta: InputMetadata) -> List[JobInfo]:
    jobs: List[JobInfo] = []
    for raw_job in schedule_list(result):
        if isinstance(raw_job, Mapping):
            parsed = parse_job(raw_job, input_meta)
            if parsed is not None:
                jobs.append(parsed)
    return jobs


def derive_task_assignment(jobs: Sequence[JobInfo], result: Mapping[str, Any], input_meta: InputMetadata) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Return task_id -> (core_id, cluster_id).  Schedule-derived assignment wins."""
    assignment: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    # Common explicit assignment formats.
    raw_assignments = first_key(result, ["assignments", "allocation", "task_allocation", "taskAllocation", "mapping", "task_mapping"], None)
    if isinstance(raw_assignments, Mapping):
        for task_id_raw, value in raw_assignments.items():
            task_id = id_as_str(task_id_raw)
            if not task_id:
                continue
            if isinstance(value, Mapping):
                core_id = id_as_str(first_key(value, ["core", "core_id", "coreId", "assigned_core", "assignedCore"]))
                cluster_id = id_as_str(first_key(value, ["cluster", "cluster_id", "clusterId", "assigned_cluster", "assignedCluster"]))
            else:
                core_id = id_as_str(value)
                cluster_id = None
            if cluster_id is None and core_id in input_meta.cores:
                cluster_id = input_meta.cores[core_id].cluster_id
            assignment[task_id] = (core_id, cluster_id)
    elif isinstance(raw_assignments, list):
        for item in raw_assignments:
            if not isinstance(item, Mapping):
                continue
            task_id = id_as_str(first_key(item, ["task", "task_id", "taskId", "taskTemplateId", "id"]))
            if not task_id:
                continue
            core_id = id_as_str(first_key(item, ["core", "core_id", "coreId", "assigned_core", "assignedCore"]))
            cluster_id = id_as_str(first_key(item, ["cluster", "cluster_id", "clusterId", "assigned_cluster", "assignedCluster"]))
            if cluster_id is None and core_id in input_meta.cores:
                cluster_id = input_meta.cores[core_id].cluster_id
            assignment[task_id] = (core_id, cluster_id)

    # Schedule-derived assignment is more concrete and should overwrite ambiguous explicit data.
    for job in jobs:
        if job.task_id is None:
            continue
        core_id = job.core_id
        cluster_id = job.cluster_id
        if cluster_id is None and core_id in input_meta.cores:
            cluster_id = input_meta.cores[core_id].cluster_id
        if core_id is not None or cluster_id is not None:
            assignment[job.task_id] = (core_id, cluster_id)

    return assignment


def reconstruct_memory_usage(input_meta: InputMetadata, task_assignment: Mapping[str, Tuple[Optional[str], Optional[str]]]) -> Dict[str, Any]:
    core_used: Counter[str] = Counter()
    cluster_used: Counter[str] = Counter()

    for task_id, task in input_meta.tasks.items():
        core_id, cluster_id = task_assignment.get(task_id, (None, None))
        if core_id:
            core_used[core_id] += task.memory_kb
            if cluster_id is None and core_id in input_meta.cores:
                cluster_id = input_meta.cores[core_id].cluster_id
        if cluster_id:
            cluster_used[cluster_id] += task.memory_kb

    core_overflow = 0.0
    core_nodes = 0
    for core_id, used in core_used.items():
        budget = input_meta.cores.get(core_id).memory_budget_kb if core_id in input_meta.cores else None
        if budget is not None:
            overflow = max(0.0, used - budget)
            core_overflow += overflow
            if overflow > 0:
                core_nodes += 1

    cluster_overflow = 0.0
    cluster_nodes = 0
    for cluster_id, used in cluster_used.items():
        budget = input_meta.clusters.get(cluster_id).memory_budget_kb if cluster_id in input_meta.clusters else None
        if budget is not None:
            overflow = max(0.0, used - budget)
            cluster_overflow += overflow
            if overflow > 0:
                cluster_nodes += 1

    return {
        "core_memory_used_kb_reconstructed": float(sum(core_used.values())),
        "cluster_memory_used_kb_reconstructed": float(sum(cluster_used.values())),
        "core_memory_overflow_kb_reconstructed": core_overflow,
        "cluster_memory_overflow_kb_reconstructed": cluster_overflow,
        "core_memory_overflow_nodes_reconstructed": core_nodes,
        "cluster_memory_overflow_nodes_reconstructed": cluster_nodes,
    }


def extract_memory_metrics(result: Mapping[str, Any], input_meta: InputMetadata, task_assignment: Mapping[str, Tuple[Optional[str], Optional[str]]]) -> Dict[str, Any]:
    core_memory = get_nested(result, ["resource_usage", "core_memory"], [])
    cluster_memory = get_nested(result, ["resource_usage", "cluster_memory"], [])
    if not isinstance(core_memory, list):
        core_memory = get_nested(result, ["resourceUsage", "coreMemory"], [])
    if not isinstance(cluster_memory, list):
        cluster_memory = get_nested(result, ["resourceUsage", "clusterMemory"], [])

    reconstructed = reconstruct_memory_usage(input_meta, task_assignment)

    core_used = sum_resource(core_memory, "used")
    cluster_used = sum_resource(cluster_memory, "used")
    core_overflow = sum_resource(core_memory, "overflow")
    cluster_overflow = sum_resource(cluster_memory, "overflow")

    # Fall back to reconstruction only when solver output does not expose resource usage.
    if core_used == 0.0 and core_overflow == 0.0 and reconstructed["core_memory_used_kb_reconstructed"] > 0:
        core_used = reconstructed["core_memory_used_kb_reconstructed"]
        core_overflow = reconstructed["core_memory_overflow_kb_reconstructed"]
        core_nodes = reconstructed["core_memory_overflow_nodes_reconstructed"]
    else:
        core_nodes = count_resource_violations(core_memory)

    if cluster_used == 0.0 and cluster_overflow == 0.0 and reconstructed["cluster_memory_used_kb_reconstructed"] > 0:
        cluster_used = reconstructed["cluster_memory_used_kb_reconstructed"]
        cluster_overflow = reconstructed["cluster_memory_overflow_kb_reconstructed"]
        cluster_nodes = reconstructed["cluster_memory_overflow_nodes_reconstructed"]
    else:
        cluster_nodes = count_resource_violations(cluster_memory)

    return {
        "core_memory_used_kb": core_used,
        "cluster_memory_used_kb": cluster_used,
        "core_memory_overflow_kb": core_overflow,
        "cluster_memory_overflow_kb": cluster_overflow,
        "total_memory_overflow_kb": core_overflow + cluster_overflow,
        "core_memory_overflow_nodes": core_nodes,
        "cluster_memory_overflow_nodes": cluster_nodes,
        **reconstructed,
    }


def communication_penalty_between(
    pred_core: Optional[str],
    pred_cluster: Optional[str],
    succ_core: Optional[str],
    succ_cluster: Optional[str],
    scales: Mapping[str, float],
) -> Optional[float]:
    if pred_core is None or succ_core is None:
        return None
    if pred_core == succ_core:
        return scales["comm_same_core"]
    if pred_cluster is not None and succ_cluster is not None and pred_cluster == succ_cluster:
        return scales["comm_same_cluster"]
    return scales["comm_inter_cluster"]


def reconstruct_communication_from_tasks(input_meta: InputMetadata, task_assignment: Mapping[str, Tuple[Optional[str], Optional[str]]], scales: Mapping[str, float]) -> Dict[str, Any]:
    same_core_edges = 0
    same_cluster_edges = 0
    inter_cluster_edges = 0
    unknown_edges = 0
    total_penalty = 0.0
    edge_count = 0

    for succ_id, succ_task in input_meta.tasks.items():
        succ_core, succ_cluster = task_assignment.get(succ_id, (None, None))
        for pred_id in succ_task.dependencies:
            pred_core, pred_cluster = task_assignment.get(pred_id, (None, None))
            penalty = communication_penalty_between(pred_core, pred_cluster, succ_core, succ_cluster, scales)
            edge_count += 1
            if penalty is None:
                unknown_edges += 1
                continue
            total_penalty += penalty
            if pred_core == succ_core:
                same_core_edges += 1
            elif pred_cluster is not None and succ_cluster is not None and pred_cluster == succ_cluster:
                same_cluster_edges += 1
            else:
                inter_cluster_edges += 1

    return {
        "communication_penalty_reconstructed": total_penalty,
        "communication_edge_count": edge_count,
        "communication_same_core_edges": same_core_edges,
        "communication_same_cluster_edges": same_cluster_edges,
        "communication_inter_cluster_edges": inter_cluster_edges,
        "communication_unknown_edges": unknown_edges,
        "communication_same_core_rate": safe_divide(same_core_edges, edge_count) if edge_count else None,
        "communication_same_cluster_rate": safe_divide(same_cluster_edges, edge_count) if edge_count else None,
        "communication_inter_cluster_rate": safe_divide(inter_cluster_edges, edge_count) if edge_count else None,
    }


def reconstruct_communication_from_jobs(jobs: Sequence[JobInfo], scales: Mapping[str, float]) -> Dict[str, Any]:
    by_id = {job.job_id: job for job in jobs}
    same_core_edges = 0
    same_cluster_edges = 0
    inter_cluster_edges = 0
    unknown_edges = 0
    total_penalty = 0.0
    edge_count = 0

    for job in jobs:
        for pred_id in job.predecessors:
            pred = by_id.get(pred_id)
            if pred is None:
                continue
            edge_count += 1
            penalty = communication_penalty_between(pred.core_id, pred.cluster_id, job.core_id, job.cluster_id, scales)
            if penalty is None:
                unknown_edges += 1
                continue
            total_penalty += penalty
            if pred.core_id == job.core_id:
                same_core_edges += 1
            elif pred.cluster_id is not None and job.cluster_id is not None and pred.cluster_id == job.cluster_id:
                same_cluster_edges += 1
            else:
                inter_cluster_edges += 1

    return {
        "communication_penalty_reconstructed": total_penalty,
        "communication_edge_count": edge_count,
        "communication_same_core_edges": same_core_edges,
        "communication_same_cluster_edges": same_cluster_edges,
        "communication_inter_cluster_edges": inter_cluster_edges,
        "communication_unknown_edges": unknown_edges,
        "communication_same_core_rate": safe_divide(same_core_edges, edge_count) if edge_count else None,
        "communication_same_cluster_rate": safe_divide(same_cluster_edges, edge_count) if edge_count else None,
        "communication_inter_cluster_rate": safe_divide(inter_cluster_edges, edge_count) if edge_count else None,
    }


def extract_communication_metrics(result: Mapping[str, Any], input_meta: InputMetadata, jobs: Sequence[JobInfo], task_assignment: Mapping[str, Tuple[Optional[str], Optional[str]]], scales: Mapping[str, float]) -> Dict[str, Any]:
    explicit = extract_numeric_candidate(
        result,
        [
            ["communication_penalty"],
            ["communication_cost"],
            ["comm_cost"],
            ["summary", "communication_penalty"],
            ["summary", "communication_cost"],
            ["metadata", "communication_penalty"],
            ["metadata", "communication_cost"],
            ["metadata", "comm_cost"],
            ["objective_components", "communication_penalty"],
            ["objectiveComponents", "communicationPenalty"],
        ],
    )
    by_tasks = reconstruct_communication_from_tasks(input_meta, task_assignment, scales)
    by_jobs = reconstruct_communication_from_jobs(jobs, scales)

    # Prefer task-template reconstruction because the formal objective is usually at
    # template-dependency level.  If there are no template edges, use job predecessor edges.
    reconstructed = by_tasks if by_tasks["communication_edge_count"] else by_jobs

    return {
        "communication_penalty_explicit": explicit,
        "communication_penalty": explicit if explicit is not None else reconstructed["communication_penalty_reconstructed"],
        "communication_penalty_source": "explicit" if explicit is not None else ("task_dependencies" if reconstructed is by_tasks else "job_dependencies"),
        **reconstructed,
    }


def extract_deadline_violation(result: Mapping[str, Any], jobs: Sequence[JobInfo]) -> Optional[float]:
    explicit = extract_numeric_candidate(
        result,
        [
            ["deadline_violation"],
            ["deadline_violation_total"],
            ["summary", "deadline_violation"],
            ["metadata", "deadline_violation"],
            ["metadata", "strict_chain_violation"],
            ["metadata", "constraint_violation"],
        ],
    )
    if explicit is not None:
        return explicit

    seen = False
    total_lateness = 0.0
    for job in jobs:
        if job.finish is None or job.deadline is None:
            continue
        seen = True
        total_lateness += max(0.0, job.finish - job.deadline)
    return total_lateness if seen else None


def extract_makespan(result: Mapping[str, Any], jobs: Sequence[JobInfo]) -> Optional[float]:
    explicit = extract_numeric_candidate(result, [["makespan"], ["summary", "makespan"], ["metadata", "makespan"]])
    if explicit is not None:
        return explicit
    finishes = [job.finish for job in jobs if job.finish is not None]
    if finishes:
        return max(finishes)
    return None


def extract_compute_pressure(jobs: Sequence[JobInfo], makespan: Optional[float], core_count: Optional[int]) -> Dict[str, Any]:
    durations = [(job.core_id, job.duration) for job in jobs if job.duration is not None]
    total_duration = sum(d for _core, d in durations)
    by_core: Counter[str] = Counter()
    for core_id, duration in durations:
        if core_id is not None:
            by_core[core_id] += duration or 0.0

    if makespan is None or makespan <= 0:
        return {
            "total_scheduled_duration": total_duration if durations else None,
            "avg_core_load_fraction": None,
            "max_core_load_fraction": None,
            "busy_core_count": len(by_core) if by_core else None,
        }

    avg_denominator = makespan * core_count if core_count and core_count > 0 else None
    avg_load = total_duration / avg_denominator if avg_denominator else None
    max_load = max(by_core.values()) / makespan if by_core else None
    return {
        "total_scheduled_duration": total_duration if durations else None,
        "avg_core_load_fraction": avg_load,
        "max_core_load_fraction": max_load,
        "busy_core_count": len(by_core) if by_core else None,
    }


def extract_objective_components(result: Mapping[str, Any], memory_metrics: Mapping[str, Any], communication_metrics: Mapping[str, Any], scales: Mapping[str, float]) -> Dict[str, Any]:
    explicit_core = extract_numeric_candidate(
        result,
        [
            ["core_memory_penalty"],
            ["memory_core_penalty"],
            ["summary", "core_memory_penalty"],
            ["metadata", "core_memory_penalty"],
            ["objective_components", "core_memory_penalty"],
            ["objectiveComponents", "coreMemoryPenalty"],
        ],
    )
    explicit_cluster = extract_numeric_candidate(
        result,
        [
            ["cluster_memory_penalty"],
            ["memory_cluster_penalty"],
            ["summary", "cluster_memory_penalty"],
            ["metadata", "cluster_memory_penalty"],
            ["objective_components", "cluster_memory_penalty"],
            ["objectiveComponents", "clusterMemoryPenalty"],
        ],
    )
    explicit_memory_total = extract_numeric_candidate(
        result,
        [
            ["memory_penalty"],
            ["summary", "memory_penalty"],
            ["metadata", "memory_penalty"],
            ["objective_components", "memory_penalty"],
            ["objectiveComponents", "memoryPenalty"],
        ],
    )

    reconstructed_core = (as_float(memory_metrics.get("core_memory_overflow_kb")) or 0.0) * scales["core_overflow_scale"]
    reconstructed_cluster = (as_float(memory_metrics.get("cluster_memory_overflow_kb")) or 0.0) * scales["cluster_overflow_scale"]

    core_penalty = explicit_core if explicit_core is not None else reconstructed_core
    cluster_penalty = explicit_cluster if explicit_cluster is not None else reconstructed_cluster

    if explicit_memory_total is not None:
        memory_penalty = explicit_memory_total
    else:
        memory_penalty = core_penalty + cluster_penalty

    communication_penalty = as_float(communication_metrics.get("communication_penalty")) or 0.0

    return {
        "core_memory_penalty": core_penalty,
        "cluster_memory_penalty": cluster_penalty,
        "memory_penalty": memory_penalty,
        "communication_penalty_component": communication_penalty,
        "known_soft_objective_sum": memory_penalty + communication_penalty,
        "memory_component_source": "explicit" if explicit_memory_total is not None or explicit_core is not None or explicit_cluster is not None else "reconstructed_from_overflow",
    }


# ---------------------------------------------------------------------------
# Task-chain locality and latency
# ---------------------------------------------------------------------------


def collect_jobs_by_task(jobs: Sequence[JobInfo]) -> Dict[str, List[JobInfo]]:
    by_task: Dict[str, List[JobInfo]] = defaultdict(list)
    for job in jobs:
        if job.task_id:
            by_task[job.task_id].append(job)
    for task_id in by_task:
        by_task[task_id].sort(key=lambda j: ((j.release if j.release is not None else float("inf")), (j.start if j.start is not None else float("inf")), (j.finish if j.finish is not None else float("inf")), j.job_id))
    return by_task


def chain_latency_samples(chain: ChainInfo, jobs_by_task: Mapping[str, List[JobInfo]]) -> Tuple[List[float], List[float]]:
    """Approximate chain-instance latencies by pairing the kth job of each task.

    The backend may not expose explicit chain-instance identifiers.  For synthetic
    periodic chains this kth-activation pairing is a practical approximation and is
    marked as such in the output.  If the solver output contains fewer jobs for one
    chain member, only complete paired instances are used.
    """
    if len(chain.task_ids) < 2:
        return [], []
    task_jobs = [jobs_by_task.get(task_id, []) for task_id in chain.task_ids]
    if any(len(lst) == 0 for lst in task_jobs):
        return [], []
    instance_count = min(len(lst) for lst in task_jobs)

    latencies: List[float] = []
    violations: List[float] = []
    for idx in range(instance_count):
        root_job = task_jobs[0][idx]
        terminal_job = task_jobs[-1][idx]
        start_ref = root_job.release if root_job.release is not None else root_job.start
        end_ref = terminal_job.finish
        if start_ref is None or end_ref is None:
            continue
        latency = end_ref - start_ref
        if latency < 0:
            # Bad pairing or malformed schedule; ignore rather than contaminating p95.
            continue
        latencies.append(latency)
        if chain.deadline is not None:
            violations.append(max(0.0, latency - chain.deadline))
    return latencies, violations


def analyze_chain_locality(
    input_meta: InputMetadata,
    task_assignment: Mapping[str, Tuple[Optional[str], Optional[str]]],
    jobs: Sequence[JobInfo],
    solver: str,
    run_status: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    chains = input_meta.chains
    jobs_by_task = collect_jobs_by_task(jobs)
    detail_rows: List[Dict[str, Any]] = []

    for chain in chains:
        assigned = [task_assignment.get(tid, (None, None)) for tid in chain.task_ids]
        core_ids = [core for core, _cluster in assigned if core is not None]
        cluster_ids = [cluster for _core, cluster in assigned if cluster is not None]
        all_assigned = len(core_ids) == len(chain.task_ids)
        distinct_cores = len(set(core_ids)) if core_ids else None
        distinct_clusters = len(set(cluster_ids)) if cluster_ids else None
        same_core = bool(all_assigned and distinct_cores == 1)
        same_cluster = bool(all_assigned and distinct_clusters == 1)
        inter_cluster = bool(all_assigned and distinct_clusters is not None and distinct_clusters > 1)

        edge_count = max(0, len(chain.task_ids) - 1)
        same_core_edges = 0
        same_cluster_edges = 0
        inter_cluster_edges = 0
        unknown_edges = 0
        for pred_task, succ_task in zip(chain.task_ids[:-1], chain.task_ids[1:]):
            pred_core, pred_cluster = task_assignment.get(pred_task, (None, None))
            succ_core, succ_cluster = task_assignment.get(succ_task, (None, None))
            if pred_core is None or succ_core is None:
                unknown_edges += 1
            elif pred_core == succ_core:
                same_core_edges += 1
            elif pred_cluster is not None and succ_cluster is not None and pred_cluster == succ_cluster:
                same_cluster_edges += 1
            else:
                inter_cluster_edges += 1

        latencies, violations = chain_latency_samples(chain, jobs_by_task)
        deadline_violation_rate = None
        if violations:
            deadline_violation_rate = sum(1 for v in violations if v > 0) / len(violations)

        detail_rows.append(
            {
                "taskset_id": input_meta.taskset_id,
                "base_workload_key": input_meta.base_workload_key,
                "platform_group": input_meta.platform_group,
                "solver": solver,
                "run_status": run_status,
                "chain_id": chain.chain_id,
                "chain_source": chain.source,
                "chain_length": len(chain.task_ids),
                "chain_deadline": chain.deadline,
                "chain_period": chain.period,
                "all_tasks_assigned": all_assigned,
                "same_core_chain": same_core,
                "same_cluster_chain": same_cluster,
                "inter_cluster_chain": inter_cluster,
                "distinct_cores": distinct_cores,
                "distinct_clusters": distinct_clusters,
                "edge_count": edge_count,
                "same_core_edges": same_core_edges,
                "same_cluster_edges": same_cluster_edges,
                "inter_cluster_edges": inter_cluster_edges,
                "unknown_edges": unknown_edges,
                "latency_instance_count": len(latencies),
                "chain_latency_median": median_or_none(latencies),
                "chain_latency_p95": p95_or_none(latencies),
                "chain_latency_max": max(latencies) if latencies else None,
                "chain_deadline_violation_rate": deadline_violation_rate,
                "chain_deadline_violation_max": max(violations) if violations else None,
            }
        )

    if not detail_rows:
        return {
            "chain_count": 0,
            "chain_analysis_source": "none",
            "same_core_chain_rate": None,
            "same_cluster_chain_rate": None,
            "inter_cluster_chain_rate": None,
            "avg_distinct_cores_per_chain": None,
            "avg_distinct_clusters_per_chain": None,
            "chain_edge_same_core_rate": None,
            "chain_edge_same_cluster_rate": None,
            "chain_edge_inter_cluster_rate": None,
            "chain_latency_median": None,
            "chain_latency_p95": None,
            "chain_deadline_violation_rate": None,
        }, []

    chain_count = len(detail_rows)
    assigned_rows = [r for r in detail_rows if r["all_tasks_assigned"]]
    total_edges = sum(as_int(r["edge_count"]) or 0 for r in detail_rows)
    total_same_core_edges = sum(as_int(r["same_core_edges"]) or 0 for r in detail_rows)
    total_same_cluster_edges = sum(as_int(r["same_cluster_edges"]) or 0 for r in detail_rows)
    total_inter_cluster_edges = sum(as_int(r["inter_cluster_edges"]) or 0 for r in detail_rows)

    all_latency_medians = [r["chain_latency_median"] for r in detail_rows if r["chain_latency_median"] is not None]
    all_latency_p95s = [r["chain_latency_p95"] for r in detail_rows if r["chain_latency_p95"] is not None]
    violation_rates = [r["chain_deadline_violation_rate"] for r in detail_rows if r["chain_deadline_violation_rate"] is not None]

    summary = {
        "chain_count": chain_count,
        "chain_analysis_source": "explicit" if any(r["chain_source"] == "explicit" for r in detail_rows) else "inferred_dependencies",
        "same_core_chain_rate": sum(1 for r in assigned_rows if r["same_core_chain"]) / len(assigned_rows) if assigned_rows else None,
        "same_cluster_chain_rate": sum(1 for r in assigned_rows if r["same_cluster_chain"]) / len(assigned_rows) if assigned_rows else None,
        "inter_cluster_chain_rate": sum(1 for r in assigned_rows if r["inter_cluster_chain"]) / len(assigned_rows) if assigned_rows else None,
        "avg_distinct_cores_per_chain": statistics.mean([r["distinct_cores"] for r in assigned_rows if r["distinct_cores"] is not None]) if assigned_rows else None,
        "avg_distinct_clusters_per_chain": statistics.mean([r["distinct_clusters"] for r in assigned_rows if r["distinct_clusters"] is not None]) if assigned_rows else None,
        "chain_edge_same_core_rate": total_same_core_edges / total_edges if total_edges else None,
        "chain_edge_same_cluster_rate": total_same_cluster_edges / total_edges if total_edges else None,
        "chain_edge_inter_cluster_rate": total_inter_cluster_edges / total_edges if total_edges else None,
        "chain_latency_median": median_or_none(all_latency_medians),
        "chain_latency_p95": p95_or_none(all_latency_p95s),
        "chain_deadline_violation_rate": statistics.mean(violation_rates) if violation_rates else None,
    }
    return summary, detail_rows


# ---------------------------------------------------------------------------
# Bottleneck classification
# ---------------------------------------------------------------------------


def classify_bottleneck(record: Mapping[str, Any]) -> str:
    status = normalized_string(record.get("run_status"))
    if status == "PRESOLVE_REJECTED":
        return "compute"

    deadline_violation = as_float(record.get("deadline_violation")) or 0.0
    if deadline_violation > 0:
        return "deadline"

    memory_penalty = as_float(record.get("memory_penalty")) or 0.0
    communication_penalty = as_float(record.get("communication_penalty")) or 0.0
    max_core_load = as_float(record.get("max_core_load_fraction"))

    if memory_penalty > 0 or communication_penalty > 0:
        if memory_penalty >= communication_penalty:
            return "memory"
        return "communication"

    if max_core_load is not None and max_core_load >= 0.85:
        return "compute"
    if status in {"ERROR", "UNKNOWN", "MISSING_SOLUTION"}:
        return "unknown"
    return "none"


# ---------------------------------------------------------------------------
# Record extraction
# ---------------------------------------------------------------------------


def resolve_solution_file(output_root: Path, row: Mapping[str, Any]) -> Optional[Path]:
    raw_path = normalized_string(row.get("solution_file"))
    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = output_root / path
        if path.exists():
            return path
        # Some manifests may store paths relative to output/solutions.
        candidate = output_root / "solutions" / raw_path
        if candidate.exists():
            return candidate

    taskset_id = normalized_string(row.get("taskset_id"))
    solver = normalize_solver_name(row.get("solver"))
    if taskset_id and solver != "UNKNOWN":
        candidate = output_root / "solutions" / taskset_id / f"{solver}_solution.json"
        if candidate.exists():
            return candidate
        # Case-insensitive fallback.
        folder = output_root / "solutions" / taskset_id
        if folder.exists():
            for path in folder.glob("*_solution.json"):
                if parse_solver_from_solution_path(path) == solver:
                    return path
    return None


def build_missing_record(row: Mapping[str, Any], output_root: Path, expected_timeout: Optional[float]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    taskset_id = normalized_string(row.get("taskset_id"))
    if not taskset_id:
        taskset_id = "UNKNOWN_TASKSET"
    solver = normalize_solver_name(row.get("solver"))
    input_meta = extract_input_metadata(output_root, taskset_id, row.get("input_taskset_file"))
    runtime = as_float(row.get("runtime_seconds"))
    dummy_result: Dict[str, Any] = {}
    run_status = normalize_run_status(dummy_result, row, runtime, expected_timeout)
    if run_status == "UNKNOWN":
        run_status = normalized_string(row.get("manifest_status")) or normalized_string(row.get("status")) or "MISSING_SOLUTION"
        run_status = normalize_run_status({"status": run_status}, row, runtime, expected_timeout)

    task_count = as_int(row.get("task_count")) or input_meta.task_count or input_meta.task_count_from_id
    platform_group = normalize_platform_name(row.get("platform")) if row.get("platform") is not None else input_meta.platform_group

    record = {
        "taskset_id": taskset_id,
        "base_workload_key": input_meta.base_workload_key,
        "taskset_run_id": input_meta.run_id,
        "platform_key_from_id": input_meta.platform_key_from_id,
        "platform_name": input_meta.platform_name or row.get("platform"),
        "platform_group": platform_group,
        "solver": solver,
        "solution_file": None,
        "solution_file_exists": False,
        "input_taskset_file": str(input_meta.path) if input_meta.path else None,
        "input_taskset_exists": input_meta.exists,
        "manifest_source": row.get("manifest_source"),
        "raw_status": raw_status_text(dummy_result, row),
        "run_status": run_status,
        "solver_invoked": status_is_attempted(run_status),
        "timeout": status_is_timeout(run_status),
        "feasible": status_is_feasible(run_status),
        "quality_eligible": False,
        "error_message": row.get("error_message"),
        "runtime_seconds": runtime,
        "task_template_count": task_count,
        "job_count": None,
        "scheduled_job_count": None,
        "task_chain_count": len(input_meta.chains) if input_meta.chains else None,
        "dependency_template_count": input_meta.dependency_count,
        "core_count": input_meta.num_cores,
        "cluster_count": input_meta.num_clusters,
        "objective": None,
        "best_objective_bound": None,
        "bound_gap": None,
        "makespan": None,
        "core_memory_overflow_kb": None,
        "cluster_memory_overflow_kb": None,
        "total_memory_overflow_kb": None,
        "core_memory_penalty": None,
        "cluster_memory_penalty": None,
        "memory_penalty": None,
        "communication_penalty": None,
        "deadline_violation": None,
        "max_core_load_fraction": None,
        "bottleneck": "unknown" if run_status in {"MISSING_SOLUTION", "UNKNOWN"} else classify_bottleneck({"run_status": run_status}),
    }
    return record, []


def extract_record_from_solution(
    output_root: Path,
    row: Mapping[str, Any],
    solution_path: Path,
    expected_timeout: Optional[float],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    result = load_json(solution_path)
    taskset_id = normalized_string(row.get("taskset_id")) or parse_taskset_id_from_solution_path(solution_path)
    solver_from_file = parse_solver_from_solution_path(solution_path)
    solver_from_json = normalize_solver_name(first_key(result, ["solver", "solver_name", "solverName"]))
    solver = normalize_solver_name(row.get("solver")) if row.get("solver") is not None else (solver_from_json if solver_from_json != "UNKNOWN" else solver_from_file)

    input_meta = extract_input_metadata(output_root, taskset_id, row.get("input_taskset_file"))
    runtime = extract_runtime_seconds(result, row)
    run_status = normalize_run_status(result, row, runtime, expected_timeout)
    feasible = status_is_feasible(run_status)

    jobs = parse_schedule(result, input_meta)
    task_assignment = derive_task_assignment(jobs, result, input_meta)
    scales = extract_config_scales(result, input_meta)

    objective = extract_objective(result)
    best_bound = extract_best_bound(result, objective)
    bound_gap = None
    if objective is not None and best_bound is not None:
        bound_gap = abs(objective - best_bound) / max(abs(objective), 1.0)

    memory_metrics = extract_memory_metrics(result, input_meta, task_assignment)
    communication_metrics = extract_communication_metrics(result, input_meta, jobs, task_assignment, scales)
    objective_components = extract_objective_components(result, memory_metrics, communication_metrics, scales)
    deadline_violation = extract_deadline_violation(result, jobs)
    makespan = extract_makespan(result, jobs)
    compute_metrics = extract_compute_pressure(jobs, makespan, input_meta.num_cores)
    chain_summary, chain_details = analyze_chain_locality(input_meta, task_assignment, jobs, solver, run_status)

    summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
    metadata = result.get("metadata") if isinstance(result.get("metadata"), Mapping) else {}

    task_count = as_int(row.get("task_count")) or as_int(summary.get("task_template_count")) or input_meta.task_count or input_meta.task_count_from_id
    platform_group = normalize_platform_name(row.get("platform")) if row.get("platform") is not None else input_meta.platform_group

    record: Dict[str, Any] = {
        "taskset_id": taskset_id,
        "base_workload_key": input_meta.base_workload_key,
        "taskset_run_id": input_meta.run_id,
        "platform_key_from_id": input_meta.platform_key_from_id,
        "platform_name": input_meta.platform_name or row.get("platform"),
        "platform_group": platform_group,
        "solver": solver,
        "solver_from_file": solver_from_file,
        "solver_from_json": solver_from_json,
        "solution_file": str(solution_path),
        "solution_file_exists": solution_path.exists(),
        "input_taskset_file": str(input_meta.path) if input_meta.path else None,
        "input_taskset_exists": input_meta.exists,
        "manifest_source": row.get("manifest_source"),
        "raw_status": raw_status_text(result, row),
        "run_status": run_status,
        "solver_invoked": status_is_attempted(run_status),
        "timeout": status_is_timeout(run_status),
        "feasible": feasible,
        "quality_eligible": feasible and objective is not None,
        "error_message": row.get("error_message") or result.get("error") or result.get("message"),
        "runtime_seconds": runtime,
        "objective": objective,
        "best_objective_bound": best_bound,
        "bound_gap": bound_gap,
        "makespan": makespan,
        "task_template_count": task_count,
        "job_count": as_int(summary.get("job_count")) or len(jobs) or None,
        "scheduled_job_count": as_int(summary.get("scheduled_job_count")) or len(jobs) or None,
        "task_chain_count": as_int(summary.get("task_chain_count")) or len(input_meta.chains) or None,
        "dependency_template_count": as_int(summary.get("dependency_template_count")) or input_meta.dependency_count,
        "job_dependency_count": as_int(summary.get("job_dependency_count")) or sum(len(job.predecessors) for job in jobs) or None,
        "core_count": as_int(summary.get("core_count")) or input_meta.num_cores,
        "cluster_count": as_int(summary.get("cluster_count")) or input_meta.num_clusters,
        "input_task_memory_kb_sum": input_meta.total_task_memory_kb,
        "input_task_wcet_sum": input_meta.total_task_wcet,
        "core_overflow_scale": scales["core_overflow_scale"],
        "cluster_overflow_scale": scales["cluster_overflow_scale"],
        "comm_same_core": scales["comm_same_core"],
        "comm_same_cluster": scales["comm_same_cluster"],
        "comm_inter_cluster": scales["comm_inter_cluster"],
        "deadline_violation": deadline_violation,
        "num_conflicts": as_int(metadata.get("num_conflicts")),
        "num_branches": as_int(metadata.get("num_branches")),
        "model_building_seconds": as_float(metadata.get("model_building_seconds")),
        "solve_time": as_float(metadata.get("solve_time")),
        "ga_fitness": as_float(metadata.get("fitness")),
        "ga_constraint_violation": as_float(metadata.get("constraint_violation")),
        "ga_constraint_violation_cost": as_float(metadata.get("constraint_violation_cost")),
        "ga_generations_completed": as_int(get_nested(metadata, ["ga_metadata", "generations_completed"])) or as_int(metadata.get("generations_completed")),
    }
    record.update(memory_metrics)
    record.update(communication_metrics)
    record.update(objective_components)
    record.update(compute_metrics)
    record.update(chain_summary)
    record["bottleneck"] = classify_bottleneck(record)

    return record, chain_details


def load_results(
    output_root: Path,
    manifest: Optional[Path],
    expected_solvers: Sequence[str],
    expected_timeout: Optional[float],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if manifest is None:
        manifest = find_manifest(output_root)

    if manifest is not None:
        manifest_df = normalize_manifest_columns(load_manifest(manifest), manifest)
    else:
        manifest_df = normalize_manifest_columns(build_inferred_manifest(output_root, expected_solvers), None)

    # If a manifest is present but omits solution_file, resolve by convention.
    if "taskset_id" not in manifest_df.columns:
        raise ValueError("Manifest must contain a taskset_id column or equivalent.")
    if "solver" not in manifest_df.columns:
        raise ValueError("Manifest must contain a solver column or equivalent.")

    records: List[Dict[str, Any]] = []
    chain_details: List[Dict[str, Any]] = []

    for _, row_series in manifest_df.iterrows():
        row = row_series.to_dict()
        solution_path = resolve_solution_file(output_root, row)
        if solution_path is None:
            record, details = build_missing_record(row, output_root, expected_timeout)
        else:
            try:
                record, details = extract_record_from_solution(output_root, row, solution_path, expected_timeout)
            except Exception as exc:
                # Do not drop malformed result files from the denominator.
                record, details = build_missing_record(row, output_root, expected_timeout)
                record["run_status"] = "ERROR"
                record["solver_invoked"] = True
                record["feasible"] = False
                record["quality_eligible"] = False
                record["solution_file"] = str(solution_path)
                record["solution_file_exists"] = True
                record["error_message"] = f"Failed to parse solution JSON: {exc}"
        records.append(record)
        chain_details.extend(details)

    df = pd.DataFrame(records)
    chain_df = pd.DataFrame(chain_details)
    df = add_best_known_objective_gap(df)
    return df, chain_df


# ---------------------------------------------------------------------------
# Best-known objective and paired platform support
# ---------------------------------------------------------------------------


def add_best_known_objective_gap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "objective" not in out.columns or out.empty:
        out["best_known_objective"] = pd.NA
        out["objective_gap_to_best_known"] = pd.NA
        out["objective_gap_percent_to_best_known"] = pd.NA
        return out

    eligible = out[(out["quality_eligible"] == True) & out["objective"].notna()].copy()  # noqa: E712
    if eligible.empty:
        out["best_known_objective"] = pd.NA
        out["objective_gap_to_best_known"] = pd.NA
        out["objective_gap_percent_to_best_known"] = pd.NA
        return out

    # Best-known is per concrete taskset/platform instance, not across platforms.
    best = eligible.groupby("taskset_id", dropna=False)["objective"].min().rename("best_known_objective").reset_index()
    out = out.merge(best, on="taskset_id", how="left")
    denominator = out["best_known_objective"].abs().clip(lower=1.0)
    out["objective_gap_to_best_known"] = (out["objective"] - out["best_known_objective"]) / denominator
    out.loc[out["objective"].isna() | out["best_known_objective"].isna(), "objective_gap_to_best_known"] = pd.NA
    out["objective_gap_percent_to_best_known"] = 100.0 * out["objective_gap_to_best_known"]
    return out


def compute_platform_pair_coverage(df: pd.DataFrame, platform_order: Sequence[str]) -> pd.DataFrame:
    required = set(platform_order)
    rows: List[Dict[str, Any]] = []
    for (solver, key), group in df.groupby(["solver", "base_workload_key"], dropna=False):
        platforms = set(group["platform_group"].dropna().astype(str))
        rows.append(
            {
                "solver": solver,
                "base_workload_key": key,
                "platforms_present": ",".join(sorted(platforms)),
                "platform_count": len(platforms),
                "complete_platform_triplet": required.issubset(platforms),
            }
        )
    return pd.DataFrame(rows)


def paired_platform_subset(df: pd.DataFrame, platform_order: Sequence[str]) -> pd.DataFrame:
    coverage = compute_platform_pair_coverage(df, platform_order)
    complete_keys = coverage[coverage["complete_platform_triplet"] == True][["solver", "base_workload_key"]]  # noqa: E712
    if complete_keys.empty:
        return df.iloc[0:0].copy()
    return df.merge(complete_keys, on=["solver", "base_workload_key"], how="inner")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_evaluation(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["solver", "task_template_count"], dropna=False)
        .agg(
            attempted_runs=("taskset_id", "count"),
            solver_invoked_rate=("solver_invoked", "mean"),
            feasible_rate=("feasible", "mean"),
            timeout_rate=("timeout", "mean"),
            runtime_median=("runtime_seconds", "median"),
            runtime_mean=("runtime_seconds", "mean"),
            runtime_iqr_low=("runtime_seconds", lambda s: s.quantile(0.25)),
            runtime_iqr_high=("runtime_seconds", lambda s: s.quantile(0.75)),
            objective_median=("objective", "median"),
            objective_mean=("objective", "mean"),
            best_known_objective_median=("best_known_objective", "median"),
            objective_gap_to_best_known_median=("objective_gap_to_best_known", "median"),
            objective_gap_to_best_known_mean=("objective_gap_to_best_known", "mean"),
            bound_gap_median=("bound_gap", "median"),
            makespan_median=("makespan", "median"),
            job_count_median=("job_count", "median"),
            scheduled_job_count_median=("scheduled_job_count", "median"),
            memory_penalty_median=("memory_penalty", "median"),
            core_memory_penalty_median=("core_memory_penalty", "median"),
            cluster_memory_penalty_median=("cluster_memory_penalty", "median"),
            communication_penalty_median=("communication_penalty", "median"),
            total_memory_overflow_kb_median=("total_memory_overflow_kb", "median"),
            deadline_violation_median=("deadline_violation", "median"),
            max_core_load_fraction_median=("max_core_load_fraction", "median"),
            same_core_chain_rate_median=("same_core_chain_rate", "median"),
            same_cluster_chain_rate_median=("same_cluster_chain_rate", "median"),
            inter_cluster_chain_rate_median=("inter_cluster_chain_rate", "median"),
            chain_latency_median=("chain_latency_median", "median"),
            chain_latency_p95_median=("chain_latency_p95", "median"),
            chain_deadline_violation_rate_median=("chain_deadline_violation_rate", "median"),
            num_conflicts_median=("num_conflicts", "median"),
            num_branches_median=("num_branches", "median"),
        )
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )


def aggregate_status_counts(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["solver", "task_template_count", "run_status"], dropna=False)
        .size()
        .rename("runs")
        .reset_index()
        .sort_values(["solver", "task_template_count", "run_status"])
    )


def aggregate_objective_components(df: pd.DataFrame) -> pd.DataFrame:
    eligible = df[df["quality_eligible"] == True].copy() if "quality_eligible" in df.columns else df.copy()  # noqa: E712
    if eligible.empty:
        return pd.DataFrame()
    return (
        eligible.groupby(["solver", "task_template_count"], dropna=False)
        .agg(
            runs=("taskset_id", "count"),
            objective_median=("objective", "median"),
            core_memory_penalty_median=("core_memory_penalty", "median"),
            cluster_memory_penalty_median=("cluster_memory_penalty", "median"),
            memory_penalty_median=("memory_penalty", "median"),
            communication_penalty_median=("communication_penalty", "median"),
            known_soft_objective_sum_median=("known_soft_objective_sum", "median"),
            memory_share_median=("memory_penalty", lambda s: s.median()),
        )
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )


def aggregate_platform_comparison(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["platform_group", "solver", "task_template_count"], dropna=False)
        .agg(
            attempted_runs=("taskset_id", "count"),
            feasible_rate=("feasible", "mean"),
            timeout_rate=("timeout", "mean"),
            runtime_median=("runtime_seconds", "median"),
            objective_median=("objective", "median"),
            memory_penalty_median=("memory_penalty", "median"),
            communication_penalty_median=("communication_penalty", "median"),
            total_memory_overflow_kb_median=("total_memory_overflow_kb", "median"),
            same_core_chain_rate_median=("same_core_chain_rate", "median"),
            same_cluster_chain_rate_median=("same_cluster_chain_rate", "median"),
        )
        .reset_index()
        .sort_values(["platform_group", "solver", "task_template_count"])
    )


def aggregate_paired_platform_comparison(df: pd.DataFrame, platform_order: Sequence[str]) -> pd.DataFrame:
    paired = paired_platform_subset(df, platform_order)
    if paired.empty:
        return pd.DataFrame()
    return aggregate_platform_comparison(paired)


def aggregate_chain_locality(chain_df: pd.DataFrame) -> pd.DataFrame:
    if chain_df.empty:
        return pd.DataFrame()
    return (
        chain_df.groupby(["solver", "platform_group", "chain_source"], dropna=False)
        .agg(
            chains=("chain_id", "count"),
            same_core_chain_rate=("same_core_chain", "mean"),
            same_cluster_chain_rate=("same_cluster_chain", "mean"),
            inter_cluster_chain_rate=("inter_cluster_chain", "mean"),
            distinct_cores_median=("distinct_cores", "median"),
            distinct_clusters_median=("distinct_clusters", "median"),
            chain_latency_median=("chain_latency_median", "median"),
            chain_latency_p95_median=("chain_latency_p95", "median"),
            chain_deadline_violation_rate=("chain_deadline_violation_rate", "mean"),
        )
        .reset_index()
        .sort_values(["solver", "platform_group", "chain_source"])
    )


def aggregate_communication_edges(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["solver", "task_template_count"], dropna=False)
        .agg(
            runs=("taskset_id", "count"),
            communication_edge_count_median=("communication_edge_count", "median"),
            same_core_rate_median=("communication_same_core_rate", "median"),
            same_cluster_rate_median=("communication_same_cluster_rate", "median"),
            inter_cluster_rate_median=("communication_inter_cluster_rate", "median"),
            communication_penalty_median=("communication_penalty", "median"),
        )
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )


def aggregate_bottlenecks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["solver", "task_template_count", "bottleneck"], dropna=False)
        .size()
        .rename("runs")
        .reset_index()
        .sort_values(["solver", "task_template_count", "bottleneck"])
    )


def data_quality_report(df: pd.DataFrame, chain_df: pd.DataFrame, platform_order: Sequence[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    def add(check: str, value: Any, severity: str = "info", note: str = "") -> None:
        rows.append({"check": check, "value": value, "severity": severity, "note": note})

    add("total_manifest_rows", len(df))
    add("missing_solution_rows", int((df["run_status"] == "MISSING_SOLUTION").sum()) if "run_status" in df else None, "warning")
    add("error_rows", int((df["run_status"] == "ERROR").sum()) if "run_status" in df else None, "warning")
    add("presolve_rejected_rows", int((df["run_status"] == "PRESOLVE_REJECTED").sum()) if "run_status" in df else None)
    add("rows_without_input_taskset", int((df["input_taskset_exists"] == False).sum()) if "input_taskset_exists" in df else None, "warning")  # noqa: E712
    add("rows_without_runtime", int(df["runtime_seconds"].isna().sum()) if "runtime_seconds" in df else None, "warning")
    add("quality_eligible_rows", int((df["quality_eligible"] == True).sum()) if "quality_eligible" in df else None)  # noqa: E712
    add("chain_detail_rows", len(chain_df), "warning" if chain_df.empty else "info")

    coverage = compute_platform_pair_coverage(df, platform_order)
    add("complete_platform_triplets", int((coverage["complete_platform_triplet"] == True).sum()) if not coverage.empty else 0, "warning" if coverage.empty else "info")  # noqa: E712
    add("incomplete_platform_triplets", int((coverage["complete_platform_triplet"] == False).sum()) if not coverage.empty else 0, "warning")  # noqa: E712

    task_sizes = sorted(df["task_template_count"].dropna().astype(int).unique().tolist()) if "task_template_count" in df else []
    add("observed_task_sizes", ",".join(map(str, task_sizes)))
    platforms = sorted(df["platform_group"].dropna().astype(str).unique().tolist()) if "platform_group" in df else []
    add("observed_platforms", ",".join(platforms))
    solvers = sorted(df["solver"].dropna().astype(str).unique().tolist()) if "solver" in df else []
    add("observed_solvers", ",".join(solvers))

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def save_runtime_vs_task_count(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "01_runtime_vs_task_count.png"
    plot_df = df.dropna(subset=["runtime_seconds", "task_template_count", "solver"]).copy()
    plot_df = plot_df[(plot_df["solver_invoked"] == True) & (plot_df["runtime_seconds"] > 0)]  # noqa: E712
    if plot_df.empty:
        return path

    plt.figure(figsize=(8.5, 5.2))
    for solver in ordered_unique(plot_df["solver"].unique().tolist(), solver_order):
        sdf = plot_df[plot_df["solver"] == solver]
        grouped = sdf.groupby("task_template_count")["runtime_seconds"].median().reset_index().sort_values("task_template_count")
        plt.plot(grouped["task_template_count"], grouped["runtime_seconds"], marker="o", label=solver)
    plt.yscale("log")
    plt.xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Median runtime in seconds, log scale", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Runtime scalability by nominal task-set size", fontsize=TITLE_FONTSIZE)
    plt.xticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE)
    save_current_plot(path)
    return path


def save_runtime_vs_job_count(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "01b_runtime_vs_job_count.png"
    plot_df = df.dropna(subset=["runtime_seconds", "solver"]).copy()
    plot_df = plot_df[(plot_df["solver_invoked"] == True) & (plot_df["runtime_seconds"] > 0)]  # noqa: E712
    plot_df["runtime_job_count"] = plot_df["scheduled_job_count"]
    plot_df.loc[plot_df["runtime_job_count"].isna(), "runtime_job_count"] = plot_df["job_count"]
    plot_df = plot_df.dropna(subset=["runtime_job_count"])
    plot_df = plot_df[plot_df["runtime_job_count"] > 0]
    if plot_df.empty:
        return path

    plt.figure(figsize=(8.5, 5.2))
    for solver in ordered_unique(plot_df["solver"].unique().tolist(), solver_order):
        sdf = plot_df[plot_df["solver"] == solver]
        grouped = sdf.groupby("runtime_job_count")["runtime_seconds"].median().reset_index().sort_values("runtime_job_count")
        plt.plot(grouped["runtime_job_count"], grouped["runtime_seconds"], marker="o", label=solver)
    plt.yscale("log")
    plt.xlabel("Number of scheduled jobs", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Median runtime in seconds, log scale", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Runtime scalability by expanded job count", fontsize=TITLE_FONTSIZE)
    plt.xticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE)
    save_current_plot(path)
    return path


def save_status_distribution(df: pd.DataFrame, analysis_dir: Path) -> Path:
    path = analysis_dir / "02_status_distribution_vs_task_count.png"
    if df.empty:
        return path
    counts = df.groupby(["task_template_count", "run_status"]).size().rename("runs").reset_index()
    if counts.empty:
        return path
    pivot = counts.pivot(index="task_template_count", columns="run_status", values="runs").fillna(0)
    cols = [c for c in STATUS_ORDER if c in pivot.columns] + [c for c in pivot.columns if c not in STATUS_ORDER]
    pivot = pivot[cols]
    ax = pivot.plot(kind="bar", stacked=True, figsize=(9, 5.5))
    ax.set_xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    ax.set_ylabel("Run count", fontsize=AXIS_LABEL_FONTSIZE)
    ax.set_title("Run status distribution by task-set size", fontsize=TITLE_FONTSIZE)
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5)
    ax.legend(title="Status", fontsize=LEGEND_FONTSIZE)
    plt.xticks(rotation=0, fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    save_current_plot(path)
    return path


def save_feasibility_rate(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "03_feasibility_rate_vs_task_count.png"
    plot_df = df.dropna(subset=["solver", "task_template_count"]).copy()
    if plot_df.empty:
        return path
    grouped = plot_df.groupby(["solver", "task_template_count"])["feasible"].mean().reset_index().sort_values(["solver", "task_template_count"])
    plt.figure(figsize=(8.5, 5.2))
    for solver in ordered_unique(grouped["solver"].unique().tolist(), solver_order):
        sdf = grouped[grouped["solver"] == solver]
        plt.plot(sdf["task_template_count"], sdf["feasible"], marker="o", label=solver)
    plt.ylim(-0.05, 1.05)
    plt.xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Feasibility rate over attempted runs", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Feasibility rate including presolve, timeout, and missing-output cases", fontsize=TITLE_FONTSIZE)
    plt.xticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE)
    save_current_plot(path)
    return path


def save_objective_gap_boxplot(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "04_objective_gap_to_best_known_boxplot.png"
    plot_df = df[(df["quality_eligible"] == True) & df["objective_gap_percent_to_best_known"].notna()].copy()  # noqa: E712
    if plot_df.empty:
        return path
    solvers = ordered_unique(plot_df["solver"].unique().tolist(), solver_order)
    data = [plot_df.loc[plot_df["solver"] == solver, "objective_gap_percent_to_best_known"].astype(float).values for solver in solvers]
    plt.figure(figsize=(8, 5))
    plt.boxplot(data, labels=solvers, showmeans=True)
    plt.axhline(0, linestyle="--", linewidth=0.8)
    plt.xlabel("Solver", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Objective gap to best known (%)", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Solution quality relative to best feasible solver result", fontsize=TITLE_FONTSIZE)
    plt.xticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5)
    save_current_plot(path)
    return path


def save_objective_decomposition(df: pd.DataFrame, analysis_dir: Path) -> Path:
    path = analysis_dir / "05_objective_decomposition.png"
    plot_df = df[(df["quality_eligible"] == True)].dropna(subset=["solver", "task_template_count"]).copy()  # noqa: E712
    if plot_df.empty:
        return path
    grouped = (
        plot_df.groupby(["task_template_count", "solver"])
        .agg(
            core_memory_penalty=("core_memory_penalty", "median"),
            cluster_memory_penalty=("cluster_memory_penalty", "median"),
            communication_penalty=("communication_penalty", "median"),
        )
        .reset_index()
        .sort_values(["task_template_count", "solver"])
    )
    grouped["label"] = grouped["task_template_count"].astype(str) + " / " + grouped["solver"].astype(str)
    x = list(range(len(grouped)))
    core = grouped["core_memory_penalty"].fillna(0).astype(float).values
    cluster = grouped["cluster_memory_penalty"].fillna(0).astype(float).values
    comm = grouped["communication_penalty"].fillna(0).astype(float).values
    plt.figure(figsize=(max(10, len(grouped) * 0.45), 5.7))
    plt.bar(x, core, label="Core memory")
    plt.bar(x, cluster, bottom=core, label="Cluster memory")
    plt.bar(x, comm, bottom=core + cluster, label="Communication")
    plt.xticks(x, grouped["label"], rotation=60, ha="right", fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(fontsize=TICK_LABEL_FONTSIZE)
    plt.xlabel("Task count / solver", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Median objective component", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Objective decomposition for feasible runs", fontsize=TITLE_FONTSIZE)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE)
    save_current_plot(path)
    return path


def save_platform_paired_comparison(df: pd.DataFrame, analysis_dir: Path, platform_order: Sequence[str]) -> Path:
    path = analysis_dir / "06_platform_paired_objective_memory.png"
    paired = paired_platform_subset(df, platform_order)
    paired = paired[(paired["quality_eligible"] == True)].copy() if not paired.empty else paired  # noqa: E712
    if paired.empty:
        return path
    grouped = (
        paired.groupby(["platform_group", "solver"])
        .agg(objective=("objective", "median"), total_memory_overflow_kb=("total_memory_overflow_kb", "median"))
        .reset_index()
    )
    platforms = ordered_unique(grouped["platform_group"].unique().tolist(), platform_order)
    solvers = ordered_unique(grouped["solver"].unique().tolist(), DEFAULT_SOLVER_ORDER)
    pivot_obj = grouped.pivot(index="platform_group", columns="solver", values="objective").reindex(platforms).reindex(columns=solvers)
    pivot_mem = grouped.pivot(index="platform_group", columns="solver", values="total_memory_overflow_kb").reindex(platforms).reindex(columns=solvers)
    fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    pivot_obj.plot(kind="bar", ax=axes[0])
    axes[0].set_ylabel("Median objective", fontsize=AXIS_LABEL_FONTSIZE)
    axes[0].set_title("Paired platform comparison: objective", fontsize=TITLE_FONTSIZE)
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.5)
    axes[0].legend(title="Solver", fontsize=LEGEND_FONTSIZE)
    pivot_mem.plot(kind="bar", ax=axes[1])
    axes[1].set_ylabel("Median memory overflow (KB)", fontsize=AXIS_LABEL_FONTSIZE)
    axes[1].set_title("Paired platform comparison: memory overflow", fontsize=TITLE_FONTSIZE)
    axes[1].grid(True, axis="y", linestyle="--", linewidth=0.5)
    axes[1].legend(title="Solver", fontsize=LEGEND_FONTSIZE)
    axes[1].set_xlabel("Platform", fontsize=AXIS_LABEL_FONTSIZE)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close(fig)
    return path


def save_chain_locality_rates(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "07_chain_locality_rates.png"
    plot_df = df[(df["quality_eligible"] == True)].dropna(subset=["solver", "task_template_count"]).copy()  # noqa: E712
    if plot_df.empty or plot_df["same_core_chain_rate"].notna().sum() == 0:
        return path
    grouped = (
        plot_df.groupby(["solver", "task_template_count"])
        .agg(
            same_core_chain_rate=("same_core_chain_rate", "median"),
            same_cluster_chain_rate=("same_cluster_chain_rate", "median"),
            inter_cluster_chain_rate=("inter_cluster_chain_rate", "median"),
        )
        .reset_index()
        .sort_values(["solver", "task_template_count"])
    )
    plt.figure(figsize=(9, 5.5))
    for solver in ordered_unique(grouped["solver"].unique().tolist(), solver_order):
        sdf = grouped[grouped["solver"] == solver]
        plt.plot(sdf["task_template_count"], sdf["same_core_chain_rate"], marker="o", label=f"{solver} same core")
        plt.plot(sdf["task_template_count"], sdf["same_cluster_chain_rate"], marker="s", linestyle="--", label=f"{solver} same cluster")
    plt.ylim(-0.05, 1.05)
    plt.xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Median chain locality rate", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Task-chain locality by solver and task-set size", fontsize=TITLE_FONTSIZE)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE, ncol=2)
    save_current_plot(path)
    return path


def save_chain_latency(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "08_chain_latency_vs_task_count.png"
    plot_df = df[(df["quality_eligible"] == True)].dropna(subset=["solver", "task_template_count", "chain_latency_p95"]).copy()  # noqa: E712
    if plot_df.empty:
        return path
    grouped = plot_df.groupby(["solver", "task_template_count"])["chain_latency_p95"].median().reset_index().sort_values(["solver", "task_template_count"])
    plt.figure(figsize=(8.5, 5.2))
    for solver in ordered_unique(grouped["solver"].unique().tolist(), solver_order):
        sdf = grouped[grouped["solver"] == solver]
        plt.plot(sdf["task_template_count"], sdf["chain_latency_p95"], marker="o", label=solver)
    plt.xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Median per-run p95 chain latency", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("End-to-end task-chain latency", fontsize=TITLE_FONTSIZE)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.legend(fontsize=LEGEND_FONTSIZE)
    save_current_plot(path)
    return path


def save_bottleneck_heatmap(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str]) -> Path:
    path = analysis_dir / "09_dominant_bottleneck_heatmap.png"
    plot_df = df.dropna(subset=["solver", "task_template_count", "bottleneck"]).copy()
    if plot_df.empty:
        return path
    counts = plot_df.groupby(["solver", "task_template_count", "bottleneck"]).size().rename("runs").reset_index()
    dominant = counts.sort_values(["solver", "task_template_count", "runs"], ascending=[True, True, False]).drop_duplicates(["solver", "task_template_count"])
    task_counts = sorted(plot_df["task_template_count"].dropna().astype(int).unique().tolist())
    solvers = ordered_unique(plot_df["solver"].dropna().unique().tolist(), solver_order)
    code_map = {name: idx for idx, name in enumerate(BOTTLENECK_ORDER)}
    matrix: List[List[float]] = []
    labels: List[List[str]] = []
    for solver in solvers:
        row_values: List[float] = []
        row_labels: List[str] = []
        for task_count in task_counts:
            match = dominant[(dominant["solver"] == solver) & (dominant["task_template_count"].astype(int) == int(task_count))]
            if match.empty:
                row_values.append(float("nan"))
                row_labels.append("")
            else:
                bottleneck = str(match.iloc[0]["bottleneck"])
                runs = int(match.iloc[0]["runs"])
                row_values.append(float(code_map.get(bottleneck, code_map["unknown"])))
                row_labels.append(f"{bottleneck}\n({runs})")
        matrix.append(row_values)
        labels.append(row_labels)
    plt.figure(figsize=(max(8, len(task_counts) * 0.8), max(3.5, len(solvers) * 0.8)))
    plt.imshow(matrix, aspect="auto", interpolation="nearest")
    plt.xticks(range(len(task_counts)), task_counts, fontsize=TICK_LABEL_FONTSIZE)
    plt.yticks(range(len(solvers)), solvers, fontsize=TICK_LABEL_FONTSIZE)
    plt.xlabel("Number of task templates", fontsize=AXIS_LABEL_FONTSIZE)
    plt.ylabel("Solver", fontsize=AXIS_LABEL_FONTSIZE)
    plt.title("Dominant bottleneck by solver and task-set size", fontsize=TITLE_FONTSIZE)
    cbar = plt.colorbar(ticks=list(code_map.values()))
    cbar.ax.set_yticklabels(BOTTLENECK_ORDER)
    for i, row in enumerate(labels):
        for j, text in enumerate(row):
            if text:
                plt.text(j, i, text, ha="center", va="center", fontsize=ANNOTATION_FONTSIZE)
    save_current_plot(path)
    return path


def save_all_plots(df: pd.DataFrame, analysis_dir: Path, solver_order: Sequence[str], platform_order: Sequence[str]) -> List[Path]:
    return [
        save_runtime_vs_task_count(df, analysis_dir, solver_order),
        save_runtime_vs_job_count(df, analysis_dir, solver_order),
        save_status_distribution(df, analysis_dir),
        save_feasibility_rate(df, analysis_dir, solver_order),
        save_objective_gap_boxplot(df, analysis_dir, solver_order),
        save_objective_decomposition(df, analysis_dir),
        save_platform_paired_comparison(df, analysis_dir, platform_order),
        save_chain_locality_rates(df, analysis_dir, solver_order),
        save_chain_latency(df, analysis_dir, solver_order),
        save_bottleneck_heatmap(df, analysis_dir, solver_order),
    ]


# ---------------------------------------------------------------------------
# Output and reporting
# ---------------------------------------------------------------------------


def write_outputs(
    df: pd.DataFrame,
    chain_df: pd.DataFrame,
    analysis_dir: Path,
    solver_order: Sequence[str],
    platform_order: Sequence[str],
    make_plots: bool,
) -> List[Path]:
    ensure_dir(analysis_dir)
    written: List[Path] = []

    agg = aggregate_evaluation(df)
    status_counts = aggregate_status_counts(df)
    objective_components = aggregate_objective_components(df)
    platform_summary = aggregate_platform_comparison(df)
    paired_platform_summary = aggregate_paired_platform_comparison(df, platform_order)
    platform_coverage = compute_platform_pair_coverage(df, platform_order)
    chain_summary = aggregate_chain_locality(chain_df)
    communication_summary = aggregate_communication_edges(df)
    bottleneck_summary = aggregate_bottlenecks(df)
    quality = data_quality_report(df, chain_df, platform_order)

    outputs = {
        "evaluation_raw_results.csv": df,
        "evaluation_aggregated_summary.csv": agg,
        "status_counts.csv": status_counts,
        "objective_components_summary.csv": objective_components,
        "platform_comparison_summary.csv": platform_summary,
        "platform_paired_summary.csv": paired_platform_summary,
        "platform_pair_coverage.csv": platform_coverage,
        "chain_locality_summary.csv": chain_summary,
        "chain_locality_details.csv": chain_df,
        "communication_edges_summary.csv": communication_summary,
        "bottleneck_summary.csv": bottleneck_summary,
        "data_quality_report.csv": quality,
    }
    for filename, frame in outputs.items():
        path = analysis_dir / filename
        frame.to_csv(path, index=False)
        written.append(path)

    if make_plots:
        written.extend(save_all_plots(df, analysis_dir, solver_order, platform_order))

    return written


def print_summary(df: pd.DataFrame, written: Sequence[Path]) -> None:
    print("\n=== RunSoC 2.0 results analysis ===")
    print(f"Rows in denominator: {len(df)}")
    if "solver" in df:
        print("Solvers:", ", ".join(sorted(df["solver"].dropna().astype(str).unique())))
    if "task_template_count" in df:
        sizes = sorted(df["task_template_count"].dropna().astype(int).unique().tolist())
        print("Task sizes:", sizes)
    if "platform_group" in df:
        print("Platforms:", ", ".join(sorted(df["platform_group"].dropna().astype(str).unique())))

    print("\nStatus counts:")
    if {"solver", "run_status"}.issubset(df.columns):
        print(df.groupby(["solver", "run_status"]).size().rename("runs").reset_index().to_string(index=False))

    print("\nFeasibility by solver:")
    if {"solver", "feasible"}.issubset(df.columns):
        print(df.groupby("solver")["feasible"].mean().rename("feasible_rate").reset_index().to_string(index=False))

    print("\nWritten outputs:")
    for path in written:
        print(path)


# ---------------------------------------------------------------------------
# Public API and CLI
# ---------------------------------------------------------------------------


def run_analysis(
    output_root: Path,
    analysis_dir: Path,
    manifest: Optional[Path] = None,
    expected_solvers: Sequence[str] = DEFAULT_SOLVER_ORDER,
    target_sizes: Optional[Sequence[int]] = None,
    solver_timeout: Optional[float] = 1000.0,
    make_plots: bool = True,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    output_root = Path(output_root)
    analysis_dir = Path(analysis_dir)
    if not output_root.exists():
        raise FileNotFoundError(f"Output root does not exist: {output_root}")
    ensure_dir(analysis_dir)

    solver_order = [normalize_solver_name(s) for s in expected_solvers]
    df, chain_df = load_results(output_root, manifest, solver_order, solver_timeout)

    if target_sizes:
        target_set = set(int(s) for s in target_sizes)
        df = df[df["task_template_count"].isin(target_set)].copy()
        if not chain_df.empty:
            valid_tasksets = set(df["taskset_id"].astype(str))
            chain_df = chain_df[chain_df["taskset_id"].astype(str).isin(valid_tasksets)].copy()

    written = write_outputs(df, chain_df, analysis_dir, solver_order, DEFAULT_PLATFORM_ORDER, make_plots)
    if verbose:
        print_summary(df, written)
    return df, aggregate_evaluation(df)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Thesis-grade analysis for RunSoC 2.0 solver results.")
    parser.add_argument("--output-root", type=Path, required=True, help="Root output directory containing generated_tasksets/ and solutions/.")
    parser.add_argument("--analysis-dir", type=Path, required=True, help="Directory where CSV summaries and figures are written.")
    parser.add_argument("--manifest", type=Path, default=None, help="Optional CSV/JSON/JSONL run manifest preserving all attempted runs.")
    parser.add_argument("--expected-solvers", nargs="+", default=DEFAULT_SOLVER_ORDER, help="Expected solvers used to infer missing runs when no manifest is present.")
    parser.add_argument("--target-sizes", nargs="+", type=int, default=None, help="Optional task sizes to keep. Defaults to all discovered sizes.")
    parser.add_argument("--thesis-target-sizes", action="store_true", help="Keep the thesis experiment sizes: 10 50 100 200 500 1000.")
    parser.add_argument("--solver-timeout", type=float, default=1000.0, help="Timeout in seconds used to classify timeout-like runs when status text is ambiguous.")
    parser.add_argument("--no-plots", action="store_true", help="Write CSV files only; skip figures.")
    parser.add_argument("--quiet", action="store_true", help="Suppress console summary.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_sizes = DEFAULT_TARGET_TASK_SIZES if args.thesis_target_sizes else args.target_sizes
    run_analysis(
        output_root=args.output_root,
        analysis_dir=args.analysis_dir,
        manifest=args.manifest,
        expected_solvers=args.expected_solvers,
        target_sizes=target_sizes,
        solver_timeout=args.solver_timeout,
        make_plots=not args.no_plots,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
