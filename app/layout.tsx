import type { Metadata } from "next";
import "./globals.css";
import "reactflow/dist/style.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import Assistant from "@/components/Assistant";

export const metadata: Metadata = {
  title: "MOSAIC | Personal Intelligence Workspace",
  description:
    "A proactive personal intelligence system: it builds a model of your world, watches the outside world, and alerts you when the two collide.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans min-h-screen bg-paper flex flex-col justify-between">
        <div>
          <Header />
          <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-8">{children}</main>
        </div>
        <Footer />
        <Assistant />
      </body>
    </html>
  );
}
