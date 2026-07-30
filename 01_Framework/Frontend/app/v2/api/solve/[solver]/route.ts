import {NextRequest, NextResponse} from 'next/server';

export const runtime = 'nodejs';

const DEFAULT_BACKEND_URL = 'http://localhost:5001';

function getBackendUrl(path = '') {
    const baseUrl = (process.env.BACKEND_URL || DEFAULT_BACKEND_URL)
        .replace(/\/+$/, '')
        .replace(/\/api\/schedule$/i, '');

    if (!path) return baseUrl;

    return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function POST(
    req: NextRequest,
    {params}: {params: Promise<{solver: string}>},
) {
    const {solver} = await params;
    const backendUrl = getBackendUrl(`/api/solve/${solver}`);

    try {
        const backendRes = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: JSON.stringify(await req.json()),
        });

        const contentType = backendRes.headers.get('content-type') ?? '';
        const payload = contentType.includes('application/json')
            ? await backendRes.json()
            : await backendRes.text();

        return NextResponse.json(payload, {status: backendRes.status});
    } catch (e) {
        console.error('[solve/POST] fetch failed:', e);
        return NextResponse.json(
            {
                error: 'Failed to connect to backend',
                details: String(e),
                target: backendUrl,
            },
            {status: 500},
        );
    }
}
