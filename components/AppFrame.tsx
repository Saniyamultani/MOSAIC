"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Assistant from "@/components/Assistant";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { useAuth } from "@/components/AuthProvider";

const PUBLIC_PATHS = new Set(["/login", "/privacy", "/terms"]);

export default function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const isPublicPath = PUBLIC_PATHS.has(pathname);
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (loading) return;
    if (!user && !isPublicPath) router.replace("/login");
    if (user && isLoginPage) router.replace("/");
  }, [isLoginPage, isPublicPath, loading, router, user]);

  if (loading || (!user && !isPublicPath) || (user && isLoginPage)) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-faint">Opening MOSAIC…</p>
      </main>
    );
  }

  if (isLoginPage) {
    return <main className="mx-auto w-full max-w-6xl px-5 py-12">{children}</main>;
  }

  return (
    <>
      <div>
        <Header />
        <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-8">{children}</main>
      </div>
      <Footer />
      {user && <Assistant />}
    </>
  );
}
