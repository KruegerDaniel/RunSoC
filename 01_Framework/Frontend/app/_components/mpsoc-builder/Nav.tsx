import Link from 'next/link';

export default function Nav() {
    return (
        <nav
            style={{
                display: 'flex',
                gap: '16px',
                padding: '16px 24px',
                borderBottom: '1px solid #ddd',
            }}
        >
            <Link href="/v2/">Overview</Link>
            <Link href="/v2/platform">Platform</Link>
            <Link href="/v2/taskset">Taskset</Link>
            <Link href="/v2/config">Config</Link>
            <Link href="/v2/solve">Solve</Link>
        </nav>
    );
}
