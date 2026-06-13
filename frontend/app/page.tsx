import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="text-center">
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          New landing page in progress.
        </p>
        <Link
          href="/app"
          className="mt-4 inline-block text-sm underline underline-offset-4"
        >
          Open dashboard
        </Link>
      </div>
    </main>
  );
}
