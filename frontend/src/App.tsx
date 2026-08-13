import { useEffect, useState } from "react";
import { getHealth } from "./api";
import "./App.css";

function App() {
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((data) => setApiOk(data.ok === true))
      .catch(() => setApiOk(false));
  }, []);

  return (
    <main>
      <h1>Pinpoint</h1>
      <p>Phase 0 scaffold. Viewer, overlay, and panel are Track A.</p>
      <p>
        API:{" "}
        {apiOk === null
          ? "checking…"
          : apiOk
            ? "reachable via /api proxy"
            : "not reachable — start uvicorn on :8000"}
      </p>
    </main>
  );
}

export default App;
