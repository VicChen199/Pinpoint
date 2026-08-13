/** Frozen Pinpoint prototype types. Do not add fields. See docs/prototype-contract.md. */

export type Bbox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type Pin = {
  id: string;
  page: number; // 1-based
  x: number;
  y: number;
  text: string;
  bbox: Bbox;
  explanation?: string | null;
};

export type DocumentStatus = "processing" | "ready" | "failed";

export type Document = {
  id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
};
