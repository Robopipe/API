import { useCallback, useRef, useState } from "react";

const MIN_PANEL_PCT = 15;

export interface ResizablePanelsProps {
  /** Content for the left panel */
  left: React.ReactNode;
  /** Content for the right panel */
  right: React.ReactNode;
  /** Initial width of the left panel in percent (default: 40) */
  defaultLeftPct?: number;
  /** Additional className for the outer container */
  className?: string;
}

export const ResizablePanels = ({
  left,
  right,
  defaultLeftPct = 40,
  className = "",
}: ResizablePanelsProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [leftPct, setLeftPct] = useState(defaultLeftPct);
  const dragging = useRef(false);

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = (x / rect.width) * 100;
    setLeftPct(Math.min(100 - MIN_PANEL_PCT, Math.max(MIN_PANEL_PCT, pct)));
  }, []);

  const onPointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  return (
    <div ref={containerRef} className={`flex ${className}`}>
      <div
        className="min-w-0 overflow-auto"
        style={{ flexBasis: `${leftPct}%`, flexShrink: 0, flexGrow: 0 }}
      >
        {left}
      </div>

      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        className="w-2 shrink-0 cursor-col-resize flex items-center justify-center group"
      >
        <div className="w-0.5 h-8 rounded-full bg-gray-700 group-hover:bg-gray-500 transition-colors" />
      </div>

      <div className="min-w-0 overflow-auto flex-1">{right}</div>
    </div>
  );
};
