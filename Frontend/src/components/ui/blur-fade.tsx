"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface BlurFadeProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

/**
 * A restrained, SSR-visible adaptation of Magic UI's Blur Fade component.
 * It never wraps workflow controls or approval surfaces.
 */
export function BlurFade({ children, className, delay = 0 }: BlurFadeProps) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <motion.div
      animate={
        shouldReduceMotion
          ? undefined
          : {
              filter: ["blur(3px)", "blur(0px)"],
              opacity: [0.86, 1],
              y: [7, 0]
            }
      }
      className={cn(className)}
      initial={false}
      transition={{ delay, duration: 0.48, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
