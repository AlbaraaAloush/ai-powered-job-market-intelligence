import { Workspace } from '@/components/workspace/Workspace';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const chatEnabled = process.env.ENABLE_CHAT === 'true';
  return <Workspace chatEnabled={chatEnabled}>{children}</Workspace>;
}
