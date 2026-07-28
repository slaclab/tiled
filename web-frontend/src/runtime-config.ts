// Shared by vite.config.js (emits the element) and settings.ts (reads it), so
// it must stay free of DOM access: Vite evaluates the config in Node.
export const RUNTIME_CONFIG_ELEMENT_ID = "tiled-runtime-config";

export interface RuntimeConfig {
  root_path: string;
  api_url: string;
}
