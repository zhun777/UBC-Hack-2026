// Shared building blocks so every page looks the same.
// Change a style here and it changes everywhere.

import Link from "next/link";
import { BottomNav } from "./nav";

/** The page frame: a phone-width column with an optional title, back link and bottom toolbar. */
export function Screen({
  title,
  back,
  nav = false,
  children,
}: {
  title?: string;
  back?: string;
  nav?: boolean;
  children: React.ReactNode;
}) {
  return (
    <main className={`w-full max-w-md mx-auto px-5 pt-8 space-y-6 ${nav ? "pb-28" : "pb-8"}`}>
      {(title || back) && (
        <header className="flex items-center gap-3">
          {back && (
            <Link href={back} className="text-stone-400 hover:text-stone-900 text-xl" aria-label="Back">
              ←
            </Link>
          )}
          {title && <h1 className="text-xl font-semibold">{title}</h1>}
        </header>
      )}
      {children}
      {nav && <BottomNav />}
    </main>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-stone-200 bg-white p-5 ${className}`}>{children}</div>;
}

export function Button({
  children,
  loading = false,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean; variant?: "primary" | "secondary" }) {
  const look =
    variant === "primary"
      ? "bg-green-700 text-white hover:bg-green-800"
      : "border border-stone-300 text-stone-900 hover:bg-stone-50";
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className={`w-full rounded-xl py-3 font-medium transition disabled:opacity-40 ${look} ${className}`}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
}

export function Spinner() {
  return (
    <span
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent align-middle"
      aria-label="Loading"
    />
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="text-sm text-red-600 text-center">{children}</p>;
}

/** Small "Verify onchain" link to the Arc explorer. Hidden when there's no real transaction. */
export function VerifyLink({ url }: { url: string | null }) {
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="text-xs text-stone-400 hover:text-green-700">
      Verify onchain ↗
    </a>
  );
}
