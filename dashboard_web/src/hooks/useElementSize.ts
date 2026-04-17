import { useLayoutEffect, useRef, useState } from "react";

export interface ElementSize {
  width: number;
  height: number;
}

export function useElementSize<T extends HTMLElement>(): [
  React.RefObject<T | null>,
  ElementSize,
] {
  const ref = useRef<T>(null);
  const [size, setSize] = useState<ElementSize>({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;

    let rafId: number | null = null;
    let pending: ElementSize | null = null;

    const flush = () => {
      rafId = null;
      if (pending) {
        const next = pending;
        pending = null;
        setSize((prev) =>
          prev.width === next.width && prev.height === next.height ? prev : next,
        );
      }
    };

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      pending = { width, height };
      if (rafId === null) {
        rafId = requestAnimationFrame(flush);
      }
    });

    observer.observe(element);

    const rect = element.getBoundingClientRect();
    setSize({ width: rect.width, height: rect.height });

    return () => {
      observer.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, []);

  return [ref, size];
}
