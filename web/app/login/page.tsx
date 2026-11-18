"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, saveName, errorMessage } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email);
      saveName(name.trim());
      router.push("/");
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold">$APP Rewards</h1>
          <p className="text-gray-500">Points that travel with you</p>
        </div>

        <input
          type="text"
          required
          placeholder="Your name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="block mx-auto w-56 border rounded-lg px-4 py-3"
        />

        <input
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="block mx-auto w-56 border rounded-lg px-4 py-3"
        />

        <button
          type="submit"
          disabled={loading}
          className="block mx-auto w-54 bg-green-700 text-white rounded-lg py-3 font-semibold disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Continue"}
        </button>

        {error && <p className="text-red-600 text-sm text-center">{error}</p>}
      </form>
    </main>
  );
}