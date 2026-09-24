import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base + HashRouter (see src/main.jsx) so the built site works
// unmodified whether it's served from a GitHub Pages project subpath
// (https://<user>.github.io/<repo>/) or any other path depth, with no
// extra GH Pages SPA-fallback (404.html) trickery needed.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
