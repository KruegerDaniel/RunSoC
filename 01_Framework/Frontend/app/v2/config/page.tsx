'use client';

import JsonEditor from '@/app/_components/mpsoc-builder/JsonEditor';
import { useJsonModel } from '@/lib/JsonModelContext';

export default function ConfigPage() {
    const { model, updateConfig } = useJsonModel();

    return (
        <JsonEditor
            title="Config"
            value={model.config}
            onChange={updateConfig}
        />
    );
}
