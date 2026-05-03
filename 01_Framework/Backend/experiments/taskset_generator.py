import argparse
import json
import os
import random
from pathlib import Path
from typing import Dict, Optional, List

from WATERS15_distributions import PERIOD_DISTRIBUTION, ACTIVATION_PATTERN_DISTRIBUTION, sample_weibull_us, \
    CHAIN_LENGTH_DISTRIBUTION
from domain_taskname_distributions import DOMAIN_DISTRIBUTIONS, TASK_NAME_PREFIXES_BY_DOMAIN, memory_usage_kb_by_domain


###################################
# UTIL
###################################
def weighted_choice(weighted_items):
    values = [x[0] for x in weighted_items]
    weights = [x[1] for x in weighted_items]
    return random.choices(values, weights=weights, k=1)[0]


def random_period():
    return weighted_choice(PERIOD_DISTRIBUTION)


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
        max_tasks: int,
) -> List[Dict]:
    tasks = []

    num_patterns = random_activation_patterns_per_chain()
    total_chain_length = sum(random_chain_size() for _ in range(num_patterns))
    total_chain_length = min(total_chain_length, max_tasks - start_index)

    if total_chain_length < 0:
        return tasks

    root_period = random_period()
    if root_period == "event_angle_sync":
        root_period = random.choice([1000, 2000, 5000, 10_000, 20_000, 50_000, 100_000, 200_000, 1_000_000])

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


def generate_independent_tasks(task_index):
    period = random_period()
    if period == "event_angle_sync":
        pass
    domain = random_domain()
    return create_runnable(
        task_id=f"r_{task_index:04d}",
        task_index=task_index,
        period=period,
        required_domain=domain,
        dependencies=[],
    )


def generate_taskset(num_tasks: int):
    tasks = []
    next_index = 0

    target_num_chains = min(random.randint(30, 60), max(1, num_tasks // 2))

    for _ in range(target_num_chains):
        remaining = num_tasks - len(tasks)
        if remaining <= 0:
            break

        chain = generate_chain(
            start_index=next_index,
            max_tasks=remaining,
        )
        tasks.extend(chain)
        next_index += len(chain)

    while len(tasks) < num_tasks:
        task = generate_independent_tasks(task_index=next_index)
        tasks.append(task)
        next_index += 1

    result = {"tasks": tasks}

    return result

def write_taskset(output_dir: str, filename: str, taskset: Dict, soc_template: dict) -> str:
    os.makedirs(output_dir, exist_ok=True)

    body = soc_template.copy()
    body["tasks"] = taskset["tasks"]
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)

    return output_path


def int_arg_range(mini, maxi):
    def range_limited_int_type(arg):
        try:
            f = int(arg)
        except ValueError:
            raise argparse.ArgumentTypeError("Must be a floating point number")
        if f < mini or f > maxi:
            raise argparse.ArgumentTypeError("Argument must be < " + str(mini) + "and > " + str(maxi))
        return f
    return range_limited_int_type

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run taskset JSON files against selected solvers."
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
        default=None
    )

    return parser.parse_args()

if __name__ == "__main__":
    # read command line arguments
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    taskset = generate_taskset(args.num_tasks)

    soc_template = json.load(open(args.soc_template, "r"))

    output_path = write_taskset(
        output_dir=args.output_dir,
        filename=args.filename,
        taskset=taskset,
        soc_template=soc_template,
    )

    print(f"Generated {args.num_tasks} runnables in {output_path}")
