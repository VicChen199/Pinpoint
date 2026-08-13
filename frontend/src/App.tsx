import { useEffect, useState } from "react";
import { ExplanationPanel } from "./panel/ExplanationPanel";
import { useExplanationSession } from "./panel/useExplanationSession";
import type { Pin } from "./types";
import { PdfViewer } from "./viewer/PdfViewer";
import "./App.css";

const SAMPLE_PDF = "/sample.pdf";
const PINS_FIXTURE = "/pins.fixture.json";

function App() {
  const [pins, setPins] = useState<Pin[]>([]);
  const [scale, setScale] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);
  const session = useExplanationSession();

  useEffect(() => {
    fetch(PINS_FIXTURE)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} ${PINS_FIXTURE}`);
        return res.json() as Promise<Pin[]>;
      })
      .then(setPins)
      .catch((err: unknown) => {
        setLoadError(err instanceof Error ? err.message : "Failed to load pins");
      });
  }, []);

  return (
    <div
      className={
        session.panelOpen ? "app-shell app-shell-panel-open" : "app-shell"
      }
    >
      <div className="viewer-column">
        {loadError ? <p className="app-banner">{loadError}</p> : null}
        <PdfViewer
          fileUrl={SAMPLE_PDF}
          pins={pins}
          scale={scale}
          onScaleChange={setScale}
          onPinClick={session.activateFromPage}
          focusPinId={session.focusPinId}
          toolbarExtra={
            session.everOpened && !session.panelOpen ? (
              <button type="button" onClick={session.reopenPanel}>
                Explanations
              </button>
            ) : null
          }
        />
      </div>
      {session.panelOpen ? (
        <div className="panel-column">
          <ExplanationPanel
            current={session.current}
            stack={session.stack}
            allPins={pins}
            stackEpoch={session.stackEpoch}
            onStackToggle={session.toggleStack}
            onClose={session.closePanel}
          />
        </div>
      ) : null}
    </div>
  );
}

export default App;
