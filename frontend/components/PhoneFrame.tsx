"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DEMO_MERCHANTS, useApp } from "@/lib/state";

const TABS = [["/", "Home"], ["/chat", "Poochho"], ["/brief", "Report"], ["/benchmark", "Proof"]];

export default function PhoneFrame({ children }: { children: React.ReactNode }) {
  const { merchant } = useApp();
  const path = usePathname();
  const name = DEMO_MERCHANTS.find((m) => m.id === merchant)?.name ?? merchant;
  return (
    <div className="w-[360px] h-[740px] bg-white rounded-[28px] border-[10px] border-gray-900 shadow-xl flex flex-col overflow-hidden shrink-0">
      <div className="px-4 pt-3 pb-2 border-b flex items-center justify-between">
        <div>
          <div className="text-[11px] text-gray-500">VyaparSaathi</div>
          <div className="font-semibold text-sm">{name}</div>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-gray-100 text-gray-600 border">Synthetic data</span>
      </div>
      <div className="flex-1 overflow-y-auto">{children}</div>
      <nav className="border-t grid grid-cols-4 text-xs">
        {TABS.map(([href, label]) => (
          <Link key={href} href={href} className={`py-2.5 text-center ${path === href ? "text-act font-semibold" : "text-gray-500"}`}>{label}</Link>
        ))}
      </nav>
    </div>
  );
}
