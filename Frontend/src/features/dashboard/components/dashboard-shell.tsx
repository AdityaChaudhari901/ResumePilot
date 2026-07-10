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
import { JobListingCard } from "@/features/dashboard/components/job-listing-card";
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
  ApplicationItem,
  ApplicationListResponse,
  ApplicationReport,
  ApplicationStatus,
  DashboardAuthSession,
  HealthStatus,
  JobAnalysisResponse,
  JobPreviewResponse,
  JobProfile,
  OpenClawStatus,
  ReportHistoryItem,
  ReportHistoryResponse,
  ReportExportFormat,
  ReportWorkflowTraceResponse,
  ResumeProfile,
  ResumeUploadResponse,
  TailoredResumeDraft,
  TailoredResumeExportFormat,
  TailoredResumeItemUpdate,
  UsageSummaryResponse
} from "@/features/dashboard/types";
import { readApiError } from "@/features/dashboard/utils/api-error";

interface DashboardStatusPayload {
  applications: ApplicationItem[];
  auth: DashboardAuthSession | null;
  health: HealthStatus;
  openclaw: OpenClawStatus;
  reports: ReportHistoryItem[];
  usage: UsageSummaryResponse | null;
}

async function fetchDashboardStatus(): Promise<DashboardStatusPayload> {
  const [authResponse, healthResponse, openclawResponse] = await Promise.all([
    fetch("/api/auth/session", { cache: "no-store" }),
    fetch("/api/health", { cache: "no-store" }),
    fetch("/api/openclaw/status", { cache: "no-store" })
  ]);

  return {
    auth: authResponse.ok ? ((await authResponse.json()) as DashboardAuthSession) : null,
    health: (await healthResponse.json()) as HealthStatus,
    openclaw: (await openclawResponse.json()) as OpenClawStatus,
    applications: await fetchApplications(),
    reports: await fetchReportHistory(),
    usage: await fetchUsageSummary()
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
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [authSession, setAuthSession] = useState<DashboardAuthSession | null>(
    initialAuthSession
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
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
    setReport(null);
    setTailoredResumeDraft(null);
    setWorkflowTrace(null);
  }

  function handleJobUrlChange(value: string) {
    startWorkspaceRequest();
    setJobUrl(value);
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

  async function handleJobContinue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestRevision = startWorkspaceRequest();
    const trimmedJobUrl = jobUrl.trim();

    if (!isHttpUrl(trimmedJobUrl)) {
      setErrorMessage("Enter a valid public http(s) job listing URL.");
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
        body: JSON.stringify({
          job_url: trimmedJobUrl
        })
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

      if (!isHttpUrl(trimmedJobUrl)) {
        setErrorMessage("Enter a valid public http(s) job listing URL.");
        setWorkflowStep("job");
        setIsAnalyzing(false);
        return;
      }
      if (!isJobPreviewCurrent(jobPreview, trimmedJobUrl)) {
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

      const response = await fetch("/api/jobs/analyze", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          resume_id: resume.resume_id,
          application_id: activeApplicationId,
          job_text: null,
          job_url: trimmedJobUrl,
          company: null,
          role: null,
          reviewed_job_profile: reviewedJobProfile,
          allow_live_ai_processing: allowLiveAiProcessing
        })
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const nextAnalysis = (await response.json()) as JobAnalysisResponse;
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setAnalysis(nextAnalysis);
      const didLoadReport = await loadReport(nextAnalysis.report_id, requestRevision);
      if (!didLoadReport || !isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      const [nextApplications, nextReportHistory] = await Promise.all([
        fetchApplications(),
        fetchReportHistory()
      ]);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setApplications(nextApplications);
      setReportHistory(nextReportHistory);
      setWorkflowStep("draft");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Job analysis failed");
    } finally {
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

  const isJobUrlValid = isHttpUrl(jobUrl.trim());
  const isJobEvidenceReady =
    isJobPreviewCurrent(jobPreview, jobUrl.trim()) && Boolean(reviewedJobProfile);
  const isResumeReady = Boolean(resume);
  const canAnalyze = isJobEvidenceReady && isResumeReady && !isAnalyzing;
  const workflowSteps = buildWorkflowSteps({
    analysisReady: Boolean(analysis && report),
    currentStep: workflowStep,
    draftReady: Boolean(tailoredResumeDraft?.export_ready),
    jobEvidenceReady: isJobEvidenceReady,
    jobReady: isJobUrlValid,
    resumeReady: isResumeReady
  });

  function handleEditResume() {
    setErrorMessage(null);
    setWorkflowStep(isJobEvidenceReady ? "resume" : jobPreview ? "jobReview" : "job");
  }

  async function handleConfirmJobEvidence(profile: JobProfile) {
    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    try {
      const response = await fetch("/api/applications", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          job_url: jobUrl.trim(),
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
    if (!isJobUrlValid) {
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
    if (analysis) {
      setWorkflowStep("draft");
    }
  }

  async function handleSelectApplication(application: ApplicationItem) {
    if (!application.report_id || !application.analysis_id || !application.resume_id) {
      return;
    }
    const requestRevision = startWorkspaceRequest();
    setErrorMessage(null);
    setActiveApplicationId(application.id);
    setAnalysis({
      analysis_id: application.analysis_id,
      match_score: application.match_score ?? 0,
      report_id: application.report_id,
      status: "completed"
    });
    setReport(null);
    setWorkflowTrace(null);
    setWorkflowStep("draft");
    try {
      const [profile] = await Promise.all([
        fetchResumeProfile(application.resume_id),
        loadReport(application.report_id, requestRevision)
      ]);
      if (!isCurrentWorkspaceRequest(requestRevision)) {
        return;
      }
      setResumeProfile(profile);
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
  ) {
    if (!activeApplicationId) {
      return;
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
        throw new Error(await readApiError(response));
      }
      const draft = (await response.json()) as TailoredResumeDraft;
      if (
        isCurrentWorkspaceRequest(requestRevision) &&
        draft.application_id === applicationId &&
        draft.report_id === report?.analysis_id
      ) {
        setTailoredResumeDraft(draft);
      }
    } catch (error) {
      if (isCurrentWorkspaceRequest(requestRevision)) {
        setErrorMessage(error instanceof Error ? error.message : "Tailored resume update failed");
      }
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
      await downloadExport({
        fallbackFilename: tailoredResumeExportFilename(applicationId, format),
        path: `/api/applications/${encodeURIComponent(
          String(applicationId)
        )}/tailored-resume/${format}`
      });
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
                Add a job listing URL, review the extracted job evidence, upload the resume,
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
          <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
            {errorMessage}
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-label="Active workflow step" className="space-y-4">
            {workflowStep === "job" ? (
              <JobListingCard
                isPreviewing={isPreviewingJob}
                isJobUrlValid={isJobUrlValid}
                jobUrl={jobUrl}
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
                onAllowLiveAiProcessingChange={setAllowLiveAiProcessing}
                onSubmit={handleAnalyze}
                usage={usage}
              />
            ) : null}

            {workflowStep === "report" ? (
              <ReportViewer
                analysis={analysis}
                isExporting={isExportingReport}
                onExport={handleReportExport}
                report={report}
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
              analysis={analysis}
              isJobEvidenceReady={isJobEvidenceReady}
              isJobReady={isJobUrlValid}
              isResumeReady={isResumeReady}
              jobPreview={jobPreview}
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

async function downloadExport({
  fallbackFilename,
  path
}: {
  fallbackFilename: string;
  path: string;
}): Promise<void> {
  const response = await fetch(path, {
    cache: "no-store",
    method: "POST"
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
  if (format === "markdown") {
    return `/api/reports/${encodedReportId}/markdown`;
  }
  return `/api/reports/${encodedReportId}/resume/${format}`;
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

function exportFileExtension(format: ReportExportFormat): string {
  const extensions: Record<ReportExportFormat, string> = {
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
      detail: jobReady ? "Job listing URL captured" : "Add the public job URL",
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

function isJobPreviewCurrent(
  preview: JobPreviewResponse | null,
  jobUrl: string
): boolean {
  if (!preview || !isHttpUrl(jobUrl)) {
    return false;
  }
  return canonicalHttpUrl(preview.job_url) === canonicalHttpUrl(jobUrl);
}

function canonicalHttpUrl(value: string): string {
  try {
    const parsedUrl = new URL(value);
    return parsedUrl.toString();
  } catch {
    return value;
  }
}
