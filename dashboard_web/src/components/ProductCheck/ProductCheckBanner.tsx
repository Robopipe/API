import { useProductMatch } from "../../hooks/useProductMatch";
import { useAppState } from "../../provider";

/**
 * Thin warning strip shown while no products have committed for longer than
 * the idle timeout (or the learned inter-product interval once calibrated) —
 * either the line is stopped or the model does not recognize what is on it.
 * A stopped line records no wrong data, so nothing here blocks or auto-stops;
 * the Stop button just lets the operator end the run without hunting for the
 * header control. Clears itself when products commit again.
 */
export const ProductCheckBanner = () => {
  const { running, toggleRunning } = useAppState();
  const status = useProductMatch();

  if (!running || status?.state !== "starved") return null;

  return (
    <div className="fixed inset-x-0 bottom-2 z-40 flex justify-center pointer-events-none">
      <div className="flex items-center gap-3 py-2 px-4 mx-2 rounded-xl bg-pear-500 text-gray-950 text-sm font-medium shadow-lg pointer-events-auto">
        <span>
          No products detected for a while — line stopped or model not
          recognizing the current product.
        </span>
        <button
          className="shrink-0 py-1.5 px-4 rounded-lg bg-red-500/90 hover:bg-red-500 text-white cursor-pointer transition-colors"
          onClick={toggleRunning}
        >
          Stop
        </button>
      </div>
    </div>
  );
};
