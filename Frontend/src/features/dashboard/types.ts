import type { AuthProvider } from "@/lib/auth-runtime";

export interface ResumeUploadResponse {
  resume_id: number;
  candidate_name: string | null;
  status: string;
  warnings: ValidationWarning[];
}

export type Confidence = "high" | "medium" | "low";

export interface CandidateProfile {
  name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  links: string[];
}

export interface ResumeFact {
  id: string;
  text: string;
  section: string;
  confidence: Confidence;
}

export interface ResumeSkill {
  name: string;
  category: string;
  evidence_ids: string[];
  confidence: Confidence;
}

export interface ResumeProfile {
  resume_id: number;
  candidate: CandidateProfile;
  skills: ResumeSkill[];
  experience: ResumeFact[];
  projects: ResumeFact[];
  education: ResumeFact[];
  certifications: ResumeFact[];
  facts: ResumeFact[];
  warnings: ValidationWarning[];
}

export interface JobAnalysisResponse {
  analysis_id: number;
  report_id: number;
  match_score: number;
  status: string;
}

export interface JobSkill {
  id: string;
  name: string;
  importance: "required" | "preferred" | "keyword";
  evidence_text: string;
  confidence: Confidence;
}

export interface JobProfile {
  job_id: number;
  company: string | null;
  role_title: string | null;
  location: string | null;
  employment_type: string | null;
  required_skills: JobSkill[];
  preferred_skills: JobSkill[];
  responsibilities: string[];
  experience_level: string | null;
  keywords: string[];
  benefits: string[];
  unclear_items: string[];
  warnings: ValidationWarning[];
}

export type JobPreviewStatus =
  | "ready"
  | "needs_review"
  | "blocked_private"
  | "too_short"
  | "missing_requirements";

export interface JobPreviewQualityCheck {
  code: string;
  status: "pass" | "warn" | "fail";
  message: string;
}

export interface JobPreviewResponse {
  job_url: string;
  profile: JobProfile;
  raw_text_char_count: number;
  status: JobPreviewStatus;
  parser: string;
  quality_checks: JobPreviewQualityCheck[];
}

export type ApplicationStatus = "draft" | "reviewed" | "analyzed" | "exported" | "applied";

export interface ApplicationItem {
  id: number;
  status: ApplicationStatus;
  job_url: string;
  company: string | null;
  role: string | null;
  resume_id: number | null;
  job_id: number | null;
  analysis_id: number | null;
  report_id: number | null;
  match_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationListResponse {
  items: ApplicationItem[];
  count: number;
}

export type TailoredResumeDraftStatus = "draft" | "reviewed" | "exported";
export type TailoredResumeItemStatus = "pending" | "accepted" | "rejected";
export type ReportExportFormat = "markdown" | "docx" | "latex" | "pdf";
export type TailoredResumeExportFormat = Exclude<ReportExportFormat, "markdown">;

export interface TailoredResumeItem {
  id: string;
  source_bullet: string;
  suggested_bullet: string;
  edited_bullet: string | null;
  evidence_ids: string[];
  evidence_labels: string[];
  evidence_texts: string[];
  jd_keywords_used: string[];
  unsupported_claims: string[];
  status: TailoredResumeItemStatus;
  validation_warnings: ValidationWarning[];
}

export interface TailoredResumeDraft {
  id: number;
  application_id: number;
  report_id: number;
  status: TailoredResumeDraftStatus;
  items: TailoredResumeItem[];
  accepted_count: number;
  rejected_count: number;
  pending_count: number;
  export_ready: boolean;
  created_at: string;
  updated_at: string;
}

export interface TailoredResumeItemUpdate {
  status?: TailoredResumeItemStatus;
  edited_bullet?: string;
  reset_edited_bullet?: boolean;
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

export interface ReportHistoryItem {
  report_id: number;
  analysis_id: number;
  resume_id: number;
  job_id: number;
  company: string | null;
  role: string | null;
  resume_candidate_name: string | null;
  status: string;
  match_score: number;
  workflow_mode: string;
  validation_warnings_count: number;
  matched_skills_count: number;
  missing_skills_count: number;
  weak_skills_count: number;
  created_at: string;
}

export interface ReportHistoryResponse {
  items: ReportHistoryItem[];
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

export type { AuthProvider };

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
      canSignIn: boolean;
    };
