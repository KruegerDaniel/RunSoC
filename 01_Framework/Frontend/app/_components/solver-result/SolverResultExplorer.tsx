'use client';

import { useState } from 'react';
import type { SolverResult } from './types';
import { ChainView } from './ChainView';
import { CoreGantt } from './CoreGantt';
import { JobTable } from './JobTable';
import { MemoryHeatmap } from './MemoryHeatMap';
import { ObjectiveBreakdown } from './ObjectiveBreakdown';
import { PlatformTopology } from './PlatformTopology';
import { ResultDashboard } from './ResultDashboard';

type Props = {
    result: SolverResult;
};

type Tab = 'schedule' | 'topology' | 'memory' | 'chains' | 'objective' | 'jobs';

const tabs: { id: Tab; label: string }[] = [
    { id: 'schedule', label: 'Schedule' },
    { id: 'topology', label: 'Topology' },
    { id: 'memory', label: 'Memory' },
    { id: 'chains', label: 'Chains' },
    { id: 'objective', label: 'Objective' },
    { id: 'jobs', label: 'Jobs' },
];

export function SolverResultExplorer({ result }: Props) {
    const [activeTab, setActiveTab] = useState<Tab>('schedule');

    return (
        <div className="space-y-5">
            <ResultDashboard result={result} />

            <div className="rounded-2xl border border-slate-200 bg-white p-2 shadow-sm">
                <div className="flex flex-wrap gap-2">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            onClick={() => setActiveTab(tab.id)}
                            className={`rounded-xl px-4 py-2 text-sm font-medium ${
                                activeTab === tab.id
                                    ? 'bg-slate-900 text-white'
                                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            {activeTab === 'schedule' && <CoreGantt result={result} />}
            {activeTab === 'topology' && <PlatformTopology result={result} />}
            {activeTab === 'memory' && <MemoryHeatmap result={result} />}
            {activeTab === 'chains' && <ChainView result={result} />}
            {activeTab === 'objective' && <ObjectiveBreakdown result={result} />}
            {activeTab === 'jobs' && <JobTable result={result} />}
        </div>
    );
}