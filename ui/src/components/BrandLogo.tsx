import { cn } from "@/lib/utils";

export function BrandLogo({
  className,
  inverse = false,
  mark = false,
}: {
  className?: string;
  inverse?: boolean;
  mark?: boolean;
}) {
  const logoColor = inverse ? "text-white" : "text-foreground";
  
  if (mark) {
    return (
      <div className={cn("flex items-center gap-1.5", className)}>
        <svg className="h-6 w-6 text-cta" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2v20M17 5v14M22 9v6M7 5v14M2 9v6" />
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2 font-bold tracking-tight select-none", className)}>
      <svg className="h-6 w-6 text-cta animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v20M17 5v14M22 9v6M7 5v14M2 9v6" />
      </svg>
      <span className={cn("text-lg font-extrabold tracking-tight", logoColor)}>
        Dailsmart <span className="text-cta">AI</span>
      </span>
    </div>
  );
}
