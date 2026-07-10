"use client";

import { ChevronDown, RefreshCcw } from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { AccountSessionCard } from "@/features/dashboard/components/account-session-card";
import { AiWorkflowCard } from "@/features/dashboard/components/ai-workflow-card";
import { ApplicationPipelineCard } from "@/features/dashboard/components/application-pipeline-card";
import { HealthStrip } from "@/features/dashboard/components/health-strip";
import { JobEvidenceReviewCard } from "@/features/dashboard/components/job-evidence-review-card";
import {
  JobListingCard,
  MAX_JOB_TEXT_CHARS,
  MIN_JOB_TEXT_CHARS
} from "@/features/dashboard/components/job-listing-card";
import { OpenClawStatusCard } from "@/features/dashboard/components/openclaw-status-card";
import { ReportHistoryCard } from "@/features/dashboard/components/report-history-card";
import { ReportViewer } from "@/features/dashboard/components/report-viewer";
import { ResumeProfileReviewCard } from "@/features/dashboard/components/resume-profile-review-card";
import { ResumeUploadCard } from "@/features/dashboard/components/resume-upload-card";
import { TailoredResumeWorkspaceCard } from "@/features/dashboard/components/tailored-resume-workspace-card";
import { UsageStatusCard } from "@/features/dashboard/components/usage-status-card";
import {
  WorkflowProgress,
  type WorkflowProgressStep,
  type WorkflowStepId
} from "@/features/dashboard/components/workflow-progress";
import { WorkflowSummaryCard } from "@/features/dashboard/components/workflow-summary-card";
import type {
  AgentWorkflowTrace,
  ApplicationDetail,
  ApplicationItem,
  ApplicationListResponse,
  ApplicationReport,
  ApplicationStatus,
  DashboardAuthSession,
  DownloadExportFormat,
  HealthStatus,
  JobAnalysisResponse,
  JobPreviewResponse,
  JobProfile,
  JobSourceType,
  OpenClawStatus,
  PdfExportResult,
  ReportHistoryItem,
  ReportHistoryResponse,
  ReportExportFormat,
  ReportWorkflowTraceResponse,
  ResumeProfile,
  ResumeUploadResponse,
  TailoredResumeDraft,
  TailoredResumeExportFormat,
  TailoredResumeItemUpdate,
  UsageSummaryResponse,
  WorkflowApprovalDecision,
  WorkflowOperation,
  WorkflowOperationListResponse
} from "@/features/dashboard/types";
import {
  type ApiProblem,
  readApiError,
  readApiProblem
} from "@/features/dashboard/utils/api-error";

interface DashboardStatusPayload {
  activeOperation: WorkflowOperation | null;
  applications: ApplicationItem[];
  auth: DashboardAuthSession | null;
  health: HealthStatus;
  openclaw: OpenClawStatus;
  reports: ReportHistoryItem[];
  usage: UsageSummaryResponse | null;
}

async function fetchDashboardStatus(): Promise<DashboardStatusPayload> {
  const [
    authResponse,
    healthResponse,
    openclawResponse,
    applications,
    reports,
    usage,
    activeOperation
  ] = await Promise.all([
    fetch("/api/auth/session", { cache: "no-store" }),
    fetch("/api/health", { cache: "no-store" }),
    fetch("/api/openclaw/status", { cache: "no-store" }),
    fetchApplications(),
    fetchReportHistory(),
    fetchUsageSummary(),
    fetchActiveAnalysisOperation()
  ]);

  return {
    activeOperation,
    auth: authResponse.ok ? ((await authResponse.json()) as DashboardAuthSession) : null,
    health: (await healthResponse.json()) as HealthStatus,
    openclaw: (await openclawResponse.json()) as OpenClawStatus,
    applications,
    reports,
    usage
  };
}

async function fetchApplications(): Promise<ApplicationItem[]> {
  try {
    const response = await fetch("/api/applications?limit=20", { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    const payload = (await response.json()) as ApplicationListResponse;
    return payload.items;
  } catch {
    return [];
  }
}

async function fetchActiveAnalysisOperation(): Promise<WorkflowOperation | null> {
  try {
    const response = await fetch("/api/operations?limit=20", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as WorkflowOperationListResponse;
    for (const candidate of payload.items) {
      const operation = requireWorkflowOperation(candidate);
      if (isActiveAnalysisOperation(operation)) {
        return operation;
      }
    }
    return null;
  } catch {
    return null;
  }
}

async function fetchApplicationDetail(applicationId: number): Promise<ApplicationDetail> {
  const response = await fetch(`/api/applications/${encodeURIComponent(String(applicationId))}`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return (await response.json()) as ApplicationDetail;
}

async function fetchReportHistory(): Promise<ReportHistoryItem[]> {
  try {
    const response = await fetch("/api/reports?limit=20", { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    const payload = (await response.json()) as ReportHistoryResponse;
    return payload.items;
  } catch {
    return [];
  }
}

async function fetchUsageSummary(): Promise<UsageSummaryResponse | null> {
  try {
    const response = await fetch("/api/usage/summary", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as UsageSummaryResponse;
  } catch {
    return null;
  }
}

async function fetchResumeProfile(resumeId: number): Promise<ResumeProfile> {
  const response = await fetch(`/api/resumes/${encodeURIComponent(String(resumeId))}`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return (await response.json()) as ResumeProfile;
}

async function fetchTailoredResumeDraft(applicationId: number): Promise<TailoredResumeDraft> {
  const response = await fetch(
    `/api/applications/${encodeURIComponent(String(applicationId))}/tailored-resume`,
    {
      cache: "no-store"
    }
  );
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return (await response.json()) as TailoredResumeDraft;
}

interface DashboardShellProps {
  initialAuthSession: DashboardAuthSession;
}

export function DashboardShell({ initialAuthSession }: DashboardShellProps) {
  const [analysis, setAnalysis] = useState<JobAnalysisResponse | null>(null);
  const [activeOperation, setActiveOperation] = useState<WorkflowOperation | null>(null);
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [authSession, setAuthSession] = useState<DashboardAuthSession | null>(
    initialAuthSession
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);
  const [isExportingReport, setIsExportingReport] = useState<ReportExportFormat | null>(null);
  const [isExportingTailoredResume, setIsExportingTailoredResume] =
    useState<TailoredResumeExportFormat | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isLoadingApplications, setIsLoadingApplications] = useState(true);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isPreviewingJob, setIsPreviewingJob] = useState(false);
  const [isLoadingTailoredResume, setIsLoadingTailoredResume] = useState(false);
  const [isUpdatingTailoredResume, setIsUpdatingTailoredResume] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [jobPreview, setJobPreview] = useState<JobPreviewResponse | null>(null);
  const [jobSourceType, setJobSourceType] = useState<JobSourceType>("url");
  const [jobText, setJobText] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [openclaw, setOpenclaw] = useState<OpenClawStatus | null>(null);
  const [report, setReport] = useState<ApplicationReport | null>(null);
  const [reportHistory, setReportHistory] = useState<ReportHistoryItem[]>([]);
  const [reviewedJobProfile, setReviewedJobProfile] = useState<JobProfile | null>(null);
  const [resume, setResume] = useState<ResumeUploadResponse | null>(null);
  const [resumeProfile, setResumeProfile] = useState<ResumeProfile | null>(null);
  const [usage, setUsage] = useState<UsageSummaryResponse | null>(null);
  const [workflowStep, setWorkflowStep] = useState<WorkflowStepId>("job");
  const [workflowTrace, setWorkflowTrace] = useState<AgentWorkflowTrace | null>(null);
  const [activeApplicationId, setActiveApplicationId] = useState<number | null>(null);
  const [allowLiveAiProcessing, setAllowLiveAiProcessing] = useState(false);
  const [tailoredResumeDraft, setTailoredResumeDraft] =
    useState<TailoredResumeDraft | null>(null);
  const workspaceRevisionRef = useRef(0);
  const analysisCommandRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const approvalCommandRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const pdfExportCommandRef = useRef<{ fingerprint: string; key: string } | null>(null);

  function startWorkspaceRequest(): number {
    workspaceRevisionRef.current += 1;
    setIsLoadingTailoredResume(false);
    setIsUpdatingTailoredResume(false);
    return workspaceRevisionRef.current;
  }

  function isCurrentWorkspaceRequest(revision: number): boolean {
    return workspaceRevisionRef.current === revision;
  }

  const loadStatus = useCallback(async () => {
    setIsLoadingStatus(true);
    const status = await fetchDashboardStatus();
    setAuthSession(status.auth);
    setApplications(status.applications);
    setHealth(status.health);
    setOpenclaw(status.openclaw);
    setReportHistory(status.reports);
    setUsage(status.usage);
    setActiveOperation(status.activeOperation);
    if (status.activeOperation) {
      setWorkflowStep("ai");
      const recoveredAnalysis = status.activeOperation.result;
      if (isJobAnalysisResponse(recoveredAnalysis)) {
        setAnalysis(recoveredAnalysis);
        setActiveApplicationId(
          status.applications.find(
            (application) => application.report_id === recoveredAnalysis.report_id
          )?.id ?? null
        );
      }
    }
    setIsLoadingApplications(false);
    setIsLoadingHistory(false);
    setIsLoadingStatus(false);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialStatus() {
      const status = await fetchDashboardStatus();

      if (!isMounted) {
        return;
      }

      setHealth(status.health);
      setAuthSession(status.auth);
      setApplications(status.applications);
      setOpenclaw(status.openclaw);
      setReportHistory(status.reports);
      setUsage(status.usage);
      setActiveOperation(status.activeOperation);
      if (status.activeOperation) {
        setWorkflowStep("ai");
        const recoveredAnalysis = status.activeOperation.result;
        if (isJobAnalysisResponse(recoveredAnalysis)) {
          setAnalysis(recoveredAnalysis);
          setActiveApplicationId(
            status.applications.find(
              (application) => application.report_id === recoveredAnalysis.report_id
            )?.id ?? null
          );
        }
      }
      setIsLoadingApplications(false);
      setIsLoadingHistory(false);
      setIsLoadingStatus(false);
    }

    void loadInitialStatus();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadTailoredResumeDraft() {
      if (!report || !activeApplicationId) {
        setTailoredResumeDraft(null);
        setIsLoadingTailoredResume(false);
        return;
      }

      setIsLoadingTailoredResume(true);
      try {
        const draft = await fetchTailoredResumeDraft(activeApplicationId);
        if (draft.application_id !== activeApplicationId || draft.report_id !== report.analysis_id) {
          throw new Error("Tailored resume draft does not match the active report. Refresh and try again.");
        }
        if (isMounted) {
          setTailoredResumeDraft(draft);
        }
      } catch (error) {
        if (isMounted) {
          setTailoredResumeDraft(null);
          setErrorMessage(
            error instanceof Error ? error.message : "Tailored resume workspace failed to load"
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingTailoredResume(false);
        }
      }
    }

    void loadTailoredResumeDraft();

    return () => {
      isMounted = false;
    };
  }, [activeApplicationId, report]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setErrorMessage(null);
    setFile(event.target.files?.[0] ?? null);
  }

  function clearCurrentAnalysis() {
    setAnalysis(null);
    setActiveOperation(null);
    setReport(null);
    setTailoredResumeDraft(null);
    setWorkflowTrace(null);
  }

  function resetJobReviewForInputChange() {
    startWorkspaceRequest();
    setJobPreview(null);
    setReviewedJobProfile(null);
    setActiveApplicationId(null);
    if (analysis || report || workflowTrace) {
      clearCurrentAnalysis();
    }
    if (workflowStep !== "job") {
      setWorkflowStep("job");
    }
  }

  function handleJobSourceTypeChange(value: JobSourceType) {
    if (value === jobSourceType) {
      return;
    }
    setErrorMessage(null);
    setJobSourceType(value);
    resetJobReviewForInputChange();
  }

  function handleJobUrlChange(value: string) {
    setJobUrl(value);
    resetJobReviewForInputChange();
  }

  function handleJobTextChange(value: string) {
    setJobText(value);
    resetJobReviewForInputChange();
  }

  async function handleJobContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestRevision = startWorkspaceRequest();
    const trimmedJobUrl = jobUrl.trim();
    const trimmedJobText = jobText.trim();

    if (jobSourceType === "url" && !isHttpUrl(trimmedJobUrl)) {
      setErrorMessage("Enter a valid public http(s) job listing URL.");
      return;
    }
    if (
      jobSourceType === "pasted_text" &&
      (trimmedJobText.length < MIN_JOB_TEXT_CHARS || trimmedJobText.length > MAX_JOB_TEXT_CHARS)
    ) {
      setErrorMessage(
        `Paste a job description between ${MIN_JOB_TEXT_CHARS.toLocaleString()} and ${MAX_JOB_TEXT_CHARS.toLocaleString()} characters.`
      );
      return;
    }

    setErrorMessage(null);
    setIsPreviewingJob(true);
    setReviewedJobProfile(null);
    clearCurrentAnalysis();

    try {
      const response = await fetch("/api/jobs/preview", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify(
          jobSourceType === "url"
            ? { job_url: trimmedJobUrl }
            : { job_text: trimmedJobText }
        )
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const preview = (await response.json()) as JobPreviewResponse;
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setJobPreview(preview);
      setWorkflowStep("jobReview");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Job preview failed");
    } finally {
      setIsPreviewingJob(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }

    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/resumes/upload", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const nextResume = (await response.json()) as ResumeUploadResponse;
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setResume(nextResume);
      const profile = await fetchResumeProfile(nextResume.resume_id);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setResumeProfile(profile);
      setAnalysis(null);
      setReport(null);
      setWorkflowTrace(null);
      setWorkflowStep("ai");
      setReportHistory(await fetchReportHistory());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Resume upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resume) {
      setErrorMessage("Upload a resume before analyzing a job.");
      setWorkflowStep("resume");
      return;
    }

    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    setIsAnalyzing(true);
    setAnalysis(null);
    setReport(null);
    setWorkflowTrace(null);

    try {
      const trimmedJobUrl = jobUrl.trim();
      const trimmedJobText = jobText.trim();

      if (!isJobInputValid(jobSourceType, trimmedJobUrl, trimmedJobText)) {
        setErrorMessage(
          jobSourceType === "url"
            ? "Enter a valid public http(s) job listing URL."
            : "Paste the complete job description before running analysis."
        );
        setWorkflowStep("job");
        setIsAnalyzing(false);
        return;
      }
      if (
        !jobPreview ||
        !isJobPreviewCurrent(jobPreview, jobSourceType, trimmedJobUrl, trimmedJobText)
      ) {
        setErrorMessage("Review the extracted job evidence before running analysis.");
        setWorkflowStep(jobPreview ? "jobReview" : "job");
        setIsAnalyzing(false);
        return;
      }
      if (!reviewedJobProfile) {
        setErrorMessage("Save the reviewed job evidence before running analysis.");
        setWorkflowStep("jobReview");
        setIsAnalyzing(false);
        return;
      }

      const analysisRequest = activeApplicationId
        ? {
            resume_id: resume.resume_id,
            application_id: activeApplicationId,
            allow_live_ai_processing: allowLiveAiProcessing
          }
        : {
            resume_id: resume.resume_id,
            job_text:
              jobSourceType === "pasted_text"
                ? jobPreview.reviewed_job_text || trimmedJobText
                : null,
            job_url: jobSourceType === "url" ? jobPreview.job_url ?? trimmedJobUrl : null,
            company: null,
            role: null,
            reviewed_job_profile: reviewedJobProfile,
            allow_live_ai_processing: allowLiveAiProcessing
          };
      const requestFingerprint = JSON.stringify(analysisRequest);
      if (analysisCommandRef.current?.fingerprint !== requestFingerprint) {
        analysisCommandRef.current = {
          fingerprint: requestFingerprint,
          key: crypto.randomUUID()
        };
      }

      const response = await fetch("/api/jobs/analyze", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "idempotency-key": analysisCommandRef.current.key
        },
        body: requestFingerprint
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const responsePayload = (await response.json()) as unknown;
      const outcome = isJobAnalysisResponse(responsePayload)
        ? {
            analysis: responsePayload,
            status: "succeeded" as const
          }
        : await waitForAnalysisOperation(
            requireWorkflowOperation(responsePayload),
            requestRevision,
            isCurrentWorkspaceRequest,
            setActiveOperation
          );
      if (!outcome) {
        return;
      }
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      analysisCommandRef.current = null;
      const didLoadWorkspace = await loadAnalysisWorkspace(outcome.analysis, requestRevision);
      if (!didLoadWorkspace || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }

      if (outcome.status === "waiting_for_approval") {
        setWorkflowStep("ai");
        return;
      }

      setActiveOperation(null);
      setWorkflowStep("report");
    } catch (error) {
      if (error instanceof TerminalOperationError) {
        analysisCommandRef.current = null;
      }
      setErrorMessage(error instanceof Error ? error.message : "Job analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleCancelAnalysis() {
    if (!activeOperation?.cancelable) {
      return;
    }
    try {
      const response = await fetch(
        `/api/operations/${encodeURIComponent(activeOperation.id)}/cancel`,
        { method: "POST" }
      );
      if (!response.ok) {
        throw new Error(await readApiError(response));
      }
      setActiveOperation((await response.json()) as WorkflowOperation);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Analysis cancellation failed");
    }
  }

  async function handleResumeAnalysisStatus() {
    const operation = activeOperation;
    if (!operation || !isActiveAnalysisOperation(operation)) {
      setErrorMessage("There is no active analysis to resume.");
      return;
    }

    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    setIsAnalyzing(true);
    try {
      const latest = await fetchWorkflowOperation(operation.id);
      const outcome = await waitForAnalysisOperation(
        latest,
        requestRevision,
        isCurrentWorkspaceRequest,
        setActiveOperation
      );
      if (!outcome || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      const didLoadWorkspace = await loadAnalysisWorkspace(outcome.analysis, requestRevision);
      if (!didLoadWorkspace || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      if (outcome.status === "waiting_for_approval") {
        setWorkflowStep("ai");
        return;
      }
      analysisCommandRef.current = null;
      approvalCommandRef.current = null;
      setActiveOperation(null);
      setWorkflowStep("report");
    } catch (error) {
      if (error instanceof TerminalOperationError) {
        analysisCommandRef.current = null;
        approvalCommandRef.current = null;
      }
      setErrorMessage(
        error instanceof Error ? error.message : "Analysis status could not be resumed"
      );
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleWorkflowApprovalDecision(decision: WorkflowApprovalDecision) {
    const operation = activeOperation;
    const approval = operation?.approval;
    if (
      !operation ||
      operation.status !== "waiting_for_approval" ||
      !approval ||
      approval.status !== "pending"
    ) {
      setErrorMessage("This live draft is no longer waiting for a decision. Refresh and try again.");
      return;
    }

    const requestRevision = startWorkspaceRequest();
    const requestBody = {
      approval_id: approval.id,
      decision
    };
    const requestFingerprint = JSON.stringify({
      operation_id: operation.id,
      ...requestBody
    });
    if (approvalCommandRef.current?.fingerprint !== requestFingerprint) {
      approvalCommandRef.current = {
        fingerprint: requestFingerprint,
        key: crypto.randomUUID()
      };
    }

    setErrorMessage(null);
    setIsAnalyzing(true);
    setIsSubmittingApproval(true);

    try {
      const response = await fetch(
        `/api/operations/${encodeURIComponent(operation.id)}/approval`,
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "idempotency-key": approvalCommandRef.current.key
          },
          body: JSON.stringify(requestBody)
        }
      );
      if (!response.ok) {
        const message = await readApiError(response);
        if (response.status === 409) {
          const authoritative = await fetchWorkflowOperation(operation.id);
          if (isCurrentWorkspaceRequest(requestRevision)) {
            setActiveOperation(authoritative);
          }
        }
        throw new Error(message);
      }

      const outcome = await waitForAnalysisOperation(
        requireWorkflowOperation((await response.json()) as unknown),
        requestRevision,
        isCurrentWorkspaceRequest,
        setActiveOperation
      );
      if (!outcome || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }

      const didLoadWorkspace = await loadAnalysisWorkspace(outcome.analysis, requestRevision);
      if (!didLoadWorkspace || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }

      approvalCommandRef.current = null;
      analysisCommandRef.current = null;
      if (outcome.status === "waiting_for_approval") {
        setWorkflowStep("ai");
        return;
      }

      setActiveOperation(null);
      setWorkflowStep("report");
    } catch (error) {
      if (error instanceof TerminalOperationError) {
        approvalCommandRef.current = null;
        analysisCommandRef.current = null;
      }
      setErrorMessage(
        error instanceof Error ? error.message : "Live draft decision could not be submitted"
      );
    } finally {
      setIsSubmittingApproval(false);
      setIsAnalyzing(false);
    }
  }

  async function loadReport(reportId: number, requestRevision?: number): Promise<boolean> {
    const [reportResponse, traceResponse, usageSummary] = await Promise.all([
      fetch(`/api/reports/${reportId}`, { cache: "no-store" }),
      fetch(`/api/reports/${reportId}/trace`, { cache: "no-store" }),
      fetchUsageSummary()
    ]);

    if (!reportResponse.ok) {
      throw new Error(await readApiError(reportResponse));
    }

    const nextReport = (await reportResponse.json()) as ApplicationReport;
    const nextTrace = traceResponse.ok
      ? ((await traceResponse.json()) as ReportWorkflowTraceResponse).trace
      : null;
    if (
      requestRevision !== undefined &&
      !isCurrentWorkspaceRequest(requestRevision)
    ) {
      return false;
    }

    setReport(nextReport);
    setUsage(usageSummary);
    setWorkflowTrace(nextTrace);
    return true;
  }

  async function loadAnalysisWorkspace(
    nextAnalysis: JobAnalysisResponse,
    requestRevision: number
  ): Promise<boolean> {
    if (!isCurrentWorkspaceRequest(requestRevision)) {
      return false;
    }

    setAnalysis(nextAnalysis);
    const didLoadReport = await loadReport(nextAnalysis.report_id, requestRevision);
    if (!didLoadReport || !isCurrentWorkspaceRequest(requestRevision)) {
      return false;
    }

    const [nextApplications, nextReportHistory] = await Promise.all([
      fetchApplications(),
      fetchReportHistory()
    ]);
    if (!isCurrentWorkspaceRequest(requestRevision)) {
      return false;
    }

    setApplications(nextApplications);
    setReportHistory(nextReportHistory);
    setActiveApplicationId(
      nextApplications.find((application) => application.report_id === nextAnalysis.report_id)?.id ??
        null
    );
    return true;
  }

  async function handleSelectReport(item: ReportHistoryItem) {
    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    const nextAnalysis: JobAnalysisResponse = {
      analysis_id: item.analysis_id,
      match_score: item.match_score,
      report_id: item.report_id,
      status: item.status
    };
    setAnalysis(nextAnalysis);
    setReport(null);
    setWorkflowTrace(null);
    setWorkflowStep("report");
    setActiveApplicationId(null);
    setResume((currentResume) =>
      currentResume?.resume_id === item.resume_id
        ? currentResume
        : {
            candidate_name: item.resume_candidate_name,
            resume_id: item.resume_id,
            status: "parsed",
            warnings: []
          }
    );
    try {
      const [profile, nextApplications] = await Promise.all([
        fetchResumeProfile(item.resume_id),
        fetchApplications()
      ]);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setResumeProfile(profile);
      setApplications(nextApplications);
      setActiveApplicationId(
        nextApplications.find((application) => application.report_id === item.report_id)?.id ?? null
      );
      const didLoadReport = await loadReport(item.report_id, requestRevision);
      if (!didLoadReport || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
    } catch (error) {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(error instanceof Error ? error.message : "Report history load failed");
      }
    }
  }

  const isJobSourceValid = isJobInputValid(
    jobSourceType,
    jobUrl.trim(),
    jobText.trim()
  );
  const isJobEvidenceReady =
    isJobPreviewCurrent(
      jobPreview,
      jobSourceType,
      jobUrl.trim(),
      jobText.trim()
    ) && Boolean(reviewedJobProfile);
  const isResumeReady = Boolean(resume);
  const hasActiveAnalysisOperation = Boolean(
    activeOperation && isActiveAnalysisOperation(activeOperation)
  );
  const canAnalyze =
    isJobEvidenceReady &&
    isResumeReady &&
    !isAnalyzing &&
    !isSubmittingApproval &&
    !hasActiveAnalysisOperation;
  const workflowSteps = buildWorkflowSteps({
    analysisReady: Boolean(analysis && report),
    currentStep: workflowStep,
    draftReady: Boolean(tailoredResumeDraft?.export_ready),
    jobEvidenceReady: isJobEvidenceReady,
    jobReady: isJobSourceValid,
    resumeReady: isResumeReady
  });

  function handleEditResume() {
    setErrorMessage(null);
    setWorkflowStep(isJobEvidenceReady ? "resume" : jobPreview ? "jobReview" : "job");
  }

  async function handleConfirmJobEvidence(profile: JobProfile) {
    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    if (!jobPreview) {
      setErrorMessage("Preview the job description before saving its evidence.");
      setWorkflowStep("job");
      return;
    }
    if (!jobPreview.reviewed_job_text) {
      setErrorMessage("Job source text is required before its evidence can be saved.");
      setWorkflowStep("job");
      return;
    }

    const isUnchangedSavedReview =
      activeApplicationId !== null &&
      jobPreview.parser === "saved_review" &&
      jobProfilesEqual(profile, jobPreview.profile);
    if (isUnchangedSavedReview) {
      setReviewedJobProfile(profile);
      setWorkflowStep(resume ? "ai" : "resume");
      return;
    }

    try {
      const response = await fetch("/api/applications", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          source_type: jobPreview.source_type,
          job_url: jobPreview.source_type === "url" ? jobPreview.job_url : null,
          job_text:
            jobPreview.source_type === "pasted_text" ? jobPreview.reviewed_job_text : null,
          reviewed_job_text: jobPreview.reviewed_job_text,
          reviewed_job_profile: profile,
          resume_id: resume?.resume_id ?? null
        })
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const application = (await response.json()) as ApplicationItem;
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setActiveApplicationId(application.id);
      const nextApplications = await fetchApplications();
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setApplications(nextApplications);
      setReviewedJobProfile(profile);
      clearCurrentAnalysis();
      setWorkflowStep(resume ? "ai" : "resume");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Application draft save failed");
    }
  }

  function handleOpenJobEvidenceReview() {
    setErrorMessage(null);
    setWorkflowStep(jobPreview ? "jobReview" : "job");
  }

  function handleRunAiFromSummary() {
    setErrorMessage(null);
    if (!isJobSourceValid) {
      setWorkflowStep("job");
      return;
    }
    if (!isJobEvidenceReady) {
      setWorkflowStep(jobPreview ? "jobReview" : "job");
      return;
    }
    if (!resume) {
      setWorkflowStep("resume");
      return;
    }
    setWorkflowStep("ai");
  }

  function handleViewReportFromSummary() {
    if (analysis) {
      setWorkflowStep("report");
    }
  }

  function handleViewDraftFromSummary() {
    if (analysis && activeApplicationId !== null) {
      setWorkflowStep("draft");
    }
  }

  async function handleSelectApplication(application: ApplicationItem) {
    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    setActiveApplicationId(application.id);
    try {
      const detail = await fetchApplicationDetail(application.id);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }

      setJobSourceType(detail.source_type);
      setJobUrl(detail.job_url ?? "");
      setJobText(detail.source_type === "pasted_text" ? detail.reviewed_job_text : "");
      setJobPreview(jobPreviewFromApplication(detail));
      setReviewedJobProfile(detail.reviewed_job_profile);

      if (detail.resume_id) {
        const profile = await fetchResumeProfile(detail.resume_id);
        if (!isCurrentWorkspaceRequest(requestRevision)) {
          return;
        }
        setResume({
          candidate_name: profile.candidate.name,
          resume_id: profile.resume_id,
          status: "parsed",
          warnings: profile.warnings
        });
        setResumeProfile(profile);
      } else {
        setResume(null);
        setResumeProfile(null);
      }

      if (detail.report_id && detail.analysis_id && detail.resume_id) {
        setAnalysis({
          analysis_id: detail.analysis_id,
          match_score: detail.match_score ?? 0,
          report_id: detail.report_id,
          status: "completed"
        });
        setReport(null);
        setWorkflowTrace(null);
        setWorkflowStep("draft");
        await loadReport(detail.report_id, requestRevision);
      } else {
        clearCurrentAnalysis();
        setWorkflowStep(detail.resume_id ? "ai" : "resume");
      }
    } catch (error) {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(error instanceof Error ? error.message : "Application load failed");
      }
    }
  }

  async function handleUpdateApplicationStatus(
    application: ApplicationItem,
    status: ApplicationStatus
  ) {
    setErrorMessage(null);
    try {
      const response = await fetch(`/api/applications/${application.id}/status`, {
        method: "PATCH",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({ status })
      });
      if (!response.ok) {
        throw new Error(await readApiError(response));
      }
      const updatedApplication = (await response.json()) as ApplicationItem;
      setApplications((currentApplications) =>
        currentApplications.map((item) =>
          item.id === updatedApplication.id ? updatedApplication : item
        )
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Application status update failed");
    }
  }

  async function handleRefreshTailoredResumeDraft() {
    if (!activeApplicationId) {
      return;
    }
    const applicationId = activeApplicationId;
    const requestRevision = workspaceRevisionRef.current;
    setErrorMessage(null);
    setIsLoadingTailoredResume(true);
    try {
      const draft = await fetchTailoredResumeDraft(applicationId);
      if (
        isCurrentWorkspaceRequest(requestRevision) &&
        draft.application_id === applicationId &&
        draft.report_id === report?.analysis_id
      ) {
        setTailoredResumeDraft(draft);
      }
    } catch (error) {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(
          error instanceof Error ? error.message : "Tailored resume workspace refresh failed"
        );
      }
    } finally {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setIsLoadingTailoredResume(false);
      }
    }
  }

  async function handleUpdateTailoredResumeItem(
    itemId: string,
    update: TailoredResumeItemUpdate
  ): Promise<ApiProblem | null> {
    if (!activeApplicationId) {
      return {
        fieldErrors: [],
        message: "Select an application before reviewing tailored bullets.",
        status: 400,
        warnings: []
      };
    }
    const applicationId = activeApplicationId;
    const requestRevision = workspaceRevisionRef.current;
    setErrorMessage(null);
    setIsUpdatingTailoredResume(true);
    try {
      const response = await fetch(
        `/api/applications/${encodeURIComponent(
          String(applicationId)
        )}/tailored-resume/items/${encodeURIComponent(itemId)}`,
        {
          method: "PATCH",
          headers: {
            "content-type": "application/json"
          },
          body: JSON.stringify(update)
        }
      );
      if (!response.ok) {
        return await readApiProblem(response);
      }
      const draft = (await response.json()) as TailoredResumeDraft;
      if (
        isCurrentWorkspaceRequest(requestRevision) &&
        draft.application_id === applicationId &&
        draft.report_id === report?.analysis_id
      ) {
        setTailoredResumeDraft(draft);
      }
      return null;
    } catch (error) {
      return {
        fieldErrors: [],
        message: error instanceof Error ? error.message : "Tailored resume update failed",
        status: 0,
        warnings: []
      };
    } finally {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setIsUpdatingTailoredResume(false);
      }
    }
  }

  async function handleReportExport(format: ReportExportFormat): Promise<void> {
    if (!analysis) {
      return;
    }
    const requestRevision = workspaceRevisionRef.current;
    const reportId = analysis.report_id;
    setErrorMessage(null);
    setIsExportingReport(format);
    try {
      await downloadExport({
        fallbackFilename: reportExportFilename(reportId, format),
        path: reportExportPath(reportId, format)
      });
      const [nextApplications, nextUsage] = await Promise.all([
        fetchApplications(),
        fetchUsageSummary()
      ]);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setApplications(nextApplications);
      setUsage(nextUsage);
    } catch (error) {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(error instanceof Error ? error.message : "Report export failed");
      }
    } finally {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setIsExportingReport(null);
      }
    }
  }

  async function handleTailoredResumeExport(
    format: TailoredResumeExportFormat
  ): Promise<void> {
    if (!activeApplicationId || !tailoredResumeDraft) {
      return;
    }
    const applicationId = activeApplicationId;
    const requestRevision = workspaceRevisionRef.current;
    setErrorMessage(null);
    setIsExportingTailoredResume(format);
    try {
      const exportPath = `/api/applications/${encodeURIComponent(
        String(applicationId)
      )}/tailored-resume/${format}`;
      if (format === "pdf") {
        const fingerprint = `${applicationId}:${tailoredResumeDraft.report_id}:${tailoredResumeDraft.updated_at}`;
        if (pdfExportCommandRef.current?.fingerprint !== fingerprint) {
          pdfExportCommandRef.current = { fingerprint, key: crypto.randomUUID() };
        }
        await downloadPdfExport({
          fallbackFilename: tailoredResumeExportFilename(applicationId, format),
          idempotencyKey: pdfExportCommandRef.current.key,
          path: exportPath
        });
        pdfExportCommandRef.current = null;
      } else {
        await downloadExport({
          fallbackFilename: tailoredResumeExportFilename(applicationId, format),
          path: exportPath
        });
      }
      const [draft, nextApplications, nextUsage] = await Promise.all([
        fetchTailoredResumeDraft(applicationId),
        fetchApplications(),
        fetchUsageSummary()
      ]);
      if (
        !isCurrentWorkspaceRequest(requestRevision) ||
        draft.application_id !== applicationId ||
        draft.report_id !== tailoredResumeDraft.report_id
      ) {
        return;
      }
      setTailoredResumeDraft(draft);
      setApplications(nextApplications);
      setUsage(nextUsage);
    } catch (error) {
      if (error instanceof TerminalOperationError) {
        pdfExportCommandRef.current = null;
      }
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(error instanceof Error ? error.message : "Tailored resume export failed");
      }
    } finally {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setIsExportingTailoredResume(null);
      }
    }
  }

  return (
    <main className="min-h-dvh px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <header className="rounded-lg border border-border bg-surface-raised p-4 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="primary">ResumePilot</Badge>
                <Badge tone="success">evidence-first</Badge>
                <Badge tone="neutral">local MVP</Badge>
              </div>
              <h1 className="mt-3 text-2xl font-semibold text-foreground sm:text-3xl">
                Guided application workflow
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Add a job URL or paste the description, review the extracted job evidence, upload the resume,
                then run ResumePilot&apos;s evidence-first AI services and approve the tailored
                resume draft before exporting.
              </p>
            </div>
            <Button
              icon={<RefreshCcw className="h-4 w-4" aria-hidden="true" />}
              onClick={() => void loadStatus()}
              variant="secondary"
            >
              Refresh status
            </Button>
          </div>
        </header>

        <WorkflowProgress steps={workflowSteps} />

        {errorMessage && (
          <div
            aria-live="assertive"
            className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
            role="alert"
          >
            {errorMessage}
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-label="Active workflow step" className="space-y-4">
            {workflowStep === "job" ? (
              <JobListingCard
                isJobInputValid={isJobSourceValid}
                isPreviewing={isPreviewingJob}
                jobSourceType={jobSourceType}
                jobText={jobText}
                jobUrl={jobUrl}
                onJobSourceTypeChange={handleJobSourceTypeChange}
                onJobTextChange={handleJobTextChange}
                onJobUrlChange={handleJobUrlChange}
                onSubmit={handleJobContinue}
              />
            ) : null}

            {workflowStep === "jobReview" && jobPreview ? (
              <JobEvidenceReviewCard
                key={`${jobPreview.job_url}:${jobPreview.raw_text_char_count}`}
                preview={jobPreview}
                onBack={() => {
                  setErrorMessage(null);
                  setWorkflowStep("job");
                }}
                onContinue={handleConfirmJobEvidence}
                onUsePastedText={() => handleJobSourceTypeChange("pasted_text")}
              />
            ) : null}

            {workflowStep === "resume" ? (
              <ResumeUploadCard
                fileName={file?.name ?? ""}
                isUploading={isUploading}
                onFileChange={handleFileChange}
                onSubmit={handleUpload}
                resume={resume}
              />
            ) : null}

            {workflowStep === "ai" ? (
              <AiWorkflowCard
                allowLiveAiProcessing={allowLiveAiProcessing}
                canAnalyze={canAnalyze}
                isAnalyzing={isAnalyzing}
                isSubmittingApproval={isSubmittingApproval}
                operation={activeOperation}
                onAllowLiveAiProcessingChange={setAllowLiveAiProcessing}
                onApprovalDecision={(decision) =>
                  void handleWorkflowApprovalDecision(decision)
                }
                onCancel={() => void handleCancelAnalysis()}
                onResume={() => void handleResumeAnalysisStatus()}
                onSubmit={handleAnalyze}
                usage={usage}
              />
            ) : null}

            {workflowStep === "report" ? (
              <ReportViewer
                analysis={analysis}
                canOpenTailoredResume={activeApplicationId !== null}
                isExporting={isExportingReport}
                onExport={handleReportExport}
                onOpenTailoredResume={handleViewDraftFromSummary}
                report={report}
                resumeProfile={resumeProfile}
                workflowTrace={workflowTrace}
              />
            ) : null}

            {workflowStep === "draft" ? (
              <TailoredResumeWorkspaceCard
                applicationId={activeApplicationId}
                draft={tailoredResumeDraft}
                isExporting={isExportingTailoredResume}
                isLoading={isLoadingTailoredResume}
                isUpdating={isUpdatingTailoredResume}
                onExport={handleTailoredResumeExport}
                onRefresh={() => void handleRefreshTailoredResumeDraft()}
                onUpdateItem={handleUpdateTailoredResumeItem}
                onViewReport={handleViewReportFromSummary}
              />
            ) : null}
          </section>

          <div className="space-y-4">
            <ApplicationPipelineCard
              activeApplicationId={activeApplicationId}
              applications={applications}
              isBusy={
                isAnalyzing ||
                isSubmittingApproval ||
                hasActiveAnalysisOperation ||
                isExportingReport !== null ||
                isExportingTailoredResume !== null ||
                isLoadingTailoredResume ||
                isUpdatingTailoredResume ||
                isUploading
              }
              isLoading={isLoadingApplications}
              onSelectApplication={(application) => void handleSelectApplication(application)}
              onUpdateStatus={(application, status) =>
                void handleUpdateApplicationStatus(application, status)
              }
            />
            <WorkflowSummaryCard
              activeOperation={activeOperation}
              analysis={analysis}
              isJobEvidenceReady={isJobEvidenceReady}
              isJobReady={isJobSourceValid}
              isResumeReady={isResumeReady}
              jobPreview={jobPreview}
              jobSourceType={jobSourceType}
              jobText={jobText}
              jobUrl={jobUrl}
              onEditJob={() => {
                setErrorMessage(null);
                setWorkflowStep("job");
              }}
              onReviewJob={handleOpenJobEvidenceReview}
              onEditResume={handleEditResume}
              onRunAi={handleRunAiFromSummary}
              onViewDraft={handleViewDraftFromSummary}
              onViewReport={handleViewReportFromSummary}
              resume={resume}
              tailoredResumeDraft={tailoredResumeDraft}
              workflowTrace={workflowTrace}
            />
          </div>
        </div>

        <details className="group rounded-lg border border-border bg-surface-raised shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4 text-sm font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35">
            <span>Workspace review and system status</span>
            <ChevronDown
              className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>
          <div className="grid gap-4 border-t border-border p-4 xl:grid-cols-2">
            <Panel as="aside" eyebrow="Runtime" title="FastAPI status">
              <HealthStrip health={health} isLoading={isLoadingStatus} />
            </Panel>
            <ReportHistoryCard
              isBusy={
                isAnalyzing ||
                isSubmittingApproval ||
                hasActiveAnalysisOperation ||
                isExportingReport !== null ||
                isExportingTailoredResume !== null ||
                isLoadingTailoredResume ||
                isUpdatingTailoredResume ||
                isUploading
              }
              isLoading={isLoadingHistory}
              items={reportHistory}
              onSelectReport={(item) => void handleSelectReport(item)}
              selectedReportId={analysis?.report_id ?? null}
            />
            <ResumeProfileReviewCard profile={resumeProfile} />
            <AccountSessionCard session={authSession} />
            <OpenClawStatusCard status={openclaw} />
            <UsageStatusCard usage={usage} />
            <Panel as="aside" eyebrow="Boundary" title="Validation gate">
              <ul className="space-y-3 text-sm leading-6 text-muted-foreground">
                <li>Unsupported work history is rejected before the report is shown.</li>
                <li>Resume bullets retain evidence IDs for review.</li>
                <li>OpenClaw commands call the same FastAPI report path.</li>
              </ul>
            </Panel>
          </div>
        </details>
      </div>
    </main>
  );
}

interface BuildWorkflowStepsInput {
  analysisReady: boolean;
  currentStep: WorkflowStepId;
  draftReady: boolean;
  jobEvidenceReady: boolean;
  jobReady: boolean;
  resumeReady: boolean;
}

class TerminalOperationError extends Error {}

class OperationFetchError extends Error {
  constructor(message: string, readonly retryable: boolean) {
    super(message);
    this.name = "OperationFetchError";
  }
}

interface AnalysisOperationOutcome {
  analysis: JobAnalysisResponse;
  status: "succeeded" | "waiting_for_approval";
}

async function waitForAnalysisOperation(
  initial: WorkflowOperation,
  requestRevision: number,
  isCurrent: (revision: number) => boolean,
  onUpdate: (operation: WorkflowOperation) => void
): Promise<AnalysisOperationOutcome | null> {
  let operation = initial;
  let consecutivePollFailures = 0;
  for (let pollCount = 0; pollCount < 73; pollCount += 1) {
    if (!isCurrent(requestRevision)) {
      return null;
    }
    onUpdate(operation);
    if (operation.status === "waiting_for_approval") {
      if (!operation.approval) {
        throw new TerminalOperationError(
          "Analysis paused without a valid live draft approval request."
        );
      }
      if (operation.approval.status === "pending") {
        if (!isJobAnalysisResponse(operation.result)) {
          throw new TerminalOperationError(
            "Analysis paused without a deterministic baseline report."
          );
        }
        return {
          analysis: operation.result,
          status: "waiting_for_approval"
        };
      }
    }
    if (operation.status === "succeeded") {
      if (!isJobAnalysisResponse(operation.result)) {
        throw new TerminalOperationError("Analysis completed without a report result.");
      }
      return {
        analysis: operation.result,
        status: "succeeded"
      };
    }
    if (["canceled", "failed", "dead_lettered"].includes(operation.status)) {
      throw new TerminalOperationError(
        operation.error?.message ??
          (operation.status === "canceled"
            ? "Analysis was canceled."
            : "Analysis failed safely. Review the job source and retry.")
      );
    }

    await wait(operationPollDelay(pollCount));
    if (!isCurrent(requestRevision)) {
      return null;
    }
    try {
      operation = await fetchWorkflowOperation(operation.id);
      consecutivePollFailures = 0;
    } catch (error) {
      if (
        error instanceof OperationFetchError &&
        error.retryable &&
        consecutivePollFailures < 3
      ) {
        consecutivePollFailures += 1;
        continue;
      }
      throw error;
    }
  }
  throw new Error(
    "Analysis is still running after five minutes. It remains durable; use Resume status to continue polling."
  );
}

async function fetchWorkflowOperation(operationId: string): Promise<WorkflowOperation> {
  let response: Response;
  try {
    response = await fetch(`/api/operations/${encodeURIComponent(operationId)}`, {
      cache: "no-store"
    });
  } catch {
    throw new OperationFetchError(
      "The analysis status could not be reached. Check the connection and use Resume status.",
      true
    );
  }
  if (!response.ok) {
    const retryable =
      [408, 425, 429].includes(response.status) || response.status >= 500;
    throw new OperationFetchError(await readApiError(response), retryable);
  }
  return requireWorkflowOperation((await response.json()) as unknown);
}

function isActiveAnalysisOperation(operation: WorkflowOperation): boolean {
  return (
    operation.kind === "analysis" &&
    !["succeeded", "canceled", "failed", "dead_lettered"].includes(operation.status)
  );
}

function operationPollDelay(pollCount: number): number {
  if (pollCount < 5) {
    return 1_000;
  }
  if (pollCount < 20) {
    return 2_000;
  }
  return 5_000;
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function isJobAnalysisResponse(value: unknown): value is JobAnalysisResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Partial<JobAnalysisResponse>;
  return (
    typeof candidate.analysis_id === "number" &&
    typeof candidate.report_id === "number" &&
    typeof candidate.match_score === "number" &&
    typeof candidate.status === "string"
  );
}

function requireWorkflowOperation(value: unknown): WorkflowOperation {
  if (typeof value !== "object" || value === null) {
    throw new Error("Backend returned an invalid analysis operation.");
  }
  const candidate = value as Partial<WorkflowOperation>;
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.status !== "string" ||
    typeof candidate.stage !== "string" ||
    typeof candidate.progress_percent !== "number"
  ) {
    throw new Error("Backend returned an invalid analysis operation.");
  }
  if (
    candidate.status === "waiting_for_approval" &&
    !isWorkflowApproval(candidate.approval)
  ) {
    throw new Error("Backend returned an invalid live draft approval request.");
  }
  return candidate as WorkflowOperation;
}

function isWorkflowApproval(
  value: unknown
): value is NonNullable<WorkflowOperation["approval"]> {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Partial<NonNullable<WorkflowOperation["approval"]>>;
  const proposal = candidate.proposal;
  return (
    typeof candidate.id === "string" &&
    candidate.kind === "live_ai_draft" &&
    ["pending", "submitted", "approved", "rejected"].includes(candidate.status ?? "") &&
    typeof candidate.title === "string" &&
    typeof candidate.message === "string" &&
    Array.isArray(candidate.warning_codes) &&
    typeof candidate.requested_at === "string" &&
    typeof proposal === "object" &&
    proposal !== null &&
    typeof proposal.executive_summary === "string" &&
    typeof proposal.cover_letter === "string" &&
    Array.isArray(proposal.interview_questions) &&
    proposal.interview_questions.every(
      (group) =>
        typeof group?.category === "string" &&
        Array.isArray(group.questions) &&
        group.questions.every((question) => typeof question === "string") &&
        Array.isArray(group.suggested_answer_evidence_ids)
    )
  );
}

async function downloadPdfExport({
  fallbackFilename,
  idempotencyKey,
  path
}: {
  fallbackFilename: string;
  idempotencyKey: string;
  path: string;
}): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "idempotency-key": idempotencyKey }
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  let operation = requireWorkflowOperation((await response.json()) as unknown);
  for (let pollCount = 0; pollCount < 90; pollCount += 1) {
    if (operation.status === "succeeded") {
      if (!isPdfExportResult(operation.result)) {
        throw new TerminalOperationError("PDF export completed without an artifact.");
      }
      await downloadExport({
        fallbackFilename,
        method: "GET",
        path: `/api/operations/${encodeURIComponent(operation.id)}/artifact`
      });
      return;
    }
    if (["canceled", "failed", "dead_lettered"].includes(operation.status)) {
      throw new TerminalOperationError(
        operation.error?.message ?? "PDF export failed safely. Review the draft and retry."
      );
    }
    await wait(operationPollDelay(pollCount));
    const pollResponse = await fetch(
      `/api/operations/${encodeURIComponent(operation.id)}`,
      { cache: "no-store" }
    );
    if (!pollResponse.ok) {
      throw new Error(await readApiError(pollResponse));
    }
    operation = requireWorkflowOperation((await pollResponse.json()) as unknown);
  }
  throw new Error("PDF export is still running. Retry the download shortly.");
}

function isPdfExportResult(value: unknown): value is PdfExportResult {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Partial<PdfExportResult>;
  return (
    typeof candidate.application_id === "number" &&
    typeof candidate.report_id === "number" &&
    typeof candidate.artifact?.download_url === "string" &&
    typeof candidate.artifact?.sha256 === "string"
  );
}

async function downloadExport({
  fallbackFilename,
  method = "POST",
  path
}: {
  fallbackFilename: string;
  method?: "GET" | "POST";
  path: string;
}): Promise<void> {
  const response = await fetch(path, {
    cache: "no-store",
    method
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.download = filenameFromContentDisposition(
    response.headers.get("content-disposition"),
    fallbackFilename
  );
  anchor.href = objectUrl;
  anchor.style.display = "none";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

function reportExportPath(reportId: number, format: ReportExportFormat): string {
  const encodedReportId = encodeURIComponent(String(reportId));
  return `/api/reports/${encodedReportId}/${format}`;
}

function reportExportFilename(reportId: number, format: ReportExportFormat): string {
  return `resumepilot-report-${reportId}.${exportFileExtension(format)}`;
}

function tailoredResumeExportFilename(
  applicationId: number,
  format: TailoredResumeExportFormat
): string {
  return `resumepilot-application-${applicationId}.${exportFileExtension(format)}`;
}

function exportFileExtension(format: DownloadExportFormat): string {
  const extensions: Record<DownloadExportFormat, string> = {
    docx: "docx",
    latex: "tex",
    markdown: "md",
    pdf: "pdf"
  };
  return extensions[format];
}

function filenameFromContentDisposition(
  contentDisposition: string | null,
  fallbackFilename: string
): string {
  const match = contentDisposition?.match(/filename="?([^";]+)"?/i);
  return match?.[1] ? decodeURIComponent(match[1]) : fallbackFilename;
}

function buildWorkflowSteps({
  analysisReady,
  currentStep,
  draftReady,
  jobEvidenceReady,
  jobReady,
  resumeReady
}: BuildWorkflowStepsInput): WorkflowProgressStep[] {
  return [
    {
      detail: jobReady ? "Job source captured" : "Add a URL or paste the job description",
      id: "job",
      label: "Job listing",
      status: currentStep === "job" ? "active" : jobReady ? "complete" : "ready"
    },
    {
      detail: jobEvidenceReady ? "Structured job evidence reviewed" : "Review extracted role requirements",
      id: "jobReview",
      label: "Job evidence",
      status:
        currentStep === "jobReview"
          ? "active"
          : jobEvidenceReady
            ? "complete"
            : jobReady
              ? "ready"
              : "locked"
    },
    {
      detail: resumeReady ? "Resume parsed into evidence" : "Upload PDF, DOCX, TXT, or Markdown",
      id: "resume",
      label: "Resume upload",
      status:
        currentStep === "resume"
          ? "active"
          : resumeReady
            ? "complete"
            : jobEvidenceReady
              ? "ready"
              : "locked"
    },
    {
      detail: analysisReady ? "Analysis completed" : "Run matching, generation, and validation",
      id: "ai",
      label: "AI services",
      status:
        currentStep === "ai"
          ? "active"
          : analysisReady
            ? "complete"
            : jobEvidenceReady && resumeReady
              ? "ready"
              : "locked"
    },
    {
      detail: analysisReady ? "Validated report ready" : "Review score, evidence, exports",
      id: "report",
      label: "Report",
      status: currentStep === "report" ? "active" : analysisReady ? "complete" : "locked"
    },
    {
      detail: draftReady ? "Accepted bullets ready for export" : "Approve evidence-backed bullets",
      id: "draft",
      label: "Draft",
      status:
        currentStep === "draft"
          ? "active"
          : draftReady
            ? "complete"
            : analysisReady
              ? "ready"
              : "locked"
    }
  ];
}

function isHttpUrl(value: string): boolean {
  try {
    const parsedUrl = new URL(value);
    return parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:";
  } catch {
    return false;
  }
}

function isJobInputValid(sourceType: JobSourceType, jobUrl: string, jobText: string): boolean {
  if (sourceType === "url") {
    return isHttpUrl(jobUrl);
  }
  return jobText.length >= MIN_JOB_TEXT_CHARS && jobText.length <= MAX_JOB_TEXT_CHARS;
}

function isJobPreviewCurrent(
  preview: JobPreviewResponse | null,
  sourceType: JobSourceType,
  jobUrl: string,
  jobText: string
): boolean {
  if (!preview || preview.source_type !== sourceType) {
    return false;
  }
  if (sourceType === "url") {
    return Boolean(preview.job_url) && canonicalHttpUrl(preview.job_url ?? "") === canonicalHttpUrl(jobUrl);
  }
  return isJobInputValid(sourceType, jobUrl, jobText);
}

function canonicalHttpUrl(value: string): string {
  try {
    const parsedUrl = new URL(value);
    return parsedUrl.toString();
  } catch {
    return value;
  }
}

function jobPreviewFromApplication(application: ApplicationDetail): JobPreviewResponse {
  const hasSkills =
    application.reviewed_job_profile.required_skills.length > 0 ||
    application.reviewed_job_profile.preferred_skills.length > 0;
  return {
    job_url: application.job_url,
    parser: "saved_review",
    profile: application.reviewed_job_profile,
    quality_checks: [],
    raw_text_char_count: application.reviewed_job_text.length,
    reviewed_job_text: application.reviewed_job_text,
    source_content_hash: application.source_content_hash,
    source_type: application.source_type,
    status: hasSkills ? "ready" : "needs_review"
  };
}

function jobProfilesEqual(left: JobProfile, right: JobProfile): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}
