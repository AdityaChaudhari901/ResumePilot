"use client";

import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/lib/cn";

/**
 * Brand-adapted from Aceternity UI's Spotlight New registry component.
 * Decorative only, clipped by its parent, and static for reduced-motion users.
 */
export function Spotlight({ className }: { className?: string }) {
  const shouldReduceMotion = useReducedMotion();
  const animation = shouldReduceMotion
    ? undefined
    : { opacity: [0.56, 0.9, 0.56], x: [-28, 28, -28], y: [0, 14, 0] };

  return (
    <div
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      <motion.div
        animate={animation}
        className="rp-spotlight-beam absolute -left-72 -top-80 h-[48rem] w-[48rem] rounded-full"
        transition={{ duration: 12, ease: "easeInOut", repeat: Infinity }}
      />
      <motion.div
        animate={
          shouldReduceMotion
            ? undefined
            : { opacity: [0.28, 0.52, 0.28], x: [24, -24, 24], y: [0, -10, 0] }
        }
        className="rp-spotlight-beam absolute -bottom-96 -right-80 h-[44rem] w-[44rem] rounded-full"
        transition={{ duration: 15, ease: "easeInOut", repeat: Infinity }}
      />
    </div>
  );
}
