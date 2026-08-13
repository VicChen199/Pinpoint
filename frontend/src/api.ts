import type { Document, Pin } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth(): Promise<{ ok: boolean }> {
  return request("/api/health");
}

export function listDocuments(): Promise<Document[]> {
  return request("/api/documents");
}

export function getDocument(id: string): Promise<Document> {
  return request(`/api/documents/${id}`);
}

export function getPins(id: string): Promise<{ pins: Pin[] }> {
  return request(`/api/documents/${id}/pins`);
}

export function explainPin(
  documentId: string,
  pinId: string,
  body: { phrase: string; context: string; document_type: string },
): Promise<{ explanation: string }> {
  return request(`/api/documents/${documentId}/pins/${pinId}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function documentFileUrl(id: string): string {
  return `/api/documents/${id}/file`;
}
