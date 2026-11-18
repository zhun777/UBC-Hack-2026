"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, ShoppingBag, Store as StoreIcon, MapPin } from "lucide-react";
import { STORES } from "@/lib/stores";
import { Screen, Card } from "@/components/ui";

export default function StoresPage() {
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const results = STORES.filter((s) => s.name.toLowerCase().includes(q) || s.location.toLowerCase().includes(q));

  return (
    <Screen title="Stores" nav>
      <label className="flex items-center gap-2 rounded-xl border border-stone-300 px-4 py-3 focus-within:border-green-700">
        <Search size={18} className="text-stone-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search stores or cities"
          className="w-full bg-transparent focus:outline-none"
        />
      </label>

      {results.length === 0 ? (
        <p className="text-sm text-stone-400 text-center">No stores match “{query}”.</p>
      ) : (
        <div className="space-y-3">
          {results.map((store) => (
            <Link key={store.slug} href={store.href} className="block">
              <Card className="flex items-center gap-4 hover:border-stone-400 transition">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-green-50 text-green-700">
                  {store.kind === "online" ? (
                    <ShoppingBag size={20} strokeWidth={1.75} />
                  ) : (
                    <StoreIcon size={20} strokeWidth={1.75} />
                  )}
                </div>
                <div className="flex-1">
                  <p className="font-medium">{store.name}</p>
                  <p className="flex items-center gap-1 text-sm text-stone-500">
                    <MapPin size={13} /> {store.location}
                  </p>
                </div>
                <span className="text-xs text-green-700">{store.kind === "online" ? "Shop online" : "Pay in store"}</span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </Screen>
  );
}
