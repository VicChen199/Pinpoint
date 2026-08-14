import type { Pin } from "../types";
import "./UnderlineOverlay.css";

/** Extra hit area above the stroke so a tap can land on the underline. */
const HIT_HEIGHT = 16;

type UnderlineOverlayProps = {
  pins: Pin[];
  scale: number;
  onPinClick: (pin: Pin) => void;
};

/**
 * Draws underlines in unscaled PDF page space.
 * left = bbox.x * scale; stroke at bbox.y + bbox.height.
 * Hover restyles only — it must never call /explain.
 */
export function UnderlineOverlay({ pins, scale, onPinClick }: UnderlineOverlayProps) {
  return (
    <div className="underline-overlay">
      {pins.map((pin) => {
        const left = pin.bbox.x * scale;
        const width = Math.max(pin.bbox.width * scale, 8);
        const underlineY = (pin.bbox.y + pin.bbox.height) * scale;
        return (
          <button
            key={pin.id}
            id={`pin-${pin.id}`}
            type="button"
            className="underline-hit"
            style={{
              left,
              width,
              top: underlineY - HIT_HEIGHT + 4,
              height: HIT_HEIGHT,
            }}
            aria-label={`Explain ${pin.text}`}
            onClick={() => onPinClick(pin)}
          />
        );
      })}
    </div>
  );
}
