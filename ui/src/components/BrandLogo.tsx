import Image from "next/image";

import { cn } from "@/lib/utils";

// DailSmart brand logo — uses the official ds* circular mark.
// Modes:
//   mark=true  → icon only (sidebar collapsed / icon-only contexts)
//   default    → icon + "DailSmart" wordmark  (auth light panel)
//   inverse    → icon + white wordmark         (auth dark panel)

export function BrandLogo({
  className,
  inverse = false,
  mark = false,
}: {
  className?: string;
  inverse?: boolean;
  mark?: boolean;
}) {
  const textColor = inverse ? "text-white" : "text-foreground";

  if (mark) {
    // Icon-only: used in sidebar header (collapsed or alongside nav links)
    return (
      <div className={cn("flex items-center", className)}>
        <Image
          src="/dailsmart-logo.png"
          alt="DailSmart"
          width={32}
          height={32}
          className="rounded-full object-cover"
          priority
        />
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2.5 select-none", className)}>
      <Image
        src="/dailsmart-logo.png"
        alt="DailSmart"
        width={32}
        height={32}
        className="rounded-full object-cover shrink-0"
        priority
      />
      <span className={cn("text-lg font-extrabold tracking-tight leading-none", textColor)}>
        Dail<span className="text-cta">Smart</span>
      </span>
    </div>
  );
}
