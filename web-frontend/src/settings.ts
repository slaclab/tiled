import {
  RUNTIME_CONFIG_ELEMENT_ID,
  type RuntimeConfig,
} from "./runtime-config";

// Injected by the server into index.html (see tiled/server/app.py). Absent
// under the Vite dev server, which proxies the API at the origin root.
const element = document.getElementById(RUNTIME_CONFIG_ELEMENT_ID);
const config: RuntimeConfig = element?.textContent
  ? JSON.parse(element.textContent)
  : { root_path: "", api_url: "/api/v1" };

const rootPath = config.root_path;
const defaultApiUrl = config.api_url;
const uiBasePath = element
  ? `${rootPath}/ui`
  : import.meta.env.BASE_URL.replace(/\/$/, "");

const tiledUISettingsURL = `${rootPath}/tiled-ui-settings`;

interface Column {
  header: string;
  field: string;
  select_metadata: string;
}

interface Spec {
  spec: string;
  columns: Column[];
  default_columns: string[];
}

interface SpecView {
  spec: string;
  url: string;
}

interface Settings {
  api_url: string;
  specs: Spec[];
  spec_views?: SpecView[];
  structure_families: any;
}

const fetchSettings = async (signal: AbortSignal): Promise<Settings> => {
  const response = await fetch(tiledUISettingsURL, { signal });
  return (await response.json()) as Settings;
};

export { fetchSettings, defaultApiUrl, rootPath, uiBasePath };
export type { Settings };
