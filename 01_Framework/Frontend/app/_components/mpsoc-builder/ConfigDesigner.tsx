'use client';

import type { CSSProperties } from 'react';
import {
    ClockIcon,
    LightningBoltIcon,
    MixerHorizontalIcon,
    ResetIcon,
} from '@radix-ui/react-icons';
import { defaultModel } from '@/lib/defaultModel';
import { useJsonModel } from '@/lib/JsonModelContext';
import type { Config } from '@/lib/types/mpsoc';

type WeightKey = keyof Config['commsPenaltyWeight'];
type MemoryScaleKey = keyof Config['memoryPenaltyScale'];
type ConfigWithMaxChainJitter = Config & {
    maxChainJitter?: number;
};

const communicationControls: Array<{
    key: WeightKey;
    label: string;
    accent: string;
    max: number;
}> = [
    {
        key: 'intraCoreWeight',
        label: 'Intra-core',
        accent: '#2563eb',
        max: 25,
    },
    {
        key: 'interCoreWeight',
        label: 'Inter-core',
        accent: '#7c3aed',
        max: 40,
    },
    {
        key: 'interClusterWeight',
        label: 'Inter-cluster',
        accent: '#c2410c',
        max: 60,
    },
];

const memoryControls: Array<{
    key: MemoryScaleKey;
    label: string;
    accent: string;
    max: number;
}> = [
    {
        key: 'coreOverflowScale',
        label: 'Core overflow',
        accent: '#047857',
        max: 20,
    },
    {
        key: 'clusterOverflowScale',
        label: 'Cluster overflow',
        accent: '#b45309',
        max: 20,
    },
];

export default function ConfigDesigner() {
    const { model, updateConfig } = useJsonModel();
    const config = model.config as ConfigWithMaxChainJitter;

    const communicationTotal =
        config.commsPenaltyWeight.intraCoreWeight +
        config.commsPenaltyWeight.interCoreWeight +
        config.commsPenaltyWeight.interClusterWeight;

    const memoryTotal =
        config.memoryPenaltyScale.coreOverflowScale +
        config.memoryPenaltyScale.clusterOverflowScale;

    const rawMaxChainJitter = config.maxChainJitter ?? -1;
    const maxChainJitterEnabled = rawMaxChainJitter >= 0;
    const maxChainJitterValue = maxChainJitterEnabled ? rawMaxChainJitter : 0;

    function setGenerateComms(generateComms: boolean) {
        updateConfig({
            ...config,
            generateComms,
        });
    }

    function setCommunicationWeight(key: WeightKey, value: number) {
        updateConfig({
            ...config,
            commsPenaltyWeight: {
                ...config.commsPenaltyWeight,
                [key]: value,
            },
        });
    }

    function setMemoryScale(key: MemoryScaleKey, value: number) {
        updateConfig({
            ...config,
            memoryPenaltyScale: {
                ...config.memoryPenaltyScale,
                [key]: value,
            },
        });
    }

    function setMaxChainJitterEnabled(enabled: boolean) {
        updateConfig({
            ...config,
            maxChainJitter: enabled ? maxChainJitterValue : -1,
        } as Config);
    }

    function setMaxChainJitter(value: number) {
        updateConfig({
            ...config,
            maxChainJitter: Math.max(0, Math.trunc(value)),
        } as Config);
    }

    function resetConfig() {
        updateConfig(defaultModel.config);
    }

    return (
        <section style={pageStyle}>
            <header style={headerStyle}>
                <div>
                    <h1 style={titleStyle}>Config</h1>
                    <div style={summaryGridStyle}>
                        <SummaryMetric label="Communication" value={communicationTotal} />
                        <SummaryMetric label="Memory scale" value={memoryTotal} />
                        <SummaryMetric
                            label="Comms"
                            value={config.generateComms ? 'On' : 'Off'}
                        />
                        <SummaryMetric
                            label="Max jitter"
                            value={
                                maxChainJitterEnabled
                                    ? maxChainJitterValue
                                    : 'Off'
                            }
                        />
                    </div>
                </div>

                <button type="button" onClick={resetConfig} style={resetButtonStyle}>
                    <ResetIcon width={15} height={15} />
                    Reset
                </button>
            </header>

            <div style={layoutStyle}>
                <div style={editorColumnStyle}>
                    <section style={panelStyle}>
                        <div style={panelHeaderStyle}>
                            <span style={panelIconStyle}>
                                <LightningBoltIcon width={16} height={16} />
                            </span>
                            <h2 style={panelTitleStyle}>Communication</h2>
                        </div>

                        <label style={toggleRowStyle}>
                            <span>
                                <span style={fieldLabelStyle}>Generate comms</span>
                                <span style={fieldMetaStyle}>
                                    {config.generateComms ? 'enabled' : 'disabled'}
                                </span>
                            </span>
                            <input
                                type="checkbox"
                                checked={config.generateComms}
                                onChange={(event) =>
                                    setGenerateComms(event.target.checked)
                                }
                                style={toggleStyle}
                            />
                        </label>

                        <div style={controlStackStyle}>
                            {communicationControls.map((control) => (
                                <NumericSlider
                                    key={control.key}
                                    label={control.label}
                                    value={config.commsPenaltyWeight[control.key]}
                                    max={control.max}
                                    accent={control.accent}
                                    onChange={(value) =>
                                        setCommunicationWeight(control.key, value)
                                    }
                                />
                            ))}
                        </div>
                    </section>

                    <section style={panelStyle}>
                        <div style={panelHeaderStyle}>
                            <span style={panelIconStyle}>
                                <ClockIcon width={16} height={16} />
                            </span>
                            <h2 style={panelTitleStyle}>Chain Jitter</h2>
                        </div>

                        <label style={toggleRowStyle}>
                            <span>
                                <span style={fieldLabelStyle}>Max chain jitter</span>
                                <span style={fieldMetaStyle}>
                                    {maxChainJitterEnabled ? 'enabled' : 'disabled'}
                                </span>
                            </span>
                            <input
                                type="checkbox"
                                checked={maxChainJitterEnabled}
                                onChange={(event) =>
                                    setMaxChainJitterEnabled(event.target.checked)
                                }
                                style={toggleStyle}
                            />
                        </label>

                        {maxChainJitterEnabled && (
                            <NumericSlider
                                label="Jitter window"
                                value={maxChainJitterValue}
                                max={100}
                                accent="#0891b2"
                                integerOnly
                                onChange={setMaxChainJitter}
                            />
                        )}
                    </section>

                    <section style={panelStyle}>
                        <div style={panelHeaderStyle}>
                            <span style={panelIconStyle}>
                                <MixerHorizontalIcon width={16} height={16} />
                            </span>
                            <h2 style={panelTitleStyle}>Memory Penalty</h2>
                        </div>

                        <div style={controlStackStyle}>
                            {memoryControls.map((control) => (
                                <NumericSlider
                                    key={control.key}
                                    label={control.label}
                                    value={config.memoryPenaltyScale[control.key]}
                                    max={control.max}
                                    accent={control.accent}
                                    onChange={(value) =>
                                        setMemoryScale(control.key, value)
                                    }
                                />
                            ))}
                        </div>
                    </section>
                </div>

                <aside style={previewPanelStyle}>
                    <div style={previewHeaderStyle}>
                        <span style={previewDotStyle} />
                        <h2 style={previewTitleStyle}>JSON Preview</h2>
                    </div>
                    <pre style={previewStyle}>{JSON.stringify(config, null, 2)}</pre>
                </aside>
            </div>
        </section>
    );
}

function SummaryMetric({
    label,
    value,
}: {
    label: string;
    value: string | number;
}) {
    return (
        <div style={summaryMetricStyle}>
            <span style={summaryLabelStyle}>{label}</span>
            <strong style={summaryValueStyle}>{value}</strong>
        </div>
    );
}

function NumericSlider({
    label,
    value,
    max,
    accent,
    integerOnly = false,
    onChange,
}: {
    label: string;
    value: number;
    max: number;
    accent: string;
    integerOnly?: boolean;
    onChange: (value: number) => void;
}) {
    function commitValue(nextValue: number) {
        const normalizedValue = integerOnly ? Math.trunc(nextValue) : nextValue;
        onChange(Math.max(0, normalizedValue));
    }

    const width = `${Math.min(100, (value / max) * 100)}%`;

    return (
        <div style={numericControlStyle}>
            <div style={numericHeaderStyle}>
                <span style={fieldLabelStyle}>{label}</span>
                <input
                    type="number"
                    min={0}
                    value={value}
                    onChange={(event) => commitValue(Number(event.target.value))}
                    style={{
                        ...numberInputStyle,
                        borderColor: accent,
                    }}
                />
            </div>

            <div style={sliderTrackShellStyle}>
                <div
                    style={{
                        ...sliderFillStyle,
                        width,
                        background: accent,
                    }}
                />
                <input
                    type="range"
                    min={0}
                    max={max}
                    value={Math.min(value, max)}
                    onChange={(event) => commitValue(Number(event.target.value))}
                    style={rangeInputStyle}
                    aria-label={label}
                />
            </div>
        </div>
    );
}

const pageStyle: CSSProperties = {
    maxWidth: 1280,
};

const headerStyle: CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 24,
    marginBottom: 22,
};

const titleStyle: CSSProperties = {
    margin: 0,
    fontSize: 32,
    color: '#111827',
};

const summaryGridStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 14,
};

const summaryMetricStyle: CSSProperties = {
    minWidth: 132,
    border: '1px solid #d8dee8',
    borderRadius: 8,
    padding: '10px 12px',
    background: '#f8fafc',
};

const summaryLabelStyle: CSSProperties = {
    display: 'block',
    fontSize: 12,
    color: '#667085',
    marginBottom: 3,
};

const summaryValueStyle: CSSProperties = {
    fontSize: 18,
    color: '#172033',
};

const resetButtonStyle: CSSProperties = {
    border: '1px solid #cfd6e1',
    background: '#fff',
    color: '#172033',
    borderRadius: 8,
    padding: '10px 13px',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontWeight: 700,
};

const layoutStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 18,
    alignItems: 'start',
};

const editorColumnStyle: CSSProperties = {
    display: 'grid',
    gap: 18,
    flex: '1 1 460px',
    minWidth: 0,
};

const panelStyle: CSSProperties = {
    border: '1px solid #d8dee8',
    borderRadius: 8,
    background: '#fff',
    padding: 18,
    boxShadow: '0 3px 10px rgba(15, 23, 42, 0.06)',
};

const panelHeaderStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
};

const panelIconStyle: CSSProperties = {
    width: 30,
    height: 30,
    borderRadius: 7,
    background: '#eef2ff',
    color: '#3730a3',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const panelTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 18,
    color: '#172033',
};

const toggleRowStyle: CSSProperties = {
    minHeight: 62,
    border: '1px solid #e1e7ef',
    borderRadius: 8,
    padding: '12px 14px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
    marginBottom: 14,
};

const fieldLabelStyle: CSSProperties = {
    display: 'block',
    fontSize: 14,
    fontWeight: 700,
    color: '#172033',
};

const fieldMetaStyle: CSSProperties = {
    display: 'block',
    marginTop: 3,
    fontSize: 12,
    color: '#667085',
};

const toggleStyle: CSSProperties = {
    width: 18,
    height: 18,
    accentColor: '#2563eb',
    cursor: 'pointer',
};

const controlStackStyle: CSSProperties = {
    display: 'grid',
    gap: 14,
};

const numericControlStyle: CSSProperties = {
    border: '1px solid #e1e7ef',
    borderRadius: 8,
    padding: '13px 14px',
};

const numericHeaderStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
    marginBottom: 12,
};

const numberInputStyle: CSSProperties = {
    width: 82,
    height: 34,
    border: '1px solid #cbd5e1',
    borderRadius: 7,
    padding: '0 8px',
    fontSize: 14,
    fontWeight: 700,
    color: '#172033',
};

const sliderTrackShellStyle: CSSProperties = {
    position: 'relative',
    height: 10,
    borderRadius: 999,
    background: '#edf1f7',
    overflow: 'hidden',
};

const sliderFillStyle: CSSProperties = {
    position: 'absolute',
    inset: '0 auto 0 0',
    borderRadius: 999,
};

const rangeInputStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    opacity: 0,
    cursor: 'pointer',
};

const previewPanelStyle: CSSProperties = {
    border: '1px solid #d8dee8',
    borderRadius: 8,
    background: '#111827',
    color: '#e5e7eb',
    overflow: 'hidden',
    flex: '1 1 340px',
    minWidth: 0,
    maxWidth: 460,
    boxShadow: '0 3px 10px rgba(15, 23, 42, 0.10)',
};

const previewHeaderStyle: CSSProperties = {
    height: 44,
    borderBottom: '1px solid rgba(255,255,255,0.10)',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 14px',
};

const previewDotStyle: CSSProperties = {
    width: 9,
    height: 9,
    borderRadius: 999,
    background: '#22c55e',
};

const previewTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 14,
    color: '#f9fafb',
};

const previewStyle: CSSProperties = {
    margin: 0,
    minHeight: 360,
    maxHeight: 620,
    overflow: 'auto',
    padding: 18,
    fontFamily: 'Consolas, Monaco, monospace',
    fontSize: 13,
    lineHeight: 1.55,
    whiteSpace: 'pre-wrap',
};
