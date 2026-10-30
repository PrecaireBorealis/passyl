import type { Metadata } from "next";
import { Suspense } from "react";
import AgentTrace from "@/components/AgentTrace";
import DemoControls from "@/components/DemoControls";
import PhoneFrame from "@/components/PhoneFrame";
import { AppState } from "@/lib/state";
import "./globals.css";

export const metadata: Metadata = { title: "VyaparSaathi AI", description: "AI growth partner for Paytm merchants" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppState>
          <main className="min-h-screen flex items-start justify-center gap-6 p-6">
            <div className="space-y-3">
              <PhoneFrame><Suspense>{children}</Suspense></PhoneFrame>
              <Suspense><DemoControls /></Suspense>
            </div>
            <AgentTrace />
          </main>
        </AppState>
      </body>
    </html>
  );
}
