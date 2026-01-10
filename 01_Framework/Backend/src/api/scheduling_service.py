# scheduling_service.py
import matplotlib
matplotlib.use('Agg')

from typing import Dict, Any, Tuple

from scheduling.main_scheduler import run_main_scheduler
from utils.converters import normalize_runnables, to_main_tasks
from utils.gantt import create_gantt_chart_from_main


def run_scheduling_request(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    runnables = data.get('runnables', {})
    num_cores = int(data.get('numCores', 1))
    simulation_time = int(data.get('simulationTime', 400))

    algorithm = str(data.get('algorithm', 'main')).lower()
    if algorithm not in ('main', 'all'):
        return {'error': 'Unknown algorithm, use "main" or "all"'}, 400

    runnables = normalize_runnables(runnables)
    if not runnables:
        return {'error': 'No runnables provided'}, 400

    tasks_for_main = to_main_tasks(runnables)
    all_task_names = set(tasks_for_main.keys())

    sched_mode = str(data.get('schedulingPolicy', 'fcfs')).lower()
    alloc_mode = str(data.get('allocationPolicy', 'static')).lower()

    if algorithm == 'all':
        sched_policies = ['fcfs', 'pas']
        alloc_policies = ['static', 'dynamic']
    else:
        if sched_mode in ('both', 'all'):
            sched_policies = ['fcfs', 'pas']
        else:
            sched_policies = [sched_mode]

        if alloc_mode in ('both', 'all'):
            alloc_policies = ['static', 'dynamic']
        else:
            alloc_policies = [alloc_mode]

    results: Dict[str, Dict[str, Any]] = {}

    for sched_policy in sched_policies:
        sched_key = sched_policy.lower()
        results[sched_key] = {}
        for alloc_policy in alloc_policies:
            alloc_key = alloc_policy.lower()

            schedule_entries, finish_time, extra_wait = run_main_scheduler(
                tasks_for_main,
                num_cores,
                scheduling_policy=sched_key,
                allocation_policy=alloc_key,
            )

            executed_task_names = {e.task for e in schedule_entries}
            non_executed_tasks = sorted(all_task_names - executed_task_names)

            gantt_main = create_gantt_chart_from_main(
                schedule_entries,
                title=f"Main Scheduler ({sched_key.upper()}, {alloc_key})"
            )

            results[sched_key][alloc_key] = {
                'totalExecutionTime': finish_time,
                'extraWait': extra_wait,
                'schedulingPolicy': sched_key,
                'allocationPolicy': alloc_key,
                'executionLog': [
                    {
                        'start': e.start_time,
                        'end': e.finish_time,
                        'task': e.task,
                        'eligibleTime': e.eligible_time,
                        'core': e.core,
                    }
                    for e in schedule_entries
                ],
                'ganttChart': gantt_main,
                'nonExecutedTasks': non_executed_tasks,
                'allTasks': sorted(all_task_names),
            }

    return {
        'success': True,
        'results': results,
    }, 200
