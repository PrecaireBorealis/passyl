"use client";
import { useEffect, useRef } from "react";
import { useApp } from "@/lib/state";

export default function AgentTrace() {
  const { trace } = useApp();
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [trace]);
  return (
    <div className="w-[420px] h-[740px] bg-white rounded-xl border flex flex-col">
      <div className="px-4 py-3 border-b">
        <div className="font-semibold text-sm">Agent trace</div>
        <div className="text-xs text-gray-500">Every tool call, with its time. Numbers on screen come from these tools, not the LLM.</div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4 font-mono text-[12px]">
        {trace.length === 0 && <div className="text-gray-400">Ask something to see the agent work.</div>}
        {trace.map((t, i) => (
          <div key={i}>
            <div className="text-gray-500 mb-1">› {t.turn}</div>
            <ol className="space-y-1">
              {t.items.map((x, j) => (
                <li key={j} className="flex gap-2 animate-[fadein_.3s_ease]" style={{ animationDelay: `${j * 120}ms` }}>
                  <span className="text-ok">✓</span>
                  <span className="w-28 shrink-0 font-semibold">{x.tool}</span>
                  <span className="flex-1 text-gray-700">{x.summary}</span>
                  <span className="text-gray-400 w-14 text-right">{x.ms} ms</span>
                </li>
              ))}
            </ol>
          </div>
        ))}
        <div ref={end} />
      </div>
    </div>
  );
}
