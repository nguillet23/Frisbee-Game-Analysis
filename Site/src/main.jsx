import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

// HashRouter (not BrowserRouter): GitHub Pages serves plain static files
// with no server-side rewrite rule, so a path-based route like
// /players/2026-x would 404 on refresh/direct link. Hash routes
// (#/players/2026-x) always resolve to index.html first.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>
);
