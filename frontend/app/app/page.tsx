import type { Metadata } from 'next';
import { Workspace } from '@/components/workspace/Workspace';

export const metadata: Metadata = {
  title: 'Dashboard | Mihna',
  description: 'Explore GCC job-market signals across countries, sectors, skills, and time.',
};

export default function DashboardPage() {
  return <Workspace mode="dashboard" />;
}
