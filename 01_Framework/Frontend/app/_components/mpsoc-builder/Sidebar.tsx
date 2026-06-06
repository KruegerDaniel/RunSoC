'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const items = [
    { href: '/v2/platform', label: 'SoC Design', icon: '✦' },
    { href: '/v2/taskset', label: 'Tasks', icon: '✩' },
    { href: '/v2/config', label: 'Config', icon: '✩' },
    { href: '/v2/solve', label: 'Finalize', icon: '✓' },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside
            style={{
                width: 94,
                minHeight: '100vh',
                background: '#f2f2f7',
                borderRight: '1px solid #e5e5e5',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                paddingTop: 48,
                gap: 28,
                position: 'fixed',
                left: 0,
                top: 0,
            }}
        >
            <div style={{ fontSize: 22, marginBottom: 20 }}>☰</div>

            {items.map((item) => {
                const active = pathname === item.href;

                return (
                    <Link
                        key={item.href}
                        href={item.href}
                        style={{
                            textDecoration: 'none',
                            color: '#333',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 6,
                            fontSize: 13,
                            width: '100%',
                        }}
                    >
                        <div
                            style={{
                                width: 54,
                                height: 28,
                                borderRadius: 999,
                                background: active ? '#e7ddff' : 'transparent',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: 20,
                            }}
                        >
                            {item.icon}
                        </div>
                        <span>{item.label}</span>
                    </Link>
                );
            })}
        </aside>
    );
}
