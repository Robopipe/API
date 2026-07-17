import { useProductMatch } from "../../hooks/useProductMatch";
import { useAppState } from "../../provider";

/**
 * Thin warning strip shown while no products have committed for much longer
 * than the learned inter-product interval — either the line is stopped or
 * the model does not recognize what is on it. Banner-only by design: a
 * stopped line records no wrong data, so this never blocks or auto-stops.
 * Clears itself when products commit again.
 */
export const ProductCheckBanner = () => {
  const { running } = useAppState();
  const status = useProductMatch();

  if (!running || status?.state !== "starved") return null;

  return (
    <div className="fixed inset-x-0 bottom-2 z-40 flex justify-center pointer-events-none">
      <div className="py-2 px-4 mx-2 rounded-xl bg-pear-500 text-gray-950 text-sm font-medium shadow-lg">
        No products detected for a while — line stopped or model not
        recognizing the current product.
      </div>
    </div>
  );
};
