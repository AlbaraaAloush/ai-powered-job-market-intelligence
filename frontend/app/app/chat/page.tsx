import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

export const metadata: Metadata = {
  title: 'Chat | Mihna',
  description: 'Ask grounded questions across Mihna job-market datasets.',
};

export default function ChatPage() {
  if (process.env.ENABLE_CHAT !== 'true') {
    notFound();
  }

  return null;
}
