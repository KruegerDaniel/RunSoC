'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
    ClockIcon,
    DotsHorizontalIcon,
    LightningBoltIcon,
    Link2Icon,
    Pencil1Icon,
    PlusIcon,
    TrashIcon,
} from '@radix-ui/react-icons';
import ReactFlow, {
    Background,
    Controls,
    Edge,
    Handle,
    MarkerType,
    Node,
    NodeMouseHandler,
    NodeProps,
    Position,
    ReactFlowInstance,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { useJsonModel } from '@/lib/JsonModelContext';
import type { Communication, Task } from '@/lib/types/mpsoc';

type TaskLinkKind = 'dependency' | 'communication';

type TaskLink = {
    id: string;
    kind: TaskLinkKind;
    source: string;
    target: string;
    penalty?: number;
    notes?: string;
    dependencyIndex?: number;
    communicationIndex?: number;
};

type TaskDialogState = {
    mode: 'add' | 'edit';
    task: Task;
};

type LinkDialogState = {
    mode: 'add' | 'edit';
    link: TaskLink;
};

type PendingDelete =
    | { kind: 'task'; taskId: string }
    | { kind: 'link'; link: TaskLink }
    | null;

type DropdownState =
    | { kind: 'task'; id: string }
    | { kind: 'link'; id: string }
    | null;

type TaskNodeData = {
    task: Task;
};

function TaskFlowNode({ data, selected }: NodeProps<TaskNodeData>) {
    const taskType = getTaskType(data.task);
    const Icon = taskType === 'periodic' ? ClockIcon : LightningBoltIcon;
    const memory = getMemoryValue(data.task);
    const executionTime = getExecutionTime(data.task);

    return (
        <div
            style={{
                width: 220,
                minHeight: 98,
                border: selected ? '2px solid #2563eb' : '1px solid #b9c4d4',
                borderRadius: 8,
                background: '#fff',
                boxShadow: selected
                    ? '0 8px 22px rgba(37, 99, 235, 0.18)'
                    : '0 3px 10px rgba(15, 23, 42, 0.10)',
                padding: '12px 14px',
                fontFamily: 'Arial, sans-serif',
                boxSizing: 'border-box',
            }}
        >
            <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />

            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    marginBottom: 10,
                }}
            >
                <div style={{ minWidth: 0 }}>
                    <div
                        style={{
                            fontSize: 15,
                            fontWeight: 700,
                            color: '#172033',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                        title={data.task.name || data.task.id}
                    >
                        {data.task.name || data.task.id}
                    </div>
                    <div
                        style={{
                            marginTop: 3,
                            fontSize: 12,
                            color: '#657084',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                        title={data.task.id}
                    >
                        {data.task.id}
                    </div>
                </div>

                <span
                    style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 28,
                        height: 28,
                        borderRadius: 6,
                        background: taskType === 'periodic' ? '#edf4ff' : '#fff7e8',
                        color: taskType === 'periodic' ? '#2563eb' : '#b45309',
                        flexShrink: 0,
                    }}
                    title={taskType}
                >
                    <Icon width={15} height={15} />
                </span>
            </div>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                    gap: 8,
                    fontSize: 12,
                }}
            >
                <Metric label="WCET" value={formatNumber(executionTime)} />
                <Metric
                    label="Period"
                    value={taskType === 'periodic' ? formatNumber(data.task.period) : '-'}
                />
                <Metric label="Memory" value={formatNumber(memory)} />
            </div>

            <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
        </div>
    );
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <div style={{ color: '#7b8494', marginBottom: 2 }}>{label}</div>
            <div
                style={{
                    color: '#172033',
                    fontWeight: 700,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
            >
                {value}
            </div>
        </div>
    );
}

const nodeTypes = {
    task: TaskFlowNode,
};

export default function TasksetDesigner() {
    const { model, setModel } = useJsonModel();
    const tasks = useMemo(() => model.tasks ?? [], [model.tasks]);
    const communications = useMemo(
        () => model.communications ?? [],
        [model.communications],
    );

    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [openDropdown, setOpenDropdown] = useState<DropdownState>(null);
    const [taskDialog, setTaskDialog] = useState<TaskDialogState | null>(null);
    const [linkDialog, setLinkDialog] = useState<LinkDialogState | null>(null);
    const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
    const rfRef = useRef<ReactFlowInstance | null>(null);

    const taskLinks = useMemo(
        () => buildTaskLinks(tasks, communications),
        [tasks, communications],
    );

    const { nodes, edges } = useMemo(
        () => buildTaskGraph(tasks, taskLinks, selectedTaskId),
        [tasks, taskLinks, selectedTaskId],
    );

    const selectedTask = selectedTaskId
        ? tasks.find((task) => task.id === selectedTaskId) ?? null
        : null;

    useEffect(() => {
        if (!selectedTaskId || !rfRef.current) return;

        const selectedNode = nodes.find((node) => node.id === selectedTaskId);
        if (!selectedNode) return;

        rfRef.current.setCenter(
            selectedNode.position.x + 110,
            selectedNode.position.y + 50,
            {
                zoom: 1.15,
                duration: 300,
            },
        );
    }, [nodes, selectedTaskId]);

    function updateTaskset(nextTasks: Task[], nextCommunications = communications) {
        setModel((current) => ({
            ...current,
            tasks: nextTasks,
            communications: nextCommunications,
        }));
    }

    function addTask() {
        setTaskDialog({
            mode: 'add',
            task: makeDefaultTask(tasks),
        });
    }

    function editTask(taskId: string) {
        const task = tasks.find((item) => item.id === taskId);
        if (!task) return;

        setTaskDialog({
            mode: 'edit',
            task,
        });
        setOpenDropdown(null);
    }

    function saveTask(task: Task, previousTaskId?: string) {
        const normalizedTask = normalizeTask(task);

        if (!normalizedTask.id) {
            window.alert('Task ID is required.');
            return;
        }

        if (!normalizedTask.name) {
            window.alert('Task name is required.');
            return;
        }

        if (getExecutionTime(normalizedTask) < 0) {
            window.alert('WCET must be a positive number.');
            return;
        }

        if (getTaskType(normalizedTask) === 'periodic' && !normalizedTask.period) {
            window.alert('Periodic tasks require a period.');
            return;
        }

        const duplicate = tasks.some(
            (item) => item.id === normalizedTask.id && item.id !== previousTaskId,
        );

        if (duplicate) {
            window.alert(`Task ID "${normalizedTask.id}" already exists.`);
            return;
        }

        const nextTasks = previousTaskId
            ? tasks.map((item) =>
                item.id === previousTaskId
                    ? replaceDependencyReferences(
                        normalizedTask,
                        previousTaskId,
                        normalizedTask.id,
                    )
                    : replaceDependencyReferences(
                        item,
                        previousTaskId,
                        normalizedTask.id,
                    ),
            )
            : [...tasks, normalizedTask];

        const nextCommunications = previousTaskId
            ? replaceCommunicationEndpoint(
                communications,
                previousTaskId,
                normalizedTask.id,
            )
            : communications;

        updateTaskset(nextTasks, nextCommunications);
        setSelectedTaskId(normalizedTask.id);
        setTaskDialog(null);
    }

    function deleteTask(taskId: string) {
        const nextTasks = tasks
            .filter((task) => task.id !== taskId)
            .map((task) => ({
                ...task,
                dependencies: (task.dependencies ?? []).filter((id) => id !== taskId),
            }));

        const nextCommunications = communications.filter(
            (comm) => comm.source !== taskId && comm.target !== taskId,
        );

        updateTaskset(nextTasks, nextCommunications);

        if (selectedTaskId === taskId) {
            setSelectedTaskId(null);
        }

        setOpenDropdown(null);
        setPendingDelete(null);
    }

    function addLink() {
        if (tasks.length < 2) {
            window.alert('Create at least two tasks before adding a task link.');
            return;
        }

        setLinkDialog({
            mode: 'add',
            link: {
                id: 'new-link',
                kind: 'dependency',
                source: tasks[0].id,
                target: tasks[1].id,
                penalty: 0,
            },
        });
    }

    function editLink(link: TaskLink) {
        setLinkDialog({
            mode: 'edit',
            link,
        });
        setOpenDropdown(null);
    }

    function saveLink(nextLink: TaskLink, previousLink?: TaskLink) {
        if (!nextLink.source || !nextLink.target) {
            window.alert('Source and target tasks are required.');
            return;
        }

        if (nextLink.source === nextLink.target) {
            window.alert('Source and target tasks must be different.');
            return;
        }

        if (!tasks.some((task) => task.id === nextLink.source)) {
            window.alert(`Source task "${nextLink.source}" does not exist.`);
            return;
        }

        if (!tasks.some((task) => task.id === nextLink.target)) {
            window.alert(`Target task "${nextLink.target}" does not exist.`);
            return;
        }

        const withoutPrevious = previousLink
            ? removeTaskLink(tasks, communications, previousLink)
            : { nextTasks: tasks, nextCommunications: communications };

        const existingLinks = buildTaskLinks(
            withoutPrevious.nextTasks,
            withoutPrevious.nextCommunications,
        );
        const duplicate = existingLinks.some(
            (link) =>
                link.kind === nextLink.kind &&
                link.source === nextLink.source &&
                link.target === nextLink.target,
        );

        if (duplicate) {
            window.alert(
                `${nextLink.kind === 'dependency' ? 'Dependency' : 'Communication'} link already exists.`,
            );
            return;
        }

        const saved = addTaskLink(
            withoutPrevious.nextTasks,
            withoutPrevious.nextCommunications,
            nextLink,
        );

        updateTaskset(saved.nextTasks, saved.nextCommunications);
        setLinkDialog(null);
    }

    function deleteLink(link: TaskLink) {
        const next = removeTaskLink(tasks, communications, link);
        updateTaskset(next.nextTasks, next.nextCommunications);
        setPendingDelete(null);
        setOpenDropdown(null);
    }

    const handleNodeClick: NodeMouseHandler = (_event, node) => {
        setSelectedTaskId(String(node.id));
    };

    return (
        <div style={pageStyle}>
            <section style={graphShellStyle}>
                <div style={graphHeaderStyle}>
                    <div>
                        <h1 style={pageTitleStyle}>Task Set</h1>
                        <p style={pageSubtitleStyle}>
                            {tasks.length} tasks · {taskLinks.length} task links
                        </p>
                    </div>

                    {selectedTask && (
                        <button
                            onClick={() => editTask(selectedTask.id)}
                            style={secondaryButtonStyle}
                        >
                            <Pencil1Icon />
                            Edit selected
                        </button>
                    )}
                </div>

                <div style={flowContainerStyle}>
                    {tasks.length === 0 ? (
                        <div style={emptyGraphStyle}>
                            <h2 style={{ margin: 0, fontSize: 18 }}>No tasks yet</h2>
                            <button onClick={addTask} style={primaryButtonStyle}>
                                <PlusIcon />
                                Add task
                            </button>
                        </div>
                    ) : (
                        <ReactFlow
                            nodes={nodes}
                            edges={edges}
                            nodeTypes={nodeTypes}
                            fitView
                            onInit={(instance) => {
                                rfRef.current = instance;
                                instance.fitView({ padding: 0.22 });
                            }}
                            onNodeClick={handleNodeClick}
                            nodesDraggable={false}
                            nodesConnectable={false}
                            elementsSelectable
                            zoomOnScroll
                        >
                            <Background />
                            <Controls />
                        </ReactFlow>
                    )}
                </div>
            </section>

            <aside style={sidebarStyle}>
                <Panel title="Tasks" onAction={addTask}>
                    {tasks.length === 0 ? (
                        <EmptyState label="No tasks defined." />
                    ) : (
                        tasks.map((task) => (
                            <ListEntry
                                key={task.id}
                                icon={
                                    getTaskType(task) === 'periodic' ? (
                                        <ClockIcon />
                                    ) : (
                                        <LightningBoltIcon />
                                    )
                                }
                                title={task.name || task.id}
                                subtitle={`${task.id} · ${getTaskType(task)} · WCET ${formatNumber(getExecutionTime(task))}`}
                                selected={selectedTaskId === task.id}
                                dropdownOpen={
                                    openDropdown?.kind === 'task' &&
                                    openDropdown.id === task.id
                                }
                                onSelect={() => setSelectedTaskId(task.id)}
                                onToggleDropdown={() =>
                                    setOpenDropdown(
                                        openDropdown?.kind === 'task' &&
                                            openDropdown.id === task.id
                                            ? null
                                            : { kind: 'task', id: task.id },
                                    )
                                }
                                onEdit={() => editTask(task.id)}
                                onDelete={() =>
                                    setPendingDelete({ kind: 'task', taskId: task.id })
                                }
                            />
                        ))
                    )}
                </Panel>

                <Panel title="Task Links" onAction={addLink}>
                    {taskLinks.length === 0 ? (
                        <EmptyState label="No task links defined." />
                    ) : (
                        taskLinks.map((link) => (
                            <ListEntry
                                key={link.id}
                                icon={<Link2Icon />}
                                title={`${link.source} -> ${link.target}`}
                                subtitle={
                                    link.kind === 'communication'
                                        ? `Communication · penalty ${link.penalty ?? 0}`
                                        : 'Dependency'
                                }
                                selected={false}
                                dropdownOpen={
                                    openDropdown?.kind === 'link' &&
                                    openDropdown.id === link.id
                                }
                                onSelect={() => setSelectedTaskId(link.target)}
                                onToggleDropdown={() =>
                                    setOpenDropdown(
                                        openDropdown?.kind === 'link' &&
                                            openDropdown.id === link.id
                                            ? null
                                            : { kind: 'link', id: link.id },
                                    )
                                }
                                onEdit={() => editLink(link)}
                                onDelete={() => setPendingDelete({ kind: 'link', link })}
                            />
                        ))
                    )}
                </Panel>
            </aside>

            {taskDialog && (
                <TaskDialog
                    state={taskDialog}
                    tasks={tasks}
                    onCancel={() => setTaskDialog(null)}
                    onSave={saveTask}
                />
            )}

            {linkDialog && (
                <TaskLinkDialog
                    state={linkDialog}
                    tasks={tasks}
                    onCancel={() => setLinkDialog(null)}
                    onSave={saveLink}
                />
            )}

            {pendingDelete && (
                <ConfirmDialog
                    pendingDelete={pendingDelete}
                    onCancel={() => setPendingDelete(null)}
                    onConfirm={() => {
                        if (pendingDelete.kind === 'task') {
                            deleteTask(pendingDelete.taskId);
                            return;
                        }

                        deleteLink(pendingDelete.link);
                    }}
                />
            )}
        </div>
    );
}

function TaskDialog({
    state,
    tasks,
    onCancel,
    onSave,
}: {
    state: TaskDialogState;
    tasks: Task[];
    onCancel: () => void;
    onSave: (task: Task, previousTaskId?: string) => void;
}) {
    const [task, setTask] = useState<Task>(state.task);
    const previousTaskId = state.mode === 'edit' ? state.task.id : undefined;
    const taskType = getTaskType(task);
    const taskOptions = tasks.filter((item) => item.id !== previousTaskId);

    useEffect(() => {
        setTask(state.task);
    }, [state.task]);

    function updateField<K extends keyof Task>(key: K, value: Task[K]) {
        setTask((current) => ({
            ...current,
            [key]: value,
        }));
    }

    function updateTaskType(value: 'event' | 'periodic') {
        setTask((current) => ({
            ...current,
            type: value,
            taskType: current.taskType === undefined ? undefined : value,
            period: value === 'event' ? 0 : current.period || 100,
        }));
    }

    function updateExecutionTime(value: number) {
        setTask((current) => {
            if (current.duration !== undefined && current.wcet === undefined) {
                return {
                    ...current,
                    duration: value,
                };
            }

            return {
                ...current,
                wcet: value,
            };
        });
    }

    function updateMemory(value: number | undefined) {
        setTask((current) => {
            if (current.memoryUsageKB !== undefined) {
                return {
                    ...current,
                    memoryUsageKB: value,
                };
            }

            if (current.memory !== undefined) {
                return {
                    ...current,
                    memory: value,
                };
            }

            return {
                ...current,
                memoryUsageKB: value,
            };
        });
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Task' : 'Edit Task'}
            onCancel={onCancel}
            onDone={() => onSave(task, previousTaskId)}
        >
            <DialogField label="ID">
                <input
                    value={task.id}
                    placeholder="task_01"
                    onChange={(event) => updateField('id', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField label="Name">
                <input
                    value={task.name}
                    placeholder="sensor fusion"
                    onChange={(event) => updateField('name', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField label="Type">
                <select
                    value={taskType}
                    onChange={(event) =>
                        updateTaskType(event.target.value as 'event' | 'periodic')
                    }
                    style={inputStyle}
                >
                    <option value="periodic">periodic</option>
                    <option value="event">event</option>
                </select>
            </DialogField>

            <div style={fieldGridStyle}>
                <DialogField label="WCET">
                    <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={getExecutionTime(task)}
                        onChange={(event) =>
                            updateExecutionTime(Number(event.target.value))
                        }
                        style={inputStyle}
                    />
                </DialogField>

                <DialogField label="Period">
                    <input
                        type="number"
                        min="0"
                        value={task.period ?? 0}
                        disabled={taskType === 'event'}
                        onChange={(event) =>
                            updateField('period', Number(event.target.value))
                        }
                        style={{
                            ...inputStyle,
                            background: taskType === 'event' ? '#f3f4f6' : '#fff',
                        }}
                    />
                </DialogField>
            </div>

            <div style={fieldGridStyle}>
                <DialogField label="Deadline">
                    <input
                        type="number"
                        min="0"
                        value={task.deadline ?? ''}
                        placeholder="optional"
                        onChange={(event) =>
                            updateField(
                                'deadline',
                                event.target.value === ''
                                    ? undefined
                                    : Number(event.target.value),
                            )
                        }
                        style={inputStyle}
                    />
                </DialogField>

                <DialogField label="Memory KB">
                    <input
                        type="number"
                        min="0"
                        value={getMemoryValue(task) ?? ''}
                        placeholder="optional"
                        onChange={(event) =>
                            updateMemory(
                                event.target.value === ''
                                    ? undefined
                                    : Number(event.target.value),
                            )
                        }
                        style={inputStyle}
                    />
                </DialogField>
            </div>

            <DialogField label="Required Domain">
                <input
                    value={task.requiredDomain ?? ''}
                    placeholder="general_purpose"
                    onChange={(event) =>
                        updateField(
                            'requiredDomain',
                            event.target.value || undefined,
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField label="Eligible Cores">
                <input
                    value={(task.eligibleCores ?? []).join(', ')}
                    placeholder="core_00, core_01"
                    onChange={(event) =>
                        updateField(
                            'eligibleCores',
                            event.target.value
                                .split(',')
                                .map((item) => item.trim())
                                .filter(Boolean),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField label="Dependencies">
                <select
                    multiple
                    value={task.dependencies ?? []}
                    onChange={(event) =>
                        updateField(
                            'dependencies',
                            Array.from(event.target.selectedOptions).map(
                                (option) => option.value,
                            ),
                        )
                    }
                    style={{
                        ...inputStyle,
                        height: 92,
                        padding: 8,
                    }}
                >
                    {taskOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                            {item.name || item.id} ({item.id})
                        </option>
                    ))}
                </select>
            </DialogField>

            <div style={fieldGridStyle}>
                {/*<DialogField label="Priority">*/}
                {/*    <input*/}
                {/*        type="number"*/}
                {/*        value={task.priority ?? ''}*/}
                {/*        placeholder="optional"*/}
                {/*        onChange={(event) =>*/}
                {/*            updateField(*/}
                {/*                'priority',*/}
                {/*                event.target.value === ''*/}
                {/*                    ? undefined*/}
                {/*                    : Number(event.target.value),*/}
                {/*            )*/}
                {/*        }*/}
                {/*        style={inputStyle}*/}
                {/*    />*/}
                {/*</DialogField>*/}

                {/*<DialogField label="Criticality">*/}
                {/*    <input*/}
                {/*        type="number"*/}
                {/*        value={task.criticality ?? ''}*/}
                {/*        placeholder="optional"*/}
                {/*        onChange={(event) =>*/}
                {/*            updateField(*/}
                {/*                'criticality',*/}
                {/*                event.target.value === ''*/}
                {/*                    ? undefined*/}
                {/*                    : Number(event.target.value),*/}
                {/*            )*/}
                {/*        }*/}
                {/*        style={inputStyle}*/}
                {/*    />*/}
                {/*</DialogField>*/}
            </div>

            <DialogField label="Notes">
                <textarea
                    value={task.notes ?? ''}
                    placeholder="optional"
                    onChange={(event) =>
                        updateField('notes', event.target.value || undefined)
                    }
                    style={{
                        ...inputStyle,
                        minHeight: 74,
                        paddingTop: 10,
                        resize: 'vertical',
                    }}
                />
            </DialogField>
        </DialogShell>
    );
}

function TaskLinkDialog({
    state,
    tasks,
    onCancel,
    onSave,
}: {
    state: LinkDialogState;
    tasks: Task[];
    onCancel: () => void;
    onSave: (link: TaskLink, previousLink?: TaskLink) => void;
}) {
    const [link, setLink] = useState<TaskLink>(state.link);
    const previousLink = state.mode === 'edit' ? state.link : undefined;

    useEffect(() => {
        setLink(state.link);
    }, [state.link]);

    function updateLink<K extends keyof TaskLink>(key: K, value: TaskLink[K]) {
        setLink((current) => ({
            ...current,
            [key]: value,
        }));
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Task Link' : 'Edit Task Link'}
            onCancel={onCancel}
            onDone={() => onSave(link, previousLink)}
        >
            <DialogField label="Kind">
                <select
                    value={link.kind}
                    onChange={(event) =>
                        updateLink('kind', event.target.value as TaskLinkKind)
                    }
                    style={inputStyle}
                >
                    <option value="dependency">dependency</option>
                    <option value="communication">communication</option>
                </select>
            </DialogField>

            <DialogField label="Source">
                <select
                    value={link.source}
                    onChange={(event) => updateLink('source', event.target.value)}
                    style={inputStyle}
                >
                    {tasks.map((task) => (
                        <option key={task.id} value={task.id}>
                            {task.name || task.id} ({task.id})
                        </option>
                    ))}
                </select>
            </DialogField>

            <DialogField label="Target">
                <select
                    value={link.target}
                    onChange={(event) => updateLink('target', event.target.value)}
                    style={inputStyle}
                >
                    {tasks.map((task) => (
                        <option key={task.id} value={task.id}>
                            {task.name || task.id} ({task.id})
                        </option>
                    ))}
                </select>
            </DialogField>

            {link.kind === 'communication' && (
                <>
                    <DialogField label="Penalty">
                        <input
                            type="number"
                            value={link.penalty ?? 0}
                            onChange={(event) =>
                                updateLink('penalty', Number(event.target.value))
                            }
                            style={inputStyle}
                        />
                    </DialogField>

                    <DialogField label="Notes">
                        <input
                            value={link.notes ?? ''}
                            placeholder="optional"
                            onChange={(event) =>
                                updateLink('notes', event.target.value || undefined)
                            }
                            style={inputStyle}
                        />
                    </DialogField>
                </>
            )}
        </DialogShell>
    );
}

function Panel({
    title,
    onAction,
    children,
}: {
    title: string;
    onAction: () => void;
    children: ReactNode;
}) {
    return (
        <section style={panelStyle}>
            <div style={panelHeaderStyle}>
                <h2 style={panelTitleStyle}>{title}</h2>
                <button onClick={onAction} style={iconButtonStyle} title={`Add ${title}`}>
                    <PlusIcon />
                </button>
            </div>
            <div>{children}</div>
        </section>
    );
}

function EmptyState({ label }: { label: string }) {
    return <div style={emptyStateStyle}>{label}</div>;
}

function ListEntry({
    icon,
    title,
    subtitle,
    selected,
    dropdownOpen,
    onSelect,
    onToggleDropdown,
    onEdit,
    onDelete,
}: {
    icon: ReactNode;
    title: string;
    subtitle: string;
    selected: boolean;
    dropdownOpen: boolean;
    onSelect: () => void;
    onToggleDropdown: () => void;
    onEdit: () => void;
    onDelete: () => void;
}) {
    return (
        <div
            style={{
                ...listEntryStyle,
                background: selected ? '#eef5ff' : '#fff',
                borderColor: selected ? '#9ec5fe' : '#e5e7eb',
            }}
        >
            <button onClick={onSelect} style={entryMainButtonStyle}>
                <span style={entryIconStyle}>{icon}</span>
                <span style={{ minWidth: 0 }}>
                    <span style={entryTitleStyle}>{title}</span>
                    <span style={entrySubtitleStyle}>{subtitle}</span>
                </span>
            </button>

            <button
                onClick={onToggleDropdown}
                style={entryMenuButtonStyle}
                title="Open actions"
            >
                <DotsHorizontalIcon />
            </button>

            {dropdownOpen && (
                <div style={dropdownStyle}>
                    <button onClick={onEdit} style={dropdownButtonStyle}>
                        <Pencil1Icon />
                        Edit
                    </button>
                    <button
                        onClick={onDelete}
                        style={{
                            ...dropdownButtonStyle,
                            color: '#b91c1c',
                        }}
                    >
                        <TrashIcon />
                        Delete
                    </button>
                </div>
            )}
        </div>
    );
}

function DialogShell({
    title,
    children,
    onCancel,
    onDone,
}: {
    title: string;
    children: ReactNode;
    onCancel: () => void;
    onDone: () => void;
}) {
    return (
        <div style={overlayStyle}>
            <div style={dialogStyle}>
                <h2 style={dialogTitleStyle}>{title}</h2>
                <div style={dialogContentStyle}>{children}</div>

                <div style={dialogActionsStyle}>
                    <button onClick={onCancel} style={cancelButtonStyle}>
                        Cancel
                    </button>
                    <button onClick={onDone} style={doneButtonStyle}>
                        Done
                    </button>
                </div>
            </div>
        </div>
    );
}

function DialogField({
    label,
    children,
}: {
    label: string;
    children: ReactNode;
}) {
    return (
        <label style={fieldStyle}>
            <span style={labelStyle}>{label}</span>
            {children}
        </label>
    );
}

function ConfirmDialog({
    pendingDelete,
    onCancel,
    onConfirm,
}: {
    pendingDelete: Exclude<PendingDelete, null>;
    onCancel: () => void;
    onConfirm: () => void;
}) {
    return (
        <div style={overlayStyle}>
            <div style={confirmDialogStyle}>
                <h2 style={{ margin: '0 0 10px', fontSize: 18 }}>
                    Confirm deletion
                </h2>
                <p style={{ margin: 0, color: '#4b5563', lineHeight: 1.45 }}>
                    {pendingDelete.kind === 'task'
                        ? 'Delete this task? Related task links and dependency references will also be removed.'
                        : 'Delete this task link?'}
                </p>

                <div style={dialogActionsStyle}>
                    <button onClick={onCancel} style={cancelButtonStyle}>
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        style={{
                            ...doneButtonStyle,
                            background: '#dc2626',
                        }}
                    >
                        Delete
                    </button>
                </div>
            </div>
        </div>
    );
}

function buildTaskGraph(
    tasks: Task[],
    links: TaskLink[],
    selectedTaskId: string | null,
): {
    nodes: Node<TaskNodeData>[];
    edges: Edge[];
} {
    const depths = computeTaskDepths(tasks, links);
    const levels: string[][] = [];

    tasks.forEach((task) => {
        const depth = depths[task.id] ?? 0;
        if (!levels[depth]) levels[depth] = [];
        levels[depth].push(task.id);
    });

    const nodePositions = new Map<string, { x: number; y: number }>();
    const horizontalSpacing = 280;
    const verticalSpacing = 170;

    levels.forEach((level, depth) => {
        const totalWidth = (level.length - 1) * horizontalSpacing;
        level.forEach((taskId, index) => {
            nodePositions.set(taskId, {
                x: index * horizontalSpacing - totalWidth / 2,
                y: depth * verticalSpacing,
            });
        });
    });

    return {
        nodes: tasks.map((task) => ({
            id: task.id,
            type: 'task',
            data: { task },
            position: nodePositions.get(task.id) ?? { x: 0, y: 0 },
            selected: task.id === selectedTaskId,
        })),
        edges: links.map((link) => ({
            id: link.id,
            source: link.source,
            target: link.target,
            animated: link.kind === 'communication',
            type: 'smoothstep',
            label:
                link.kind === 'communication' && link.penalty !== undefined
                    ? `Penalty ${link.penalty}`
                    : undefined,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: {
                stroke: link.kind === 'communication' ? '#0891b2' : '#4f46e5',
                strokeWidth: 2,
                strokeDasharray: link.kind === 'communication' ? '6 4' : undefined,
            },
            labelBgStyle: {
                fill: '#fff',
                fillOpacity: 0.9,
            },
            labelStyle: {
                fontSize: 12,
                fill: '#334155',
            },
        })),
    };
}

function computeTaskDepths(tasks: Task[], links: TaskLink[]) {
    const depths: Record<string, number> = {};
    const taskIds = new Set(tasks.map((task) => task.id));
    const incoming = new Map<string, string[]>();
    const visiting = new Set<string>();

    links.forEach((link) => {
        if (!taskIds.has(link.source) || !taskIds.has(link.target)) return;
        incoming.set(link.target, [...(incoming.get(link.target) ?? []), link.source]);
    });

    function getDepth(taskId: string): number {
        if (depths[taskId] !== undefined) return depths[taskId];

        if (visiting.has(taskId)) {
            depths[taskId] = 0;
            return 0;
        }

        visiting.add(taskId);
        const predecessors = incoming.get(taskId) ?? [];
        depths[taskId] = predecessors.length
            ? Math.max(...predecessors.map(getDepth)) + 1
            : 0;
        visiting.delete(taskId);

        return depths[taskId];
    }

    tasks.forEach((task) => getDepth(task.id));
    return depths;
}

function buildTaskLinks(tasks: Task[], communications: Communication[]) {
    const taskIds = new Set(tasks.map((task) => task.id));
    const links: TaskLink[] = [];

    tasks.forEach((task) => {
        (task.dependencies ?? []).forEach((dependencyId, dependencyIndex) => {
            if (!taskIds.has(dependencyId)) return;

            links.push({
                id: `dep:${task.id}:${dependencyIndex}:${dependencyId}`,
                kind: 'dependency',
                source: dependencyId,
                target: task.id,
                dependencyIndex,
            });
        });
    });

    communications.forEach((comm, communicationIndex) => {
        if (!taskIds.has(comm.source) || !taskIds.has(comm.target)) return;

        links.push({
            id: `comm:${communicationIndex}:${comm.source}->${comm.target}`,
            kind: 'communication',
            source: comm.source,
            target: comm.target,
            penalty: comm.penalty,
            notes: comm.notes,
            communicationIndex,
        });
    });

    return links;
}

function addTaskLink(
    tasks: Task[],
    communications: Communication[],
    link: TaskLink,
) {
    if (link.kind === 'dependency') {
        return {
            nextTasks: tasks.map((task) =>
                task.id === link.target
                    ? {
                        ...task,
                        dependencies: [
                            ...(task.dependencies ?? []),
                            link.source,
                        ],
                    }
                    : task,
            ),
            nextCommunications: communications,
        };
    }

    return {
        nextTasks: tasks,
        nextCommunications: [
            ...communications,
            {
                source: link.source,
                target: link.target,
                penalty: link.penalty ?? 0,
                notes: link.notes,
            },
        ],
    };
}

function removeTaskLink(
    tasks: Task[],
    communications: Communication[],
    link: TaskLink,
) {
    if (link.kind === 'dependency') {
        return {
            nextTasks: tasks.map((task) => {
                if (task.id !== link.target) return task;

                const dependencies = task.dependencies ?? [];
                return {
                    ...task,
                    dependencies:
                        link.dependencyIndex === undefined
                            ? dependencies.filter((id) => id !== link.source)
                            : dependencies.filter(
                                (_id, index) => index !== link.dependencyIndex,
                            ),
                };
            }),
            nextCommunications: communications,
        };
    }

    return {
        nextTasks: tasks,
        nextCommunications:
            link.communicationIndex === undefined
                ? communications.filter(
                    (comm) =>
                        comm.source !== link.source || comm.target !== link.target,
                )
                : communications.filter(
                    (_comm, index) => index !== link.communicationIndex,
                ),
    };
}

function makeDefaultTask(tasks: Task[]): Task {
    const nextNumber = tasks.length + 1;

    return {
        id: `task_${String(nextNumber).padStart(2, '0')}`,
        name: `Task ${nextNumber}`,
        type: 'periodic',
        wcet: 1,
        period: 100,
        deadline: 100,
        memoryUsageKB: 0,
        requiredDomain: 'general_purpose',
        eligibleCores: [],
        dependencies: [],
    };
}

function normalizeTask(task: Task): Task {
    const taskType = getTaskType(task);
    const normalized: Task = {
        ...task,
        id: task.id.trim(),
        name: task.name.trim(),
        type: taskType,
        period: taskType === 'event' ? 0 : task.period,
        dependencies: (task.dependencies ?? []).filter((id) => id !== task.id),
        eligibleCores: task.eligibleCores ?? [],
    };

    if (task.taskType !== undefined) {
        normalized.taskType = taskType;
    }

    return normalized;
}

function getTaskType(task: Task): 'event' | 'periodic' {
    return task.type ?? task.taskType ?? ((task.period ?? 0) > 0 ? 'periodic' : 'event');
}

function getExecutionTime(task: Task) {
    return task.wcet ?? task.duration ?? 0;
}

function getMemoryValue(task: Task) {
    return task.memoryUsageKB ?? task.memoryUsageKB ?? task.memory;
}

function formatNumber(value: number | undefined) {
    if (value === undefined) return '-';
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function replaceDependencyReferences(task: Task, previousId: string, nextId: string) {
    return {
        ...task,
        dependencies: (task.dependencies ?? []).map((id) =>
            id === previousId ? nextId : id,
        ),
    };
}

function replaceCommunicationEndpoint(
    communications: Communication[],
    previousId: string,
    nextId: string,
) {
    return communications.map((comm) => ({
        ...comm,
        source: comm.source === previousId ? nextId : comm.source,
        target: comm.target === previousId ? nextId : comm.target,
    }));
}

const pageStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'minmax(520px, 1fr) 420px',
    gap: 24,
    height: 'calc(100vh - 46px)',
    minHeight: 560,
};

const graphShellStyle: CSSProperties = {
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    border: '1px solid #d7dde8',
    borderRadius: 8,
    overflow: 'hidden',
    background: '#f8fafc',
};

const graphHeaderStyle: CSSProperties = {
    minHeight: 70,
    padding: '14px 18px',
    borderBottom: '1px solid #d7dde8',
    background: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
};

const pageTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 20,
    color: '#111827',
};

const pageSubtitleStyle: CSSProperties = {
    margin: '5px 0 0',
    color: '#64748b',
    fontSize: 13,
};

const flowContainerStyle: CSSProperties = {
    flex: 1,
    minHeight: 0,
};

const emptyGraphStyle: CSSProperties = {
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column',
    gap: 18,
    color: '#475569',
};

const sidebarStyle: CSSProperties = {
    minWidth: 0,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
};

const panelStyle: CSSProperties = {
    border: '1px solid #d7dde8',
    borderRadius: 8,
    background: '#fff',
    boxShadow: '0 2px 8px rgba(15, 23, 42, 0.08)',
};

const panelHeaderStyle: CSSProperties = {
    minHeight: 56,
    padding: '0 14px 0 18px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid #e5e7eb',
};

const panelTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 16,
    color: '#172033',
};

const iconButtonStyle: CSSProperties = {
    width: 32,
    height: 32,
    border: '1px solid #cbd5e1',
    borderRadius: 6,
    background: '#fff',
    color: '#0f172a',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const secondaryButtonStyle: CSSProperties = {
    border: '1px solid #cbd5e1',
    borderRadius: 6,
    background: '#fff',
    color: '#0f172a',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    minHeight: 34,
    padding: '0 12px',
    fontSize: 14,
};

const primaryButtonStyle: CSSProperties = {
    ...secondaryButtonStyle,
    background: '#2563eb',
    color: '#fff',
    borderColor: '#2563eb',
};

const emptyStateStyle: CSSProperties = {
    padding: 18,
    color: '#64748b',
    fontSize: 14,
};

const listEntryStyle: CSSProperties = {
    position: 'relative',
    borderBottom: '1px solid #e5e7eb',
    display: 'grid',
    gridTemplateColumns: '1fr 36px',
    alignItems: 'stretch',
};

const entryMainButtonStyle: CSSProperties = {
    minWidth: 0,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    display: 'grid',
    gridTemplateColumns: '34px minmax(0, 1fr)',
    alignItems: 'center',
    gap: 10,
    textAlign: 'left',
    padding: '12px 6px 12px 14px',
};

const entryIconStyle: CSSProperties = {
    width: 28,
    height: 28,
    borderRadius: 6,
    background: '#f1f5f9',
    color: '#334155',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const entryTitleStyle: CSSProperties = {
    display: 'block',
    color: '#172033',
    fontWeight: 700,
    fontSize: 14,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
};

const entrySubtitleStyle: CSSProperties = {
    display: 'block',
    color: '#64748b',
    fontSize: 12,
    marginTop: 4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
};

const entryMenuButtonStyle: CSSProperties = {
    border: 'none',
    background: 'transparent',
    color: '#475569',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const dropdownStyle: CSSProperties = {
    position: 'absolute',
    right: 10,
    top: 42,
    zIndex: 20,
    width: 132,
    border: '1px solid #cbd5e1',
    borderRadius: 6,
    background: '#fff',
    boxShadow: '0 10px 24px rgba(15, 23, 42, 0.18)',
    overflow: 'hidden',
};

const dropdownButtonStyle: CSSProperties = {
    width: '100%',
    border: 'none',
    background: '#fff',
    cursor: 'pointer',
    padding: '9px 12px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    textAlign: 'left',
    fontSize: 14,
};

const overlayStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 100,
    background: 'rgba(15, 23, 42, 0.35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
};

const dialogStyle: CSSProperties = {
    width: 520,
    maxWidth: 'calc(100vw - 48px)',
    maxHeight: '88vh',
    overflowY: 'auto',
    background: '#fff',
    borderRadius: 8,
    padding: 24,
    boxShadow: '0 22px 60px rgba(15, 23, 42, 0.28)',
};

const confirmDialogStyle: CSSProperties = {
    ...dialogStyle,
    width: 420,
};

const dialogTitleStyle: CSSProperties = {
    margin: '0 0 18px',
    fontSize: 18,
    color: '#111827',
};

const dialogContentStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
};

const fieldStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 7,
};

const fieldGridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 12,
};

const labelStyle: CSSProperties = {
    fontSize: 13,
    fontWeight: 700,
    color: '#334155',
};

const inputStyle: CSSProperties = {
    width: '100%',
    height: 38,
    border: '1px solid #cbd5e1',
    borderRadius: 6,
    padding: '0 10px',
    fontSize: 14,
    color: '#111827',
    boxSizing: 'border-box',
};

const dialogActionsStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 22,
};

const cancelButtonStyle: CSSProperties = {
    border: '1px solid #cbd5e1',
    background: '#fff',
    color: '#0f172a',
    borderRadius: 6,
    padding: '9px 14px',
    cursor: 'pointer',
};

const doneButtonStyle: CSSProperties = {
    border: 'none',
    background: '#2563eb',
    color: '#fff',
    borderRadius: 6,
    padding: '10px 16px',
    cursor: 'pointer',
};
