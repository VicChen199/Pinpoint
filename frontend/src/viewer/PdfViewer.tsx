import { useEffect, useState, type ReactNode } from "react";
import { getDocument } from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { UnderlineOverlay } from "../overlay/UnderlineOverlay";
import type { Pin } from "../types";
import "./pdfjs";
import "./PdfViewer.css";

export const MIN_SCALE = 0.5;
export const MAX_SCALE = 2;
export const SCALE_STEP = 0.25;

type PdfViewerProps = {
  fileUrl: string;
  pins: Pin[];
  scale: number;
  onScaleChange: (scale: number) => void;
  onPinClick: (pin: Pin) => void;
  focusPinId?: string | null;
  toolbarExtra?: ReactNode;
};

export function PdfViewer({
  fileUrl,
  pins,
  scale,
  onScaleChange,
  onPinClick,
  focusPinId,
  toolbarExtra,
}: PdfViewerProps) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loading = getDocument({
      url: fileUrl,
      useSystemFonts: true,
      useWasm: false,
    });
    loading.promise
      .then((doc) => {
        if (cancelled) {
          void doc.cleanup();
          return;
        }
        setPdf(doc);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load PDF");
        }
      });
    return () => {
      cancelled = true;
      void loading.destroy();
    };
  }, [fileUrl]);

  useEffect(() => {
    if (!focusPinId) return;
    document.getElementById(`pin-${focusPinId}`)?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
  }, [focusPinId, pdf, scale]);

  const zoomOut = () => onScaleChange(Math.max(MIN_SCALE, roundScale(scale - SCALE_STEP)));
  const zoomIn = () => onScaleChange(Math.min(MAX_SCALE, roundScale(scale + SCALE_STEP)));

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <h1>Pinpoint</h1>
        <div className="pdf-toolbar-actions">
          {toolbarExtra}
          <button type="button" onClick={zoomOut} disabled={scale <= MIN_SCALE}>
            −
          </button>
          <span className="pdf-zoom-label">{Math.round(scale * 100)}%</span>
          <button type="button" onClick={zoomIn} disabled={scale >= MAX_SCALE}>
            +
          </button>
        </div>
      </div>
      <div className="pdf-pages">
        {error ? <p className="pdf-status">{error}</p> : null}
        {!error && !pdf ? <p className="pdf-status">Loading PDF…</p> : null}
        {pdf
          ? Array.from({ length: pdf.numPages }, (_, i) => (
              <PdfPage
                key={`${fileUrl}-${i + 1}`}
                pdf={pdf}
                pageNumber={i + 1}
                scale={scale}
                pins={pins.filter((pin) => pin.page === i + 1)}
                onPinClick={onPinClick}
              />
            ))
          : null}
      </div>
    </div>
  );
}

function roundScale(value: number): number {
  return Math.round(value / SCALE_STEP) * SCALE_STEP;
}

function PdfPage({
  pdf,
  pageNumber,
  scale,
  pins,
  onPinClick,
}: {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  pins: Pin[];
  onPinClick: (pin: Pin) => void;
}) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!canvas) return;
    let cancelled = false;
    let task: RenderTask | undefined;

    void (async () => {
      const page = await pdf.getPage(pageNumber);
      if (cancelled) return;
      const viewport = page.getViewport({ scale });
      const outputScale = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      setSize({ width: viewport.width, height: viewport.height });
      const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined;
      task = page.render({ canvas, viewport, transform });
      try {
        await task.promise;
      } catch (err: unknown) {
        const name = err instanceof Error ? err.name : "";
        if (name !== "RenderingCancelledException") {
          console.error(err);
        }
      }
    })();

    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [canvas, pdf, pageNumber, scale]);

  return (
    <div
      className="pdf-page"
      data-page={pageNumber}
      style={size.width ? { width: size.width, height: size.height } : undefined}
    >
      <canvas ref={setCanvas} />
      <UnderlineOverlay pins={pins} scale={scale} onPinClick={onPinClick} />
    </div>
  );
}
