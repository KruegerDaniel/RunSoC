'use client';

import JsonEditor from '@/app/_components/mpsoc-builder/JsonEditor';
import { useJsonModel } from '@/lib/JsonModelContext';

export default function TasksetPage() {
    const { model, updateTasks, updateCommunications } = useJsonModel();

    return (
        <div>
            <JsonEditor
                title="Tasks"
                value={model.tasks}
                onChange={updateTasks}
            />

            <div style={{ height: '32px' }} />

            <JsonEditor
                title="Communications"
                value={model.communications}
                onChange={updateCommunications}
            />
        </div>
    );
}
