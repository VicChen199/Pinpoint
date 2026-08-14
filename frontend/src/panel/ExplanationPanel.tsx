import { useEffect, useRef } from "react";
import type { Pin } from "../types";
import type { StackItem } from "./useExplanationSession";
import "./ExplanationPanel.css";

type ExplanationPanelProps = {
  current: Pin | null;
  stack: StackItem[];
  allPins: Pin[];
  stackEpoch: number;
  loadingPinId?: string | null;
  onStackToggle: (pinId: string) => void;
  onClose: () => void;
};

function bodyText(pin: Pin, loading: boolean): string {
  if (loading && !pin.explanation) return "Loading explanation…";
  if (pin.explanation) return pin.explanation;
  return "No explanation is stored on this pin yet.";
}

function duplicateSnippet(pin: Pin, allPins: Pin[]): string | null {
  const sameWord = allPins.filter((other) => other.text === pin.text).length > 1;
  if (!sameWord) return null;
  if (pin.explanation) {
    const clipped = pin.explanation.slice(0, 72).trim();
    return pin.explanation.length > 72 ? `${clipped}…` : clipped;
  }
  return `Occurrence on page ${pin.page}`;
}

export function ExplanationPanel({
  current,
  stack,
  allPins,
  stackEpoch,
  loadingPinId,
  onStackToggle,
  onClose,
}: ExplanationPanelProps) {
  const stackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (stackRef.current) stackRef.current.scrollTop = 0;
  }, [stackEpoch]);

  if (!current) return null;

  return (
    <aside className="explanation-panel" aria-label="Explanations">
      <div className="explanation-panel-header">
        <h2>Explanations</h2>
        <button type="button" className="explanation-panel-close" onClick={onClose}>
          Close
        </button>
      </div>

      <section className="explanation-current" aria-label="Current explanation">
        <p className="explanation-card-kicker">Current</p>
        <h3 className="explanation-card-term">{current.text}</h3>
        <p className="explanation-card-meta">Page {current.page}</p>
        <p className="explanation-card-body">
          {bodyText(current, loadingPinId === current.id)}
        </p>
      </section>

      <div className="explanation-stack" ref={stackRef} aria-label="Earlier explanations">
        {stack.length === 0 ? (
          <p className="explanation-stack-empty">Opened pins will stack here.</p>
        ) : (
          stack.map((item) => {
            const snippet = duplicateSnippet(item.pin, allPins);
            return (
              <button
                key={item.pin.id}
                type="button"
                className="explanation-stack-row"
                aria-expanded={item.expanded}
                onClick={() => onStackToggle(item.pin.id)}
              >
                <span className="explanation-stack-term">{item.pin.text}</span>
                <span className="explanation-stack-meta">Page {item.pin.page}</span>
                {snippet ? <span className="explanation-stack-snippet">{snippet}</span> : null}
                {item.expanded ? (
                  <p className="explanation-stack-body">
                    {bodyText(item.pin, false)}
                  </p>
                ) : null}
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
