import React from "react";
import { Settings, defaultApiUrl } from "../settings";

const emptySettings: Settings = {
  api_url: defaultApiUrl,
  specs: [],
  spec_views: [],
  structure_families: {},
};
const SettingsContext = React.createContext(emptySettings);

export { emptySettings, SettingsContext };
