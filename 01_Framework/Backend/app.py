import base64
import heapq
import io
import json
import os
import sys
from collections import defaultdict

import matplotlib
import matplotlib.pyplot as plt
from criticality.criticality import run_criticality
from fcfs.fcfs import run_fcfs_affinity
from flask import Flask, jsonify, request
from flask_cors import CORS
from shared_log import SharedExecutionLog

matplotlib.use('Agg')  # Use non-interactive backend

# Add current directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


app = Flask(__name__)
CORS(app)


def run_scheduling(runnables, num_cores, simulation_time_ms=400):
    """Run the scheduling algorithm with given runnables and number of cores."""

    event_queue = []
    heapq.heapify(event_queue)

    last_output = defaultdict(lambda: (-1, -1))
    execution_log = SharedExecutionLog()
    task_instance_counter = defaultdict(int)
    dependency_instance = defaultdict(lambda: defaultdict(int))
    completed_instances = defaultdict(int)
    event_task_instance_counter = defaultdict(int)

    CPU_FREE_TIME = 0

    def schedule_periodic_runnables():
        """Schedule all periodic runnables up to the simulation time limit."""
        for name, props in runnables.items():
            if props['type'] == 'periodic':
                time = 0
                counter = 0
                while time <= simulation_time_ms:
                    heapq.heappush(
                        event_queue, (time, name, props['execution_time'], counter))
                    time += props['period']
                    counter += 1

    def is_dependencies_ready(runnable, current_instance):
        """Check if all dependencies of a runnable have completed by the current time."""
        deps = runnables[runnable].get('deps', [])
        return all(completed_instances[dep] > current_instance for dep in deps)

    def schedule_event_runnables(triggered, current_time):
        """Schedule all event-based tasks that are triggered by the given events."""
        for name, props in runnables.items():
            if props['type'] != 'event':
                continue

            if not set(props.get('deps', [])) & set(triggered):
                continue

            available_instances = [completed_instances[dep]
                                   for dep in props['deps']]
            min_completed = min(available_instances)
            current_count = event_task_instance_counter[name]

            if min_completed > current_count:
                current_instance = current_count
                total_delay = sum(exec_time for sched_time, _, exec_time,
                                  _ in event_queue if sched_time < current_time)
                heapq.heappush(event_queue, (current_time + total_delay,
                               name, props['execution_time'], current_instance))
                event_task_instance_counter[name] += 1

                for dep in props['deps']:
                    dependency_instance[name][dep] = completed_instances[dep] - 1

    # Run the scheduling
    schedule_periodic_runnables()

    while event_queue and CPU_FREE_TIME < simulation_time_ms:
        scheduled_time, task, execution_time, instance = heapq.heappop(
            event_queue)

        actual_start_time = max(CPU_FREE_TIME, scheduled_time)
        finish_time = actual_start_time + execution_time
        CPU_FREE_TIME = finish_time

        last_output[task] = (finish_time, instance)
        completed_instances[task] = instance + 1
        execution_log.append(
            (actual_start_time, finish_time, task, instance, runnables[task]['affinity']))

        schedule_event_runnables([task], finish_time)

    return execution_log, CPU_FREE_TIME


def create_gantt_chart(execution_log, title="Gantt Chart of Core Scheduling"):
    """Create a Gantt chart from the execution log and return as base64 string, with y-axis as cores."""
    filtered_log = [(start, end, task, instance, affinity)
                    for start, end, task, instance, affinity in execution_log.get_log()]

    if not filtered_log:
        return None

    import matplotlib.patches as mpatches

    cores = sorted(set(affinity for *_, affinity in filtered_log), key=str)
    tasks = sorted(set(task for _, _, task, _, _ in filtered_log))
    color_palette = plt.cm.get_cmap("tab20", len(tasks))
    task_colors = {task: color_palette(i) for i, task in enumerate(tasks)}
    y_positions = {core: i for i, core in enumerate(cores)}

    fig, ax = plt.subplots(figsize=(12, 6))

    for start, end, task, instance, core in filtered_log:
        ax.barh(y_positions[core], end - start, left=start,
                color=task_colors[task], edgecolor="black")
        ax.text(start + (end - start) / 2,
                y_positions[core], task, va='center', ha='center', color='white', fontsize=8)

    ax.set_yticks(range(len(cores)))
    ax.set_yticklabels([f"Core {core}" for core in cores])
    ax.set_xlabel("Time (ms)")
    ax.set_title(title)
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)
    handles = [mpatches.Patch(color=color, label=task)
               for task, color in task_colors.items()]
    ax.legend(handles=handles, bbox_to_anchor=(1.05, 1),
              loc='upper left', title="Runnables")

    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', dpi=300)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return plot_url


def normalize_runnables(runnables):
    for name, props in runnables.items():
        for key in ['period', 'execution_time', 'criticality', 'affinity']:
            if key in props:
                props[key] = int(props[key])
        if 'deps' in props and isinstance(props['deps'], list):
            props['deps'] = [str(dep) for dep in props['deps']]
    return runnables


@app.route('/api/schedule', methods=['POST'])
def schedule():
    """API endpoint to run scheduling with given runnables and number of cores."""
    try:
        data = request.get_json()
        print('Received data:', data)  # Debug print
        runnables = data.get('runnables', {})
        num_cores = int(data.get('numCores', 1))
        simulation_time = int(data.get('simulationTime', 400))
        algorithm = data.get('algorithm', 'all')

        runnables = normalize_runnables(runnables)

        if not runnables:
            print('No runnables provided!')  # Debug print
            return jsonify({'error': 'No runnables provided'}), 400

        results = {}

        if algorithm in ('all', 'fcfs'):
            execution_log_fcfs, total_execution_time_fcfs = run_fcfs_affinity(
                runnables, num_cores, simulation_time
            )
            plot_data_fcfs = create_gantt_chart(
                execution_log_fcfs, title="FCFS Gantt Chart")
            log_entries_fcfs = [
                {
                    'start': start,
                    'end': end,
                    'task': task,
                    'instance': instance,
                    'affinity': affinity
                }
                for start, end, task, instance, affinity in execution_log_fcfs.get_log()
            ]
            results['fcfs'] = {
                'totalExecutionTime': total_execution_time_fcfs,
                'executionLog': log_entries_fcfs,
                'ganttChart': plot_data_fcfs
            }

        if algorithm in ('all', 'criticality'):
            execution_log_crit, total_execution_time_crit = run_criticality(
                runnables, num_cores, simulation_time
            )
            plot_data_crit = create_gantt_chart(
                execution_log_crit, title="Criticality Gantt Chart")
            log_entries_crit = [
                {
                    'start': start,
                    'end': end,
                    'task': task,
                    'instance': instance,
                    'affinity': affinity
                }
                for start, end, task, instance, affinity in execution_log_crit.get_log()
            ]
            results['criticality'] = {
                'totalExecutionTime': total_execution_time_crit,
                'executionLog': log_entries_crit,
                'ganttChart': plot_data_crit
            }

        if algorithm == 'all':
            return jsonify({'success': True, 'results': results})
        if algorithm == 'fcfs':
            return jsonify({'success': True, **results['fcfs']})
        if algorithm == 'criticality':
            return jsonify({'success': True, **results['criticality']})

        return jsonify({'error': 'Unknown algorithm'}), 400

    except Exception as e:
        print('Exception in /api/schedule:', e)  # Debug print
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
