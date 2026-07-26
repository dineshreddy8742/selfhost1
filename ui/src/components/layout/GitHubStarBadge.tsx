"use client";

import posthog from "posthog-js";
import { useEffect, useState } from "react";

import { PostHogEvent } from "@/constants/posthog-events";
import { cn } from "@/lib/utils";

interface GitHubStarBadgeProps {
  className?: string;
  label?: string;
  showCount?: boolean;
  source: string;
}

export function GitHubStarBadge({ className, label, showCount, source }: GitHubStarBadgeProps) {
  return null;
}
