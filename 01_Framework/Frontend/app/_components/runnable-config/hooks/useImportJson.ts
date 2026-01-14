// useImportJson.ts
import { UseFormSetValue } from 'react-hook-form';
import type { SimulationForm } from '@/types/runnable';

export function useImportJson(setValue: UseFormSetValue<SimulationForm>) {
    return (file: File) => {
        const reader = new FileReader();
        reader.onload = () => {
            try {
                const json = JSON.parse(String(reader.result));
                const ok =
                    Array.isArray(json?.runnables) &&
                    typeof json?.numCores === 'number' &&
                    json.runnables.every((r: any) =>
                        r.id &&
                        r.name &&
                        typeof r.priority === 'number' &&
                        typeof r.affinity === 'number' &&
                        typeof r.execution_time === 'number' &&
                        ['periodic', 'event'].includes(r.type) &&
                        Array.isArray(r.dependencies),
                    );

                if (!ok) {
                    alert('Invalid JSON structure');
                    return;
                }

                setValue('numCores', json.numCores, {
                    shouldValidate: true,
                    shouldDirty: true,
                });
                setValue('runnables', json.runnables, {
                    shouldValidate: true,
                    shouldDirty: true,
                });
            } catch {
                alert('Invalid JSON file');
            }
        };
        reader.readAsText(file);
    };
}
