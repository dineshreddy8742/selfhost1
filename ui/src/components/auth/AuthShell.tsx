// Shared dark two-column auth shell, used by BOTH the Stack Auth handler
// (/handler/[...stack], cloud) and the local/OSS auth pages (/auth/login,
// /auth/signup). LEFT: a centered card that wraps the auth form (`children`).
// RIGHT (lg+ only): a brand/value panel with the DailSmart logo and feature highlights.
// Mobile collapses to the single card column.

import { Bot, PhoneCall, ShieldCheck, Sparkles, Zap } from "lucide-react";
import type { ReactNode } from "react";

import { BrandLogo } from "@/components/BrandLogo";

const VALUE_PROPS = [
  {
    icon: PhoneCall,
    title: "24/7 Automated Calling",
    desc: "Handle customer support & outbound campaigns without waiting queues or human fatigue.",
  },
  {
    icon: Bot,
    title: "Human-Like Voice Conversations",
    desc: "Natural speech and active listening that understands context, tone, and customer intent.",
  },
  {
    icon: Zap,
    title: "Smart Lead Qualification & Booking",
    desc: "Instantly capture caller details, qualify leads, and schedule appointments on autopilot.",
  },
  {
    icon: ShieldCheck,
    title: "Live Recordings & Smart Analytics",
    desc: "Access full call audio playback, precise transcripts, and instant AI summaries for every call.",
  },
];

export function AuthShell({
  children,
  enterpriseSlot: _enterpriseSlot,
}: {
  children: ReactNode;
  enterpriseSlot?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen w-full bg-background lg:grid-cols-[52%_48%] xl:grid-cols-[50%_50%]">
      {/* Form column (LEFT) — scrolls and stays centered so tall forms never clip. */}
      <main className="auth-imprint flex min-h-screen flex-col overflow-y-auto">
        <div className="flex min-h-full items-center justify-center p-6 sm:p-10">
          <div className="w-full max-w-md space-y-6 rounded-2xl border border-border/60 bg-card p-6 shadow-lg sm:p-8">
            {/* Mobile-only wordmark (brand panel is hidden) */}
            <div className="lg:hidden">
              <BrandLogo className="h-7" />
            </div>
            {children}
          </div>
        </div>
      </main>

      {/* Brand / value panel (RIGHT) — hidden on mobile */}
      <aside className="relative hidden flex-col justify-between overflow-hidden border-l border-border/60 bg-zinc-950 p-10 lg:flex xl:p-14">
        {/* Ambient depth: soft radial glow behind the content */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 top-1/4 size-[32rem] rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, var(--cta, #f97316), transparent 70%)" }}
        />

        <div className="relative">
          <BrandLogo inverse className="h-8" />
        </div>

        <div className="relative max-w-lg space-y-7 my-auto py-6">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-orange-500/25 bg-orange-500/10 px-3 py-1 text-xs font-medium text-orange-400">
              <Sparkles className="size-3.5" />
              <span>Next-Gen Voice AI Automation</span>
            </div>
            <h1 className="text-3xl font-bold leading-tight tracking-tight text-zinc-50 xl:text-4xl">
              Supercharge your business with smart Voice AI.
            </h1>
            <p className="text-sm leading-relaxed text-zinc-400">
              Deploy intelligent voice agents that answer inbound calls, run outbound campaigns, qualify leads, and delight customers 24/7.
            </p>
          </div>

          <div className="grid gap-3">
            {VALUE_PROPS.map((prop) => {
              const Icon = prop.icon;
              return (
                <div
                  key={prop.title}
                  className="flex items-start gap-3.5 rounded-xl border border-white/[0.08] bg-white/[0.03] p-3.5 transition-colors hover:border-orange-500/30 hover:bg-white/[0.05]"
                >
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20">
                    <Icon className="size-4" />
                  </div>
                  <div className="space-y-0.5">
                    <h2 className="text-sm font-semibold text-zinc-100">{prop.title}</h2>
                    <p className="text-xs leading-relaxed text-zinc-400">{prop.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="relative flex items-center justify-between text-xs text-zinc-500 border-t border-white/[0.06] pt-5">
          <span>Powered by DailSmart AI</span>
          <span>Enterprise-Grade Voice Platform</span>
        </div>
      </aside>
    </div>
  );
}
