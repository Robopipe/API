import { useCallback, useEffect, useRef, useState } from "react";

const MIN_PANEL_PCT = 15;

export interface ResizablePanelsProps {
  /** Content for the left panel */
  left: React.ReactNode;
  /** Content for the right panel */
  right: React.ReactNode;
  /** Initial width of the left panel in percent (default: 40) */
  defaultLeftPct?: number;
  /** Called with the final left-panel percentage when the user finishes a drag. */
  onCommit?: (leftPct: number) => void;
  /** Additional className for the outer container */
  className?: string;
}

export const ResizablePanels = ({
  left,
  right,
  defaultLeftPct = 40,
  onCommit,
  className = "",
}: ResizablePanelsProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [leftPct, setLeftPct] = useState(defaultLeftPct);
  const leftPctRef = useRef(defaultLeftPct);
  const dragging = useRef(false);

  const endDrag = useCallback(() => {
    if (!dragging.current) return;
    dragging.current = false;
    document.body.classList.remove("is-resizing-panels");
    onCommit?.(leftPctRef.current);
  }, [onCommit]);

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    document.body.classList.add("is-resizing-panels");
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = (x / rect.width) * 100;
    const clamped = Math.min(
      100 - MIN_PANEL_PCT,
      Math.max(MIN_PANEL_PCT, pct),
    );
    leftPctRef.current = clamped;
    setLeftPct(clamped);
  }, []);

  const onPointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.hasPointerCapture?.(e.pointerId)) {
        target.releasePointerCapture(e.pointerId);
      }
      endDrag();
    },
    [endDrag],
  );

  useEffect(() => {
    return () => {
      document.body.classList.remove("is-resizing-panels");
    };
  }, []);

  return (
    <div ref={containerRef} className={`flex ${className}`}>
      <div
        className="min-w-0 min-h-0 overflow-auto"
        style={{ flexBasis: `${leftPct}%`, flexShrink: 0, flexGrow: 0 }}
      >
        {left}
      </div>

      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className="shrink-0 cursor-col-resize flex items-center justify-center group px-2 touch-none select-none"
        style={{ touchAction: "none" }}
      >
        <div className="w-0.5 h-8 rounded-full bg-gray-700 group-hover:bg-gray-500 transition-colors pointer-events-none" />
      </div>

      <div className="min-w-0 min-h-0 overflow-hidden flex-1">{right}</div>
    </div>
  );
};
