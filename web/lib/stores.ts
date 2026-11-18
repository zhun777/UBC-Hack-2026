// Member stores, as shown to users. The slugs match the backend's brands.json;
// the names and locations here are display-only, so change them freely.

export type Store = {
  slug: string;
  name: string;
  location: string;
  kind: "online" | "in-store";
  href: string;
};

export const STORES: Store[] = [
  { slug: "brand-a-us", name: "Treehouse Supply Co.", location: "Online · United States", kind: "online", href: "/store/brand-a" },
  { slug: "cafe-sg", name: "Treehouse Café", location: "Orchard Road, Singapore", kind: "in-store", href: "/pay" },
];

const BRANCHES: Record<string, string> = {
  "cafe-sg-orchard": "Orchard Road, Singapore",
};

/** "cafe-sg" → "Treehouse Café" */
export function storeName(slug: string): string {
  return STORES.find((s) => s.slug === slug)?.name ?? slug;
}

/** Works for a brand ("brand-a-us") or a branch ("cafe-sg-orchard"). */
export function storeLocation(slug: string): string {
  return BRANCHES[slug] ?? STORES.find((s) => s.slug === slug)?.location ?? "";
}
