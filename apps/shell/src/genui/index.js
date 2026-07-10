/* index.js — the generative-UI barrel. Importing this triggers each component's
   registerTool() side-effect, then re-exports the registry contract. Consumers
   (panes.jsx, tests) import from here so the registry is fully populated. */
import "./FlagEditor.jsx";
import "./ContractBuilder.jsx";
import "./CriterionBuilder.jsx";
import "./KbPicker.jsx";
import "./VerdictCard.jsx";
import "./CalibrationChart.jsx";
import "./AgentEditor.jsx";
import "./AuditView.jsx";
import "./JudgeEditor.jsx";
import "./JudgeBuilder.jsx";
import "./RunPanel.jsx";
import "./CaseCard.jsx";
import "./ScorecardCard.jsx";
import "./IngestPreviewCard.jsx";
import "./ToolBuilder.jsx";
import "./ReadinessCard.jsx";
import "./ReliabilityCard.jsx";
import "./SweepCard.jsx";
import "./CriterionJuteBuilder.jsx";

export { renderTool, registerTool, getTool, KNOWN_TOOLS } from "./registry.js";

export { default as FlagEditor } from "./FlagEditor.jsx";
export { default as ContractBuilder } from "./ContractBuilder.jsx";
export { default as CriterionBuilder } from "./CriterionBuilder.jsx";
export { default as KbPicker } from "./KbPicker.jsx";
export { default as VerdictCard } from "./VerdictCard.jsx";
export { default as CalibrationChart } from "./CalibrationChart.jsx";
export { default as AgentEditor } from "./AgentEditor.jsx";
export { default as AuditView } from "./AuditView.jsx";
export { default as JudgeEditor } from "./JudgeEditor.jsx";
export { default as JudgeBuilder } from "./JudgeBuilder.jsx";
export { default as RunPanel } from "./RunPanel.jsx";
export { default as CaseCard } from "./CaseCard.jsx";
export { default as ScorecardCard } from "./ScorecardCard.jsx";
export { default as IngestPreviewCard } from "./IngestPreviewCard.jsx";
export { default as ToolBuilder } from "./ToolBuilder.jsx";
export { default as ReadinessCard } from "./ReadinessCard.jsx";
export { default as ReliabilityCard } from "./ReliabilityCard.jsx";
export { default as SweepCard } from "./SweepCard.jsx";
export { default as CriterionJuteBuilder } from "./CriterionJuteBuilder.jsx";
