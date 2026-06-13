'use client';

import { motion, useReducedMotion } from 'motion/react';
import { ReactNode } from 'react';

/* Lightweight scroll-triggered reveal. Single source for all
   "rises into place" animations on the landing page so timing
   stays consistent. Respects prefers-reduced-motion. */
export function Reveal({
  children,
  delay = 0,
  y = 14,
  duration = 0.7,
  as: Component = 'div',
  className,
  once = true,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  duration?: number;
  as?: 'div' | 'section' | 'article' | 'header' | 'footer' | 'span';
  className?: string;
  once?: boolean;
}) {
  const reduce = useReducedMotion();
  const MotionTag = motion[Component] as typeof motion.div;

  if (reduce) {
    const Tag = Component as 'div';
    return <Tag className={className}>{children}</Tag>;
  }

  return (
    <MotionTag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, amount: 0.2 }}
      transition={{
        type: 'spring',
        bounce: 0,
        duration,
        delay,
      }}
    >
      {children}
    </MotionTag>
  );
}
