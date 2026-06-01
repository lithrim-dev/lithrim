/* index.js — the generative-UI barrel. Importing this triggers each component's
   registerTool() side-effect, then re-exports the registry contract. Consumers
   (panes.jsx, tests) import from here so the registry is fully populated. */
import "./FlagEditor.jsx";
import "./ContractBuilder.jsx";
import "./KbPicker.jsx";

export { renderTool, registerTool, getTool, KNOWN_TOOLS } from "./registry.js";

export { default as FlagEditor } from "./FlagEditor.jsx";
export { default as ContractBuilder } from "./ContractBuilder.jsx";
export { default as KbPicker } from "./KbPicker.jsx";
