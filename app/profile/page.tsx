"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";

const FIELD_DEFAULTS: Record<string, { label: string; placeholder: string; defaultShared: boolean }> = {
  display_name: { label: "Display Name", placeholder: "e.g. Saniya", defaultShared: true },
  city: { label: "City", placeholder: "e.g. Mumbai", defaultShared: true },
  country: { label: "Country", placeholder: "e.g. India", defaultShared: true },
  language: { label: "Preferred Language", placeholder: "e.g. English", defaultShared: true },
  currency: { label: "Currency", placeholder: "e.g. INR", defaultShared: true },
  age: { label: "Age", placeholder: "e.g. 28", defaultShared: false },
  notification_style: { label: "Notification Style", placeholder: "concise / detailed", defaultShared: false },
};

export default function ProfilePage() {
  const router = useRouter();
  const { user, updateUserProfile, logout } = useAuth();

  const [formState, setFormState] = useState<Record<string, { value: any; shared: boolean }>>({});
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getProfile()
      .then((res) => {
        if (!alive) return;
        const prof = res.profile || {};
        const state: Record<string, { value: any; shared: boolean }> = {};
        Object.keys(FIELD_DEFAULTS).forEach((field) => {
          const item = prof[field];
          state[field] = {
            value: item?.value ?? (field === "display_name" ? res.name : ""),
            shared: item?.shared ?? FIELD_DEFAULTS[field].defaultShared,
          };
        });
        setFormState(state);
      })
      .catch((e) => {
        if (alive) setError(String(e));
      });

    return () => {
      alive = false;
    };
  }, [user]);

  const handleChangeValue = (field: string, val: any) => {
    setFormState((prev) => ({
      ...prev,
      [field]: { ...prev[field], value: val },
    }));
  };

  const handleToggleShared = (field: string) => {
    setFormState((prev) => ({
      ...prev,
      [field]: { ...prev[field], shared: !prev[field]?.shared },
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);
    setError(null);
    try {
      await updateUserProfile(formState);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      setError(err?.message || "Failed to save profile changes.");
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return (
      <div className="mx-auto max-w-md card p-8 text-center space-y-4">
        <h1 className="font-serif text-xl text-ink">Login Required</h1>
        <p className="text-sm text-ink-soft">
          Please log in to view and manage your MOSAIC profile.
        </p>
        <Link href="/login" className="btn-primary inline-block">
          Go to Login
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Top Banner */}
      <div className="card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent/15 text-accent font-serif text-xl font-bold border border-accent/20">
            {user.name ? user.name.charAt(0).toUpperCase() : "U"}
          </div>
          <div>
            <h1 className="font-serif text-2xl text-ink">{user.name}</h1>
            <p className="text-sm text-ink-soft">{user.email}</p>
            <span className="inline-block mt-1 text-[11px] font-mono text-ink-faint">
              User ID: {user.id}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            logout();
            router.push("/login");
          }}
          className="rounded-lg border border-red-200 bg-red-50/60 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-colors"
        >
          Log Out
        </button>
      </div>

      {/* Main Profile Form */}
      <form onSubmit={handleSave} className="card p-6 space-y-6">
        <div>
          <h2 className="font-serif text-xl text-ink">Profile & Assistant Context</h2>
          <p className="mt-1 text-sm text-ink-soft">
            Customize your preferences. Toggling &quot;Share with Assistant&quot; controls whether the field is passed into MOSAIC&apos;s system prompt.
          </p>
        </div>

        {savedSuccess && (
          <div className="rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
            Profile preferences saved successfully!
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid gap-6 sm:grid-cols-2">
          {Object.keys(FIELD_DEFAULTS).map((field) => {
            const config = FIELD_DEFAULTS[field];
            const state = formState[field] || { value: "", shared: config.defaultShared };
            return (
              <div key={field} className="space-y-2 rounded-lg border border-line/70 p-4 bg-paper/50">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold uppercase tracking-wider text-ink">
                    {config.label}
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-soft">
                    <input
                      type="checkbox"
                      checked={state.shared}
                      onChange={() => handleToggleShared(field)}
                      className="rounded border-line text-accent focus:ring-accent"
                    />
                    <span>Shared</span>
                  </label>
                </div>
                <input
                  type="text"
                  value={state.value || ""}
                  onChange={(e) => handleChangeValue(field, e.target.value)}
                  placeholder={config.placeholder}
                  className="w-full rounded-md border border-line bg-paper px-3 py-1.5 text-sm text-ink outline-none focus:border-accent"
                />
              </div>
            );
          })}
        </div>

        <div className="flex justify-end pt-2">
          <button type="submit" disabled={saving} className="btn-primary px-6">
            {saving ? "Saving…" : "Save Profile Preferences"}
          </button>
        </div>
      </form>
    </div>
  );
}
