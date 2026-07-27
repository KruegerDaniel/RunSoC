"""Write recommended RunSoC 2.0 evaluation config JSON files.

Usage:
    python write_evaluation_configs.py --output-dir .

This writes:
    evaluation-pilot.json
    evaluation-main.json
    evaluation-stress.json
    evaluation-comm-sensitivity.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PLATFORMS_ALL = [
    {"name": "renesas", "soc_template_path": "platforms/renesas-rcar-vh4.json"},
    {"name": "nvidia", "soc_template_path": "platforms/nvidia-jetson-agx-orin64.json"},
    {"name": "ti", "soc_template_path": "platforms/ti-tda4vm.json"},
]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory where config JSON files should be written.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pilot = {
        "platforms": PLATFORMS_ALL,
        "solvers": ["CPSAT", "CBC", "GA"],
        "timeout_seconds": 120,
        "watchdog_grace_seconds": 30,
        "generated_tasksets_dir": "runs/pilot/generated_tasksets",
        "solver_outputs_dir": "runs/pilot/solutions",
        "seed": 20260700,
        "paired_platform_workloads": True,
        "tasksets": [
            {"num_tasks": 10, "count": 5, "filename_prefix": "taskset_10"},
            {"num_tasks": 25, "count": 5, "filename_prefix": "taskset_25"},
            {"num_tasks": 50, "count": 5, "filename_prefix": "taskset_50"},
            {"num_tasks": 100, "count": 5, "filename_prefix": "taskset_100"},
            {"num_tasks": 150, "count": 5, "filename_prefix": "taskset_150"},
        ],
    }

    main_cfg = {
        "platforms": PLATFORMS_ALL,
        "solvers": ["CPSAT", "CBC", "GA"],
        "timeout_seconds": 600,
        "watchdog_grace_seconds": 30,
        "generated_tasksets_dir": "runs/main/generated_tasksets",
        "solver_outputs_dir": "runs/main/solutions",
        "seed": 20260701,
        "paired_platform_workloads": True,
        "tasksets": [
            {"num_tasks": 10, "count": 25, "filename_prefix": "taskset_10"},
            {"num_tasks": 25, "count": 25, "filename_prefix": "taskset_25"},
            {"num_tasks": 50, "count": 20, "filename_prefix": "taskset_50"},
            {"num_tasks": 75, "count": 20, "filename_prefix": "taskset_75"},
            {"num_tasks": 100, "count": 15, "filename_prefix": "taskset_100"},
            {"num_tasks": 150, "count": 12, "filename_prefix": "taskset_150"},
            {"num_tasks": 200, "count": 8, "filename_prefix": "taskset_200"},
        ],
    }

    stress = {
        "platforms": PLATFORMS_ALL,
        "solvers": ["CPSAT", "CBC", "GA"],
        "timeout_seconds": 900,
        "watchdog_grace_seconds": 30,
        "generated_tasksets_dir": "runs/stress/generated_tasksets",
        "solver_outputs_dir": "runs/stress/solutions",
        "seed": 20260702,
        "paired_platform_workloads": True,
        "tasksets": [
            {"num_tasks": 300, "count": 6, "filename_prefix": "taskset_300"},
            {"num_tasks": 500, "count": 4, "filename_prefix": "taskset_500"},
        ],
    }

    comm_sensitivity = {
        "platforms": [
            {
                "name": "nvidia_comm_low",
                "soc_template_path": "platforms/nvidia-jetson-agx-orin64-comm-low.json",
            },
            {
                "name": "nvidia_comm_default",
                "soc_template_path": "platforms/nvidia-jetson-agx-orin64.json",
            },
            {
                "name": "nvidia_comm_high",
                "soc_template_path": "platforms/nvidia-jetson-agx-orin64-comm-high.json",
            },
        ],
        "solvers": ["CPSAT"],
        "timeout_seconds": 600,
        "watchdog_grace_seconds": 30,
        "generated_tasksets_dir": "runs/comm_sensitivity/generated_tasksets",
        "solver_outputs_dir": "runs/comm_sensitivity/solutions",
        "seed": 20260703,
        "paired_platform_workloads": True,
        "tasksets": [
            {"num_tasks": 50, "count": 10, "filename_prefix": "taskset_50"},
            {"num_tasks": 100, "count": 10, "filename_prefix": "taskset_100"},
        ],
    }

    configs = {
        "evaluation-pilot.json": pilot,
        "evaluation-main.json": main_cfg,
        "evaluation-stress.json": stress,
        "evaluation-comm-sensitivity.json": comm_sensitivity,
    }

    for filename, data in configs.items():
        path = output_dir / filename
        write_json(path, data)
        print(path)


if __name__ == "__main__":
    main()
