import argparse
import copy
import json
import os
import random
from pathlib import Path
from typing import Dict, Optional, List

from WATERS15_distributions import (
    PERIOD_DISTRIBUTION,
    ACTIVATION_PATTERN_DISTRIBUTION,
    sample_weibull_us,
    CHAIN_LENGTH_DISTRIBUTION,
)
from domain_taskname_distributions import (
    DOMAIN_DISTRIBUTIONS,
    TASK_NAME_PREFIXES_BY_DOMAIN,
    memory_usage_kb_by_domain,
)


PERIODIC_PERIODS_US = [
    1_000,
    2_000,
    5_000,
    10_000,
    20_000,
    50_000,
    100_000,
    200_000,
    1_000_000,
]


###################################
# UTIL
###################################


def weighted_choice(weighted_items):
    values = [x[0] for x in weighted_items]
    weights = [x[1] for x in weighted_items]
    return random.choices(values, weights=weights, k=1)[0]


def random_period():
    return weighted_choice(PERIOD_DISTRIBUTION)


def random_periodic_period():
    """Return a concrete positive activation period.

    Event/angle-synchronous tasks use period zero in the JSON model and must be
    activated through dependencies. Roots and independent tasks therefore need a
    concrete periodic release pattern.
    """
    period = random_period()
    while period == "event_angle_sync":
        period = random_period()
    return period


def random_domain() -> str:
    return weighted_choice(DOMAIN_DISTRIBUTIONS)


def random_task_name(domain: str, task_index: int) -> str:
    prefix = random.choice(TASK_NAME_PREFIXES_BY_DOMAIN[domain])
    return f"{prefix}_{task_index:04d}"


def random_memory_usage_kb(domain: str) -> int:
    buckets = memory_usage_kb_by_domain(domain)
    low_high = weighted_choice(buckets)
    return random.randint(low_high[0], low_high[1])


def random_activation_patterns_per_chain() -> int:
    return weighted_choice(ACTIVATION_PATTERN_DISTRIBUTION)


def random_chain_size() -> int:
    return weighted_choice(CHAIN_LENGTH_DISTRIBUTION)


####################################################
# Task set generation
####################################################


def create_runnable(
    task_id: str,
    task_index: int,
    period,
    required_domain: str,
    dependencies: Optional[List[str]],
) -> Dict:
    duration_us = round(sample_weibull_us(period), ndigits=2)
    json_period = 0 if period == "event_angle_sync" else period

    return {
        "id": task_id,
        "name": random_task_name(required_domain, task_index),
        "period": json_period,
        "wcet": duration_us,
        "memoryUsageKB": random_memory_usage_kb(required_domain),
        "requiredDomain": required_domain,
        "eligibleCores": [],
        "dependencies": dependencies or [],
    }


def generate_chain(
    start_index: int,
    remaining_capacity: int,
) -> List[Dict]:
    """Generate one dependency chain within the remaining task budget.

    The previous implementation passed the number of remaining slots as
    max_tasks and then subtracted start_index again. Once start_index exceeded the
    remaining slot count, this could prevent additional chains from being
    generated. This version treats remaining_capacity as the actual remaining
    number of task templates that may still be emitted.
    """
    tasks: List[Dict] = []

    num_patterns = random_activation_patterns_per_chain()
    total_chain_length = sum(random_chain_size() for _ in range(num_patterns))
    total_chain_length = min(total_chain_length, remaining_capacity)

    if total_chain_length <= 0:
        return tasks

    root_period = random_periodic_period()
    domain = random_domain()
    previous_id = None

    for offset in range(total_chain_length):
        task_index = start_index + offset
        task_id = f"r_{task_index:04d}"

        if offset == 0:
            period = root_period
            dependencies = []
        else:
            period = "event_angle_sync"
            dependencies = [previous_id]

        task = create_runnable(
            task_id=task_id,
            task_index=task_index,
            period=period,
            required_domain=domain,
            dependencies=dependencies,
        )
        tasks.append(task)
        previous_id = task_id

    return tasks


def generate_independent_tasks(task_index: int) -> Dict:
    """Generate an independent runnable with a concrete activation period.

    Independent event/angle-synchronous runnables have no predecessor and
    therefore no activation source. They are avoided here so that every generated
    task is either periodically released itself or activated through a chain
    dependency.
    """
    period = random_periodic_period()
    domain = random_domain()

    return create_runnable(
        task_id=f"r_{task_index:04d}",
        task_index=task_index,
        period=period,
        required_domain=domain,
        dependencies=[],
    )


def generate_taskset(num_tasks: int) -> Dict:
    tasks: List[Dict] = []
    next_index = 0

    target_num_chains = min(random.randint(30, 60), max(1, num_tasks // 2))

    for _ in range(target_num_chains):
        remaining = num_tasks - len(tasks)
        if remaining <= 0:
            break

        chain = generate_chain(
            start_index=next_index,
            remaining_capacity=remaining,
        )

        if not chain:
            break

        tasks.extend(chain)
        next_index += len(chain)

    while len(tasks) < num_tasks:
        task = generate_independent_tasks(task_index=next_index)
        tasks.append(task)
        next_index += 1

    return {"tasks": tasks}


def write_taskset(output_dir: str, filename: str, taskset: Dict, soc_template: dict) -> str:
    os.makedirs(output_dir, exist_ok=True)

    # Deep-copy so nested platform/config structures from the template cannot be
    # mutated accidentally across calls when this module is used from a pipeline.
    body = copy.deepcopy(soc_template)
    body["tasks"] = taskset["tasks"]

    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)

    return output_path


def int_arg_range(mini, maxi):
    def range_limited_int_type(arg):
        try:
            value = int(arg)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Must be an integer") from exc

        if value < mini or value > maxi:
            raise argparse.ArgumentTypeError(
                f"Argument must be between {mini} and {maxi}, got {value}."
            )

        return value

    return range_limited_int_type


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate WATERS15-inspired RunSoC 2.0 taskset JSON files."
    )

    parser.add_argument(
        "--filename",
        type=str,
        default="taskset.json",
        help="Name of the taskset JSON file to generate.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where output will be written.",
    )
    parser.add_argument(
        "--soc-template",
        type=Path,
        default=Path("../../../04_Evalution/default-soc.json"),
        help="Path to the template JSON file for the SoC.",
    )
    parser.add_argument(
        "--num_tasks",
        type=int,
        default=100,
        help="Size of the taskset.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible workload generation.",
    )
    parser.add_argument(
        "--platform-key",
        type=str,
        default=None,
        help="Optional normalized platform key stored in the evaluation metadata.",
    )

    return parser.parse_args()


def main(
    filename: str,
    output_dir: Path,
    soc_template: Path,
    num_tasks: int,
    seed: Optional[int] = None,
    platform_key: Optional[str] = None,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    if seed is not None:
        random.seed(seed)

    taskset = generate_taskset(num_tasks)

    with open(soc_template, "r", encoding="utf-8") as f:
        soc_data = json.load(f)

    output_path = output_dir / filename
    soc_data.setdefault("evaluation", {})
    soc_data["evaluation"].update(
        {
            "taskset_id": output_path.stem,
            "platform_key": platform_key,
            "platform_name": soc_data.get("platform", {}).get("name"),
            "source_file": str(output_path),
            "seed": seed,
            "task_template_count": num_tasks,
        }
    )

    output_path = write_taskset(
        output_dir=str(output_dir),
        filename=filename,
        taskset=taskset,
        soc_template=soc_data,
    )
    print(f"Generated {num_tasks} runnables in {output_path}")


if __name__ == "__main__":
    args = parse_args()
    main(
        filename=args.filename,
        output_dir=args.output_dir,
        soc_template=args.soc_template,
        num_tasks=args.num_tasks,
        seed=args.seed,
        platform_key=args.platform_key,
    )
