import type { Metadata } from 'next';
import { JsonModelProvider } from '@/lib/JsonModelContext';
import Sidebar from '@/app/_components/mpsoc-builder/Sidebar';

export const metadata: Metadata = {
    title: 'Solver JSON Builder',
    description: 'Build and submit solver JSON models',
};

export default function V2Layout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <JsonModelProvider>
            <Sidebar />
            <main
                style={{
                    marginLeft: 94,
                    minHeight: '100vh',
                    background: '#ffffff',
                    padding: '14px 36px 32px',
                }}
            >
                {children}
            </main>
        </JsonModelProvider>
    );
}
