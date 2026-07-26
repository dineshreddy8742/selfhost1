"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

interface GoogleSignInButtonProps {
  googleClientId: string;
}

export function GoogleSignInButton({ googleClientId }: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).google?.accounts?.id && buttonRef.current) {
      initializeGoogleSignIn();
    }
  }, [scriptLoaded, googleClientId]);

  const initializeGoogleSignIn = () => {
    try {
      const google = (window as any).google;
      google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleCredentialResponse,
      });

      google.accounts.id.renderButton(buttonRef.current, {
        theme: "outline",
        size: "large",
        type: "standard",
        shape: "rectangular",
        logo_alignment: "left",
        width: buttonRef.current?.offsetWidth || 348,
      });
    } catch (error) {
      console.error("Failed to initialize Google Sign-In:", error);
    }
  };

  const handleCredentialResponse = async (response: any) => {
    const credential = response.credential;
    if (!credential) {
      toast.error("Google authentication failed");
      return;
    }

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(`${backendUrl}/api/v1/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential }),
      });

      const data = await res.json();
      if (!res.ok || !data.token) {
        toast.error(data.detail || "Google Sign-In failed");
        return;
      }

      // Set httpOnly cookies via server route
      await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: data.token, user: data.user }),
      });

      window.location.href = "/after-sign-in";
    } catch (error) {
      toast.error("An error occurred. Please try again.");
    }
  };

  return (
    <div className="w-full space-y-4">
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>
      <div className="w-full flex justify-center">
        <Script
          src="https://accounts.google.com/gsi/client"
          onLoad={() => setScriptLoaded(true)}
          strategy="afterInteractive"
        />
        <div ref={buttonRef} className="w-full flex justify-center" style={{ minHeight: "40px" }} />
      </div>
    </div>
  );
}
