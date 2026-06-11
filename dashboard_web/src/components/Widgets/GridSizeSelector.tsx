import { MAX_GRID_SIZE, MIN_GRID_SIZE } from "./widgetStorage";

export interface GridSizeSelectorProps {
  gridSize: number;
  onChange: (size: number) => void;
}

export const GridSizeSelector = ({
  gridSize,
  onChange,
}: GridSizeSelectorProps) => {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange(gridSize - 1)}
        disabled={gridSize <= MIN_GRID_SIZE}
        className="w-7 h-7 rounded-lg bg-gray-800 text-gray-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors text-lg leading-none"
      >
        −
      </button>
      <span className="w-16 text-center text-sm text-white font-medium">
        {gridSize}×{gridSize}
      </span>
      <button
        onClick={() => onChange(gridSize + 1)}
        disabled={gridSize >= MAX_GRID_SIZE}
        className="w-7 h-7 rounded-lg bg-gray-800 text-gray-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors text-lg leading-none"
      >
        +
      </button>
    </div>
  );
};
