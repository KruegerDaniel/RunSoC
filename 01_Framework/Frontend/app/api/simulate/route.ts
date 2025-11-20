import {NextRequest, NextResponse} from 'next/server';
import {Runnable} from '@/types/runnable';

const globalAny = globalThis as any;
if (!globalAny.__resultStore) {
    globalAny.__resultStore = {};
}
const resultStore: Record<string, unknown> = globalAny.__resultStore;

export const runtime = 'nodejs'; // NOT edge

const BACKEND_URL =
    process.env.BACKEND_URL || 'http://backend:5001/api/schedule';

export async function POST(req: NextRequest) {
    const data = await req.json();

    try {
        console.log('[simulate/POST] calling backend:', BACKEND_URL);

        const backendRes = await fetch(BACKEND_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                runnables: Object.fromEntries(
                    data.runnables.map((r: Runnable) => [
                        r.name,
                        {...r, deps: r.dependencies},
                    ]),
                ),
                numCores: data.numCores,
                simulationTime: 400,
                algorithm: data.algorithm ?? 'all',
                allocationPolicy: data.allocationPolicy ?? 'static',
            }),
        });

        if (!backendRes.ok) {
            const text = await backendRes.text().catch(() => '');
            console.error(
                '[simulate/POST] backend returned non-OK:',
                backendRes.status,
                text.slice(0, 300),
            );
            return NextResponse.json(
                {
                    error: 'Backend responded with error',
                    status: backendRes.status,
                    body: text,
                    target: BACKEND_URL,
                },
                {status: 502},
            );
        }

        const backendData = await backendRes.json();

        const resultId = Math.random().toString(36).substring(2, 10);
        const payload = {resultId, ...backendData};

        resultStore[resultId] = payload;

        return NextResponse.json(payload);
    } catch (e) {
        console.error('[simulate/POST] fetch failed:', e);
        return NextResponse.json(
            {
                error: 'Failed to connect to backend',
                details: String(e),
                target: BACKEND_URL,
            },
            {status: 500},
        );
    }
}

export async function GET(req: NextRequest) {
    const {searchParams} = new URL(req.url);
    const resultId = searchParams.get('id');

    if (!resultId || !resultStore[resultId]) {
        return NextResponse.json({error: 'Result not found'}, {status: 404});
    }

    return NextResponse.json(resultStore[resultId]);
}
