// Kanban dynamic execution template, using the existing Claude Code Workflows DSL.
// Compatible with scasella/claude-dynamic-workflows-codex (MIT).
// Read-only research and review; at most one writer at a time.
// Test commands execute OUTSIDE this script through the Kanban evidence bridge.
export const meta = {
  name: "kanban-implementation",
  description: "Investigate, implement, independently review and repair a Kanban task",
  phases: [
    { title: "Inspect", detail: "independent context discovery" },
    { title: "Implement", detail: "one bounded writer" },
    { title: "Review", detail: "independent fresh-context checks" },
    { title: "Repair", detail: "bounded rework if review fails" },
  ],
};

const TASK = (args && args.task) || "";
const REQUIREMENTS = (args && args.acceptance) || [];
const WRITE = Boolean(args && args.allowWrites);
const CRITERIA = REQUIREMENTS.map((v, i) => (i + 1) + ". " + v).join("\n");
const BASE = "Task: " + TASK + "\nAcceptance criteria:\n" + CRITERIA +
  "\nRespect repository instructions and scope. Do not mark tests passed unless run.";
const INSPECT = {
  type: "object", additionalProperties: false, required: ["findings", "risks"],
  properties: {
    findings: { type: "array", items: { type: "string" } },
    risks: { type: "array", items: { type: "string" } },
  },
};
const CHANGE = {
  type: "object", additionalProperties: false, required: ["summary", "files", "unverified"],
  properties: {
    summary: { type: "string" },
    files: { type: "array", items: { type: "string" } },
    unverified: { type: "array", items: { type: "string" } },
  },
};
const REVIEW = {
  type: "object", additionalProperties: false, required: ["verdict", "findings"],
  properties: {
    verdict: { type: "string", enum: ["fail", "pass"] },
    findings: { type: "array", items: { type: "string" } },
  },
};
if (!TASK || REQUIREMENTS.length === 0) {
  return { approved: false, reason: "Missing task or acceptance criteria" };
}
phase("Inspect");
const inspected = await parallel([
  () => agent(BASE + "\nMap existing implementation and dependencies; READ ONLY.",
    {label:"inspect:code", phase:"Inspect", sandbox:"read-only", schema:INSPECT}),
  () => agent(BASE + "\nIdentify missing tests, regressions and security risks; READ ONLY.",
    {label:"inspect:risks", phase:"Inspect", sandbox:"read-only", schema:INSPECT}),
]);
if (!WRITE) {
  return {approved:false, reason:"Read-only run: no changes applied", inspection: inspected};
}
phase("Implement");
// Deliberately serialize all filesystem mutations. Parallel writers create races.
const implementation = await agent(BASE +
  "\nIndependent inspections:\n" + JSON.stringify(inspected) +
  "\nImplement the smallest complete solution in this worktree. Don't change the Kanban journal.",
  {label:"implement", phase:"Implement", sandbox:"workspace-write", schema:CHANGE});
phase("Review");
const reviews = await parallel([
  () => agent(BASE + "\nReview the CURRENT repository changes, not the implementer's verdict. " +
    "Refute correctness and hidden regressions. Use READ ONLY access.",
    {label:"review:correctness", phase:"Review", sandbox:"read-only", schema:REVIEW}),
  () => agent(BASE + "\nReview CURRENT repository changes for security, risk, simplicity " +
    "and missing tests. Use READ ONLY access.",
    {label:"review:security", phase:"Review", sandbox:"read-only", schema:REVIEW}),
]);
const hasBlocker = reviews.some(r => !r || r.verdict !== "pass");
if (!hasBlocker) {
  return {approved:true, implementation, reviews, repair:null};
}
phase("Repair");
const repair = await agent(BASE + "\nFix independently reported issues, with minimal edits:\n" +
  JSON.stringify(reviews) + "\nDo not bypass tests or lower acceptance criteria.",
  {label:"repair", phase:"Repair", sandbox:"workspace-write", schema:CHANGE});
phase("Review final");
const lastReview = await agent(BASE + "\nIndependently evaluate the repaired CURRENT worktree. " +
  "Find unresolved issues and be skeptical; READ ONLY. Earlier issues:\n" +
  JSON.stringify(reviews),
  {label:"review:final", phase:"Review final", sandbox:"read-only", schema:REVIEW});
return {
  approved: Boolean(lastReview && lastReview.verdict === "pass"),
  implementation, reviews, repair, lastReview,
};
