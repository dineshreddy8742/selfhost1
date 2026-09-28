// Shared dark two-column auth shell, used by BOTH the Stack Auth handler
// (/handler/[...stack], cloud) and the local/OSS auth pages (/auth/login,
// /auth/signup). LEFT: a centered card that wraps the auth form (`children`).
// RIGHT (lg+ only): a brand/value panel with the Dailsmart logo and proof points.
// Mobile collapses to the single card column.

import type { ReactNode } from "react";

import { BrandLogo } from "@/components/BrandLogo";

const HIGHLIGHTS = [
  "Speech-to-speech",
  "MCP-native",
  "BYOK - any model",
];

export function AuthShell({
  children,
  enterpriseSlot: _enterpriseSlot,
}: {
  children: ReactNode;
  enterpriseSlot?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen w-full bg-background lg:grid-cols-[55%_45%]">
      {/* Form column (LEFT) — scrolls and stays centered so tall forms never
          clip. Carries the giant faded "dograh" imprint along its bottom. */}
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
          className="pointer-events-none absolute -right-24 top-1/3 size-[28rem] rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, var(--cta), transparent 70%)" }}
        />

        <div className="relative">
          <BrandLogo inverse className="h-8" />
        </div>

        <div className="relative max-w-md space-y-5">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-zinc-50 xl:text-4xl">
            The open-source voice AI platform.
          </h1>
          <ul className="flex flex-wrap gap-2">
            {HIGHLIGHTS.map((point) => (
              <li
                key={point}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300"
              >
                {point}
              </li>
            ))}
          </ul>
        </div>

        {/* Spacer to keep layout consistent */}
        <div className="mb-12 xl:mb-16" />
      </aside>
    </div>
  );
}
