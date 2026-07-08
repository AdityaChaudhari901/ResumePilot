export interface ResumeUploadResponse {
  resume_id: number;
  candidate_name: string | null;
  status: string;
  warnings: ValidationWarning[];
}

export interface JobAnalysisResponse {
  analysis_id: number;
  report_id: number;
  match_score: number;
  status: string;
}

export type AgentWorkflowMode = "deterministic_fallback" | "crewai";

export type AgentStepName =
  | "jd_parser"
  | "crewai_runtime"
  | "resume_match"
  | "ats_optimizer"
  | "cover_letter"
  | "interview_coach"
  | "validation_gate";

export type AgentStepStatus = "completed" | "degraded" | "failed";

export interface AgentStepTrace {
  name: AgentStepName;
  status: AgentStepStatus;
  summary: string;
  duration_ms?: number | null;
}

export interface AgentTokenUsage {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  reasoning_tokens: number;
  cache_creation_tokens: number;
  successful_requests: number;
}

export interface AgentWorkflowTrace {
  mode: AgentWorkflowMode;
  steps: AgentStepTrace[];
  validation_warning_codes: string[];
  duration_ms?: number | null;
  provider?: string | null;
  model?: string | null;
  token_usage?: AgentTokenUsage | null;
  cost_estimate_usd?: number | null;
  runtime_metadata?: Record<string, string | number | boolean | null>;
}

export interface ReportWorkflowTraceResponse {
  analysis_id: number;
  report_id: number;
  trace: AgentWorkflowTrace;
}

export interface MatchedSkill {
  skill: string;
  match_type: "exact" | "synonym" | "inferred";
  resume_evidence_ids: string[];
  job_evidence_text: string;
  confidence: "high" | "medium" | "low";
}

export interface MissingSkill {
  skill: string;
  importance: "required" | "preferred";
  job_evidence_text: string;
  why_it_matters: string;
  recommendation: string;
}

export interface WeakSkill {
  skill: string;
  resume_evidence_ids: string[];
  reason: string;
}

export interface TailoredBullet {
  bullet: string;
  evidence_ids: string[];
  jd_keywords_used: string[];
  unsupported_claims: string[];
}

export interface AtsKeywordSuggestion {
  keyword: string;
  status: "supported" | "add_only_if_true" | "missing";
  evidence_ids: string[];
  note: string;
}

export interface InterviewQuestionGroup {
  category: string;
  questions: string[];
  suggested_answer_evidence_ids: string[];
}

export interface ValidationWarning {
  code: string;
  message: string;
  evidence_ids: string[];
}

export interface ApplicationReport {
  analysis_id: number;
  resume_id: number;
  job_id: number;
  executive_summary: string;
  match_score: number;
  matched_skills: MatchedSkill[];
  missing_skills: MissingSkill[];
  weak_skills: WeakSkill[];
  tailored_bullets: TailoredBullet[];
  ats_keywords: AtsKeywordSuggestion[];
  cover_letter: string;
  interview_questions: InterviewQuestionGroup[];
  validation_warnings: ValidationWarning[];
  next_actions: string[];
}

export interface HealthStatus {
  status: "ok" | "degraded" | "offline";
  backendReachable: boolean;
  backendBaseUrl: string;
  latencyMs: number;
  message?: string;
  backend?: {
    status?: string;
    app?: string;
    environment?: string;
  };
}

export interface OpenClawStatus {
  llmProvider: string;
  llmModel: string;
  provider: string;
  modelReference: string;
  gatewayUrl: string;
  dashboardUrl: string;
  chatUrl: string;
  rawDashboardUrl: string;
  rawChatUrl: string;
  webSocketUrl: string;
  gateway: {
    reachable: boolean;
    statusCode: number | null;
    checkedAt: string;
  };
  auth: {
    vertexAuth: string;
    hasGatewayToken: boolean;
    projectConfigured: boolean;
    location: string;
  };
  readiness: {
    modelRegistered: boolean;
    agentModelRegistered: boolean;
    mainSessionRegistered: boolean;
    dashboardLaunch: string;
    status: "ready" | "needs_setup";
  };
  commands: {
    configure: string;
    gateway: string;
    dashboard: string;
    setModel: string;
  };
}

export type UsageLimitMetric = "analyses" | "exports" | "crewai_runs";

export interface PlanLimit {
  metric: UsageLimitMetric;
  used: number;
  limit: number | null;
  remaining: number | null;
  reset_at: string;
}

export interface UsageSummaryResponse {
  user_id: number;
  plan: string;
  subscription_status: string;
  current_period_start: string;
  current_period_end: string;
  limits: PlanLimit[];
  total_cost_estimate_usd: number;
  live_crewai_enabled: boolean;
}

export type AuthProvider = "local" | "clerk" | "trusted_headers";

export type DashboardAuthSession =
  | {
      isAuthenticated: true;
      provider: AuthProvider;
      externalId: string;
      email: string | null;
      displayName: string | null;
    }
  | {
      isAuthenticated: false;
      provider: AuthProvider;
      reason: string;
    };
