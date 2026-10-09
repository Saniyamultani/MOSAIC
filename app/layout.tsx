import type { Metadata } from "next";
import "./globals.css";
import "reactflow/dist/style.css";
import AppFrame from "@/components/AppFrame";
import { AuthProvider } from "@/components/AuthProvider";

export const metadata: Metadata = {
  title: "MOSAIC | Personal Intelligence Workspace",
  description:
    "A proactive personal intelligence system: it builds a model of your world, watches the outside world, and alerts you when the two collide.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans min-h-screen bg-paper">
        <AuthProvider>
          <AppFrame>{children}</AppFrame>
        </AuthProvider>
      </body>
    </html>
  );
}
