'use client';

import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useEffect, useState } from 'react';

const SPRING = { type: 'spring' as const, duration: 0.55, bounce: 0 };

/* Cycles through a list of words in place, animating width to fit
   each word and sliding/fading them through the same baseline.
   Marked as a span so it embeds inside an <h1> naturally. */
export function CyclingWord({
  words,
  intervalMs = 2400,
  className,
  color,
}: {
  words: string[];
  intervalMs?: number;
  className?: string;
  color?: string;
}) {
  const [i, setI] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (reduce || words.length <= 1) return;
    const id = window.setInterval(() => {
      setI((prev) => (prev + 1) % words.length);
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, words.length, reduce]);

  /* Word swap: outgoing slides up & blurs out; incoming rises & sharpens.
     Width animates with motion.span to absorb length change without
     breaking the line. */
  return (
    <motion.span
      layout
      transition={SPRING}
      className={`relative inline-flex items-baseline overflow-hidden align-baseline ${className ?? ''}`}
      style={{
        color,
        verticalAlign: 'baseline',
      }}
    >
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={words[i]}
          layout
          initial={reduce ? false : { y: '0.55em', opacity: 0, filter: 'blur(4px)' }}
          animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
          exit={reduce ? { opacity: 0 } : { y: '-0.55em', opacity: 0, filter: 'blur(4px)' }}
          transition={SPRING}
          className="inline-block whitespace-nowrap"
          style={{ willChange: 'transform, opacity, filter' }}
        >
          {words[i]}
        </motion.span>
      </AnimatePresence>
    </motion.span>
  );
}
