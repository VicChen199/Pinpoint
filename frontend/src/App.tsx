import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  documentFileUrl,
  explainPin,
  getDocument,
  getPins,
  listDocuments,
  uploadDocument,
} from "./api";
import { ExplanationPanel } from "./panel/ExplanationPanel";
import { useExplanationSession } from "./panel/useExplanationSession";
import type { Document, Pin } from "./types";
import { PdfViewer } from "./viewer/PdfViewer";
import "./App.css";

const POLL_MS = 1000;
const CRAFT_QUE_URL = "/craft-que.pdf";

function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [status, setStatus] = useState<Document["status"] | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [pins, setPins] = useState<Pin[]>([]);
  const [scale, setScale] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingPinId, setLoadingPinId] = useState<string | null>(null);
  const session = useExplanationSession();
  const sessionRef = useRef(session);
  sessionRef.current = session;

  const refreshList = useCallback(async () => {
    const docs = await listDocuments();
    setDocuments(docs);
    return docs;
  }, []);

  useEffect(() => {
    void refreshList().catch((err: unknown) => {
      setLoadError(err instanceof Error ? err.message : "Failed to list documents");
    });
  }, [refreshList]);

  useEffect(() => {
    sessionRef.current.reset();
    setPins([]);
    setFileUrl(null);
    setStatus(null);
    setLoadError(null);
    setLoadingPinId(null);
    if (!activeId) return;

    let cancelled = false;

    const loadReady = async (id: string) => {
      const { pins: nextPins } = await getPins(id);
      if (cancelled) return;
      setPins(nextPins);
      setFileUrl(documentFileUrl(id));
      setStatus("ready");
    };

    const poll = async () => {
      try {
        const doc = await getDocument(activeId);
        if (cancelled) return;
        setStatus(doc.status);
        await refreshList();
        if (doc.status === "ready") {
          await loadReady(activeId);
          return;
        }
        if (doc.status === "failed") {
          setLoadError("Processing failed for this document.");
          setPins([]);
          setFileUrl(documentFileUrl(activeId));
          return;
        }
        window.setTimeout(() => {
          if (!cancelled) void poll();
        }, POLL_MS);
      } catch (err: unknown) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load document");
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
    };
  }, [activeId, refreshList]);

  const startUpload = async (file: File) => {
    setBusy(true);
    setLoadError(null);
    try {
      const created = await uploadDocument(file);
      await refreshList();
      setActiveId(created.id);
      setStatus(created.status);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const onPickFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void startUpload(file);
  };

  const onUseCraftQue = async () => {
    setBusy(true);
    setLoadError(null);
    try {
      const res = await fetch(CRAFT_QUE_URL);
      if (!res.ok) throw new Error(`Could not read ${CRAFT_QUE_URL}`);
      const blob = await res.blob();
      const file = new File([blob], "craft-que.pdf", { type: "application/pdf" });
      await startUpload(file);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : "Failed to load craft-que.pdf");
      setBusy(false);
    }
  };

  const onPinClick = (pin: Pin) => {
    if (!activeId) return;
    session.activateFromPage(pin);
    if (pin.explanation) return;

    setLoadingPinId(pin.id);
    void explainPin(activeId, pin.id, {
      phrase: pin.text,
      document_type: "unknown",
    })
      .then(({ explanation }) => {
        setPins((prev) =>
          prev.map((item) =>
            item.id === pin.id ? { ...item, explanation } : item,
          ),
        );
        session.applyExplanation(pin.id, explanation);
      })
      .catch((err: unknown) => {
        setLoadError(err instanceof Error ? err.message : "Explain failed");
      })
      .finally(() => {
        setLoadingPinId((current) => (current === pin.id ? null : current));
      });
  };

  const active = documents.find((doc) => doc.id === activeId);

  return (
    <div
      className={
        session.panelOpen ? "app-shell app-shell-panel-open" : "app-shell"
      }
    >
      <aside className="doc-column" aria-label="Documents">
        <p className="doc-heading">Documents</p>
        <button type="button" disabled={busy} onClick={() => void onUseCraftQue()}>
          Open craft-que.pdf
        </button>
        <label className="doc-upload">
          Upload PDF
          <input type="file" accept="application/pdf" onChange={onPickFile} />
        </label>
        <ul className="doc-list">
          {documents.length === 0 ? (
            <li className="doc-empty">No uploads yet.</li>
          ) : (
            documents.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  className={
                    doc.id === activeId ? "doc-item doc-item-active" : "doc-item"
                  }
                  onClick={() => setActiveId(doc.id)}
                >
                  <span className="doc-item-name">{doc.filename}</span>
                  <span className="doc-item-status">{doc.status}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>
      <div className="viewer-column">
        {loadError ? <p className="app-banner">{loadError}</p> : null}
        {status === "processing" ? (
          <p className="app-banner">
            Processing {active?.filename ?? "document"}…
          </p>
        ) : null}
        {fileUrl ? (
          <PdfViewer
            fileUrl={fileUrl}
            pins={status === "ready" ? pins : []}
            scale={scale}
            onScaleChange={setScale}
            onPinClick={onPinClick}
            focusPinId={session.focusPinId}
            toolbarExtra={
              session.everOpened && !session.panelOpen ? (
                <button type="button" onClick={session.reopenPanel}>
                  Explanations
                </button>
              ) : null
            }
          />
        ) : (
          <div className="app-placeholder">
            <h1>Pinpoint</h1>
            <p>
              {status === "processing"
                ? "Extracting terms…"
                : "Open craft-que.pdf or upload a PDF to underline terms."}
            </p>
          </div>
        )}
      </div>
      {session.panelOpen ? (
        <div className="panel-column">
          <ExplanationPanel
            current={session.current}
            stack={session.stack}
            allPins={pins}
            stackEpoch={session.stackEpoch}
            loadingPinId={loadingPinId}
            onStackToggle={session.toggleStack}
            onClose={session.closePanel}
          />
        </div>
      ) : null}
    </div>
  );
}

export default App;
