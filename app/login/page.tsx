"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { API_BASE } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { user, login, signup, logout } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");

  // Form fields
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        if (!name.trim()) {
          throw new Error("Name is required");
        }
        await signup(name, email, password);
      }
      router.push("/");
    } catch (err) {
      if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
        const apiLocation = API_BASE || "the app's /api endpoint";
        setError(
          `Cannot reach MOSAIC at ${apiLocation}. Start both servers with "npm run dev" from the project folder, then retry.`
        );
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Authentication failed. Please check your details and try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (user) {
    return (
      <div className="mx-auto max-w-md card p-8 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-accent/10 text-accent font-serif text-2xl font-bold">
          {user.name ? user.name.charAt(0).toUpperCase() : "U"}
        </div>
        <div>
          <h1 className="font-serif text-2xl text-ink">Welcome back, {user.name}!</h1>
          <p className="mt-1 text-sm text-ink-soft">{user.email}</p>
        </div>
        <p className="text-xs text-ink-faint">
          Your personal data and MOSAIC Life Graph are active and isolated to your session.
        </p>
        <div className="flex justify-center gap-3 pt-2">
          <Link href="/" className="btn-primary">
            Go to Dashboard
          </Link>
          <Link href="/profile" className="btn-ghost">
            View Profile
          </Link>
          <button
            onClick={() => logout()}
            className="rounded-lg border border-red-200 bg-red-50/50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100/50 transition-colors"
          >
            Log Out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md py-6 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="font-serif text-3xl text-ink">MOSAIC Account</h1>
        <p className="text-sm text-ink-soft">
          Log in or create a account to personalize your intelligence workspace.
        </p>
      </div>

      <div className="card p-6 shadow-sm">
        {/* Tab Switcher */}
        <div className="mb-6 flex rounded-lg bg-line/40 p-1">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              mode === "login"
                ? "bg-paper text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Log In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              mode === "signup"
                ? "bg-paper text-ink shadow-sm"
                : "text-ink-soft hover:text-ink"
            }`}
          >
            Create Account
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ink-faint mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Saniya"
                className="w-full rounded-lg border border-line bg-paper px-3.5 py-2 text-sm text-ink outline-none focus:border-accent"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-ink-faint mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border border-line bg-paper px-3.5 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-ink-faint mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              minLength={3}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border border-line bg-paper px-3.5 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 text-center flex items-center justify-center gap-2"
          >
            {loading ? (
              <span>Processing…</span>
            ) : mode === "login" ? (
              <span>Log In</span>
            ) : (
              <span>Create Account</span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
