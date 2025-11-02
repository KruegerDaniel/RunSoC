# scheduling_service.py
import matplotlib
matplotlib.use('Agg')

from typing import Dict, Any, Tuple

from scheduling.fcfs.fcfs import run_fcfs_affinity
from scheduling.criticality.criticality import run_criticality
from scheduling.main_scheduler import run_main_scheduler
from utils.converters import normalize_runnables, to_main_tasks
from utils.gantt import create_gantt_chart, create_gantt_chart_from_main



def run_scheduling_request(data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Main entrypoint for the HTTP layer.
    Input: raw JSON dict from the request.
    Output: (payload, http_status)
    """
    runnables = data.get('runnables', {})
    num_cores = int(data.get('numCores', 1))
    simulation_time = int(data.get('simulationTime', 400))
    algorithm = data.get('algorithm', 'all')
    allocation_policy = data.get('allocationPolicy', 'static')
    scheduling_policy = data.get('schedulingPolicy', '../scheduling/fcfs')

    runnables = normalize_runnables(runnables)

    if not runnables:
        return {'error': 'No runnables provided'}, 400

    results: Dict[str, Any] = {}

    # 1) FCFS (old)
    if algorithm in ('all', 'fcfs'):
        exec_log_fcfs, total_time_fcfs = run_fcfs_affinity(
            runnables, num_cores, simulation_time
        )
        gantt_fcfs = create_gantt_chart(exec_log_fcfs, title="FCFS Gantt Chart")
        results['fcfs'] = {
            'totalExecutionTime': total_time_fcfs,
            'executionLog': [
                {
                    'start': start,
                    'end': end,
                    'task': task,
                    'instance': instance,
                    'affinity': affinity,
                }
                for start, end, task, instance, affinity in exec_log_fcfs.get_log()
            ],
            'ganttChart': gantt_fcfs,
        }

    # 2) Criticality
    if algorithm in ('all', 'criticality'):
        exec_log_crit, total_time_crit = run_criticality(
            runnables, num_cores, simulation_time
        )
        gantt_crit = create_gantt_chart(
            exec_log_crit, title="Criticality Gantt Chart"
        )
        results['criticality'] = {
            'totalExecutionTime': total_time_crit,
            'executionLog': [
                {
                    'start': start,
                    'end': end,
                    'task': task,
                    'instance': instance,
                    'affinity': affinity,
                }
                for start, end, task, instance, affinity in exec_log_crit.get_log()
            ],
            'ganttChart': gantt_crit,
        }

    # 3) Main scheduler (your static/dynamic)
    if algorithm in ('all', 'main'):
        tasks_for_main = to_main_tasks(runnables)
        schedule_entries, finish_time, extra_wait = run_main_scheduler(
            tasks_for_main,
            num_cores,
            scheduling_policy=scheduling_policy,
            allocation_policy=allocation_policy,
        )
        gantt_main = create_gantt_chart_from_main(
            schedule_entries,
            title=f"Main Scheduler ({allocation_policy})"
        )
        results['main'] = {
            'totalExecutionTime': finish_time,
            'extraWait': extra_wait,
            'allocationPolicy': allocation_policy,
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
        }

    # single algorithm responses
    if algorithm == 'fcfs':
        return {'success': True, **results['fcfs']}, 200
    if algorithm == 'criticality':
        return {'success': True, **results['criticality']}, 200
    if algorithm == 'main':
        return {'success': True, **results['main']}, 200
    if algorithm == 'all':
        return {'success': True, 'results': results}, 200

    return {'error': 'Unknown algorithm'}, 400
