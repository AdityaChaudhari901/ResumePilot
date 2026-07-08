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
  provider: string;
  modelReference: string;
  gatewayUrl: string;
  dashboardUrl: string;
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
  commands: {
    configure: string;
    gateway: string;
    dashboard: string;
    setModel: string;
  };
}
