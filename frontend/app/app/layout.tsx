import { Workspace } from '@/components/workspace/Workspace';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Workspace>{children}</Workspace>;
}
