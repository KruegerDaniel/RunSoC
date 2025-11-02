from __future__ import annotations

import os
import json
import matplotlib.pyplot as plt

from runnable_sets import RUNNABLE_SETS_50
from main_scheduler import (
    run_main_scheduler,
    average_wait_per_execution,
    _load_runnable_sets_from_json,
)


def ensure_output_dirs() -> tuple[str, str]:
    output_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "../../Images/backend")
    )
    os.makedirs(output_dir, exist_ok=True)
    sets_dir = os.path.join(output_dir, "runnable_sets_json")
    os.makedirs(sets_dir, exist_ok=True)
    return output_dir, sets_dir


def load_or_generate_sets(sets_dir: str):
    runnable_sets = _load_runnable_sets_from_json(sets_dir)
    if not runnable_sets:
        runnable_sets = RUNNABLE_SETS_50
        for idx, rset in enumerate(runnable_sets, start=1):
            with open(os.path.join(sets_dir, f"runnable_set_{idx:02d}.json"), "w") as f:
                json.dump(rset, f, indent=2)
    return runnable_sets


def compute_averages(runnable_sets):
    sweep_cores = [1, 2, 3, 4, 5, 6]
    sum_dynamic_fcfs = [0.0 for _ in sweep_cores]
    sum_dynamic_pas = [0.0 for _ in sweep_cores]
    sum_static_fcfs = [0.0 for _ in sweep_cores]
    sum_static_pas = [0.0 for _ in sweep_cores]
    n_sets = float(len(RUNNABLE_SETS_50))

    for testing_runnables in runnable_sets:
        # Dynamic policies
        for i, cores in enumerate(sweep_cores):
            sched_d_fcfs, _, extra_d_fcfs = run_main_scheduler(
                testing_runnables,
                num_cores=cores,
                scheduling_policy="fcfs",
                allocation_policy="dynamic",
                I=3,
            )
            sum_dynamic_fcfs[i] += average_wait_per_execution(
                sched_d_fcfs, extra_d_fcfs)

            sched_d_pas, _, extra_d_pas = run_main_scheduler(
                testing_runnables,
                num_cores=cores,
                scheduling_policy="pas",
                allocation_policy="dynamic",
                I=3,
            )
            sum_dynamic_pas[i] += average_wait_per_execution(
                sched_d_pas, extra_d_pas)

        # Static policies
        for i, cores in enumerate(sweep_cores):
            sched_s_fcfs, _, extra_s_fcfs = run_main_scheduler(
                testing_runnables,
                num_cores=cores,
                scheduling_policy="fcfs",
                allocation_policy="static",
                I=3,
            )
            sum_static_fcfs[i] += average_wait_per_execution(
                sched_s_fcfs, extra_s_fcfs)

            sched_s_pas, _, extra_s_pas = run_main_scheduler(
                testing_runnables,
                num_cores=cores,
                scheduling_policy="pas",
                allocation_policy="static",
                I=3,
            )
            sum_static_pas[i] += average_wait_per_execution(
                sched_s_pas, extra_s_pas)

    avg_dynamic_fcfs = [v / n_sets for v in sum_dynamic_fcfs]
    avg_dynamic_pas = [v / n_sets for v in sum_dynamic_pas]
    avg_static_fcfs = [v / n_sets for v in sum_static_fcfs]
    avg_static_pas = [v / n_sets for v in sum_static_pas]

    return sweep_cores, avg_dynamic_fcfs, avg_dynamic_pas, avg_static_fcfs, avg_static_pas


def compute_y_limits(*series_lists):
    y_values_all = []
    for series in series_lists:
        y_values_all.extend(series)
    if y_values_all:
        y_min = min(y_values_all)
        y_max = max(y_values_all)
        margin = 0.05 * (y_max - y_min) if y_max > y_min else 1.0
        return y_min - margin, y_max + margin
    return 0.0, 1.0


def plot_and_save(output_dir: str, sweep_cores, avg_dynamic_fcfs, avg_dynamic_pas, avg_static_fcfs, avg_static_pas):
    y_lower, y_upper = compute_y_limits(
        avg_dynamic_fcfs, avg_dynamic_pas, avg_static_fcfs, avg_static_pas
    )

    # Dynamic plot
    plt.figure(figsize=(10, 6))
    plt.plot(sweep_cores, avg_dynamic_fcfs,
             marker="o", linewidth=2, label="FCFS")
    plt.plot(sweep_cores, avg_dynamic_pas,
             marker="s", linewidth=2, label="PAS")
    plt.xlabel("Number of cores", fontsize=14)
    plt.ylabel("Average waiting time (ms)", fontsize=14)
    plt.title(
        "Dynamic allocation: Average waiting time (mean over 50 sets)", fontsize=16
    )
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.ylim(y_lower, y_upper)
    plt.savefig(
        os.path.join(
            output_dir, "dynamic_avg_wait_vs_cores_fcfs_pas_mean.pdf"),
        format="pdf",
        dpi=1200,
    )

    # Static plot
    plt.figure(figsize=(10, 6))
    plt.plot(sweep_cores, avg_static_fcfs,
             marker="o", linewidth=2, label="FCFS")
    plt.plot(sweep_cores, avg_static_pas, marker="s", linewidth=2, label="PAS")
    plt.xlabel("Number of cores", fontsize=14)
    plt.ylabel("Average waiting time (ms)", fontsize=14)
    plt.title(
        "Static allocation: Average waiting time (mean over 50 sets)", fontsize=16
    )
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.ylim(y_lower, y_upper)
    plt.savefig(
        os.path.join(output_dir, "static_avg_wait_vs_cores_fcfs_pas_mean.pdf"),
        format="pdf",
        dpi=1200,
    )


def main():
    output_dir, sets_dir = ensure_output_dirs()
    runnable_sets = load_or_generate_sets(sets_dir)
    sweep_cores, avg_d_fcfs, avg_d_pas, avg_s_fcfs, avg_s_pas = compute_averages(
        runnable_sets
    )
    plot_and_save(output_dir, sweep_cores, avg_d_fcfs,
                  avg_d_pas, avg_s_fcfs, avg_s_pas)


if __name__ == "__main__":
    main()
