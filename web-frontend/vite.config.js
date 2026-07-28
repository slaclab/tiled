import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteRequire } from "vite-require";
import { webcrypto as crypto } from "crypto";
import { RUNTIME_CONFIG_ELEMENT_ID } from "./src/runtime-config";

// vite.config.js
if (!global.crypto) {
  global.crypto = require("crypto");
  global.crypto.getRandomValues = (arr) =>
    require("crypto").randomFillSync(arr);
}

const productionBase = process.env.TILED_BUILD_PUBLIC_PATH || "./";

// The deployment prefix is unknown at build time, so the built index.html is a
// Jinja2 template that tiled.server.app renders per-request. These names must
// match _UI_TEMPLATE_VARIABLES in tiled/server/app.py.
const jinjaVar = (name) => `{{ ${name} }}`;

const tiledRuntimeConfig = () => ({
  name: "tiled-runtime-config",
  apply: "build",
  transformIndexHtml: () => [
    {
      tag: "base",
      attrs: { href: jinjaVar("tiled_runtime_base") },
      injectTo: "head-prepend",
    },
    {
      tag: "script",
      attrs: { type: "application/json", id: RUNTIME_CONFIG_ELEMENT_ID },
      children: jinjaVar("tiled_runtime_config"),
      injectTo: "head-prepend",
    },
  ],
});

export default defineConfig(({ command }) => ({
  base: command === "build" ? productionBase : "/ui/",
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        ws: true,
      },
      "/custom": {
        target: "http://127.0.0.1:8000",
      },
      "/tiled-ui-settings": {
        target: "http://127.0.0.1:8000",
      },
    },
  },
  plugins: [
    tiledRuntimeConfig(),
    viteRequire(),
    react({
      jsxRuntime: "automatic",
      babel: {
        plugins: [],
      },
    }),
  ],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./test/setup.ts",
    include: ["src/components/**/*.test.tsx", "src/**/*.test.tsx"],
  },
}));
