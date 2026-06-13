import type { Metadata } from 'next';
import { Workspace } from '@/components/workspace/Workspace';

export const metadata: Metadata = {
  title: 'Chat | Mihna',
  description: 'Ask grounded questions across Mihna job-market datasets.',
};

export default function ChatPage() {
  return <Workspace mode="chat" />;
}
