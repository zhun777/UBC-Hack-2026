// Turning numbers and slugs from the backend into text people can read.

/** 5000, "USD" → "$50.00";  135, "SGD" → "S$1.35" */
export function formatMoney(minor: number, currency: string): string {
  const symbol = currency === "USD" ? "$" : currency === "SGD" ? "S$" : `${currency} `;
  return symbol + (minor / 100).toFixed(2);
}

/** "2026-11-19T14:05:00Z" → "Nov 19, 2:05 PM" */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
