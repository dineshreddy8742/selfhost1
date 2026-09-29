"use client";

// Shared dark two-column auth shell, used by BOTH the Stack Auth handler
// (/handler/[...stack], cloud) and the local/OSS auth pages (/auth/login,
// /auth/signup). LEFT: a centered card that wraps the auth form (`children`).
// RIGHT (lg+ only): a brand/value panel with the DailSmart logo and feature highlights.
// Mobile collapses to the single card column.

import { Activity, Bot, KeyRound, PhoneCall, Sparkles, TrendingUp } from "lucide-react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { BrandLogo } from "@/components/BrandLogo";

const SIGNUP_CONTENT = {
  badge: "Automate Today, Lead Tomorrow",
  title: "Launch your Voice AI agents in minutes.",
  subtitle: "Smarter calling and 24/7 lead automation tailored for your business.",
  items: [
    {
      icon: PhoneCall,
      title: "Human-Like Voice Calling",
      desc: "Natural conversations with zero delay that answer questions and engage callers.",
    },
    {
      icon: TrendingUp,
      title: "Auto-Qualify & Capture Leads",
      desc: "Automatically gather customer requirements and book meetings on autopilot.",
    },
    {
      icon: KeyRound,
      title: "BYOK (Bring Your Own Key)",
      desc: "Connect your own AI model keys directly for full control and zero markup.",
    },
  ],
};

const LOGIN_CONTENT = {
  badge: "Automate Today, Lead Tomorrow",
  title: "Welcome back to your Voice AI hub.",
  subtitle: "Your intelligent voice agents are running and handling calls 24/7.",
  items: [
    {
      icon: Activity,
      title: "Live Call Operations",
      desc: "Monitor active inbound and outbound customer calls with instant transcripts.",
    },
    {
      icon: Bot,
      title: "Actionable Call Intelligence",
      desc: "Access audio recordings, caller intent detection, and smart summaries.",
    },
    {
      icon: KeyRound,
      title: "BYOK Flexibility",
      desc: "Manage and switch your AI model keys anytime with complete independence.",
    },
  ],
};

export function AuthShell({
  children,
  enterpriseSlot: _enterpriseSlot,
  mode,
}: {
  children: ReactNode;
  enterpriseSlot?: ReactNode;
  mode?: "login" | "signup";
}) {
  const pathname = usePathname();
  const isSignup = mode === "signup" || (mode ? false : pathname?.includes("signup"));
  const content = isSignup ? SIGNUP_CONTENT : LOGIN_CONTENT;

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

        <div className="relative max-w-md space-y-6 my-auto py-4">
          <div className="space-y-2.5">
            <div className="inline-flex items-center gap-2 rounded-full border border-orange-500/25 bg-orange-500/10 px-3 py-1 text-xs font-medium text-orange-400">
              <Sparkles className="size-3.5" />
              <span>{content.badge}</span>
            </div>
            <h1 className="text-2xl font-bold leading-snug tracking-tight text-zinc-50 xl:text-3xl">
              {content.title}
            </h1>
            <p className="text-sm leading-relaxed text-zinc-400">
              {content.subtitle}
            </p>
          </div>

          <div className="grid gap-2.5">
            {content.items.map((prop) => {
              const Icon = prop.icon;
              return (
                <div
                  key={prop.title}
                  className="flex items-start gap-3 rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 transition-colors hover:border-orange-500/30 hover:bg-white/[0.05]"
                >
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20">
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

        <div className="relative flex items-center justify-between text-xs text-zinc-500 border-t border-white/[0.06] pt-4">
          <span>DailSmart AI</span>
          <span>Enterprise-Grade Voice Platform</span>
        </div>
      </aside>
    </div>
  );
}
