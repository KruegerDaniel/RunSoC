import matplotlib.pyplot as plt
import networkx as nx

# Define runnables with execution times and CPU affinities
runnables = {
    'CameraCapture': {'time': 3, 'affinity': 0},
    'ImagePreprocessing': {'time': 4, 'affinity': 1},
    'LineDetection': {'time': 2, 'affinity': 1},
    'RadarCapture': {'time': 2, 'affinity': 0},
    'ObjectSegmentation': {'time': 3, 'affinity': 1},
    'ObstacleClassification': {'time': 2, 'affinity': 1},
}

# Dependencies: Directed edges in DAG
dependencies = {
    'CameraCapture': [],
    'ImagePreprocessing': ['CameraCapture'],
    'LineDetection': ['ImagePreprocessing'],
    'RadarCapture': [],
    'ObjectSegmentation': ['RadarCapture'],
    'ObstacleClassification': ['ObjectSegmentation'],
}

# CPUs
num_cpus = 2

# Build DAG
dag = nx.DiGraph()
for runnable, deps in dependencies.items():
    for dep in deps:
        dag.add_edge(dep, runnable)

# Visualize DAG
plt.figure(figsize=(10, 6))
pos = nx.spring_layout(dag)
nx.draw(dag, pos, with_labels=True, node_color='lightblue',
        node_size=2000, arrowsize=20, font_size=10, font_weight='bold')
plt.title("Task Dependencies DAG")
plt.show()

# Topological sort
topo_sorted = list(nx.topological_sort(dag))

# Helper function to compute critical path length for each node


def compute_critical_path_lengths(graph, times):
    critical_lengths = {}

    def dfs(node):
        if node in critical_lengths:
            return critical_lengths[node]
        successors = list(graph.successors(node))
        if not successors:
            critical_lengths[node] = times[node]
        else:
            max_succ = max(dfs(s) for s in successors)
            critical_lengths[node] = times[node] + max_succ
        return critical_lengths[node]

    for node in graph.nodes:
        dfs(node)

    return critical_lengths


# Execution time lookup
exec_times = {k: v['time'] for k, v in runnables.items()}

# Compute critical path lengths
critical_lengths = compute_critical_path_lengths(dag, exec_times)

# Sort runnables by descending criticality
critical_sorted = sorted(exec_times.keys(), key=lambda x: -critical_lengths[x])

# Scheduling function


def schedule(runnables_order):
    cpu_timeline = [[] for _ in range(num_cpus)]
    cpu_time = [0] * num_cpus
    start_times = {}

    for r in runnables_order:
        deps = dependencies[r]
        ready_time = max([start_times[d] + runnables[d]['time']
                         for d in deps] or [0])
        preferred_cpu = runnables[r]['affinity']
        earliest_cpu = min(
            range(num_cpus), key=lambda c: max(cpu_time[c], ready_time))
        assigned_cpu = preferred_cpu if cpu_time[preferred_cpu] <= ready_time else earliest_cpu
        start_time = max(cpu_time[assigned_cpu], ready_time)
        cpu_timeline[assigned_cpu].append(
            (r, start_time, start_time + runnables[r]['time']))
        cpu_time[assigned_cpu] = start_time + runnables[r]['time']
        start_times[r] = start_time
    return cpu_timeline


# Schedule using FCFS and Dependency-aware
schedule_fcfs = schedule(topo_sorted)
schedule_critical = schedule(critical_sorted)

print("\nFCFS Schedule:")
for cpu_idx, tasks in enumerate(schedule_fcfs):
    print(f"CPU {cpu_idx}:")
    for task, start, end in tasks:
        print(f"  {task}: {start}-{end}")

print("\nCritical Path Schedule:")
for cpu_idx, tasks in enumerate(schedule_critical):
    print(f"CPU {cpu_idx}:")
    for task, start, end in tasks:
        print(f"  {task}: {start}-{end}")

# Helper function to plot Gantt chart for a given schedule


def plot_gantt(schedule, title):
    colors = ['skyblue', 'lightgreen', 'salmon', 'orange', 'plum', 'khaki']
    fig, ax = plt.subplots(figsize=(10, 4))
    for cpu_id, tasks in enumerate(schedule):
        for idx, (runnable, start, end) in enumerate(tasks):
            ax.barh(cpu_id, end - start, left=start,
                    color=colors[idx % len(colors)], edgecolor='black')
            ax.text((start + end) / 2, cpu_id, runnable, va='center',
                    ha='center', fontsize=9, color='black')

    ax.set_yticks(range(len(schedule)))
    ax.set_yticklabels([f'CPU {i}' for i in range(len(schedule))])
    ax.set_xlabel('Time (ms)')
    ax.set_title(title)
    ax.grid(True)
    plt.tight_layout()
    plt.show()


# Plot Gantt charts for both schedules
plot_gantt(schedule_fcfs, "Gantt Chart - FCFS Scheduling")
plot_gantt(schedule_critical, "Gantt Chart - Dependency-Aware Scheduling")
