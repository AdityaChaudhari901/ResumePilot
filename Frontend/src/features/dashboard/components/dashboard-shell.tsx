"use client";

import { RefreshCcw } from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { AccountSessionCard } from "@/features/dashboard/components/account-session-card";
import { HealthStrip } from "@/features/dashboard/components/health-strip";
import { JobAnalysisCard } from "@/features/dashboard/components/job-analysis-card";
import { OpenClawStatusCard } from "@/features/dashboard/components/openclaw-status-card";
import { ReportHistoryCard } from "@/features/dashboard/components/report-history-card";
import { ReportViewer } from "@/features/dashboard/components/report-viewer";
import { ResumeProfileReviewCard } from "@/features/dashboard/components/resume-profile-review-card";
import { ResumeUploadCard } from "@/features/dashboard/components/resume-upload-card";
import { UsageStatusCard } from "@/features/dashboard/components/usage-status-card";
import { SAMPLE_JOB_TEXT } from "@/features/dashboard/constants";
import type {
  AgentWorkflowTrace,
  ApplicationReport,
  DashboardAuthSession,
  HealthStatus,
  JobAnalysisResponse,
  OpenClawStatus,
  ReportHistoryItem,
  ReportHistoryResponse,
  ReportWorkflowTraceResponse,
  ResumeProfile,
  ResumeUploadResponse,
  UsageSummaryResponse
} from "@/features/dashboard/types";
import { readApiError } from "@/features/dashboard/utils/api-error";

interface DashboardStatusPayload {
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
    reports: await fetchReportHistory(),
    usage: await fetchUsageSummary()
  };
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

interface DashboardShellProps {
  initialAuthSession: DashboardAuthSession;
}

export function DashboardShell({ initialAuthSession }: DashboardShellProps) {
  const [analysis, setAnalysis] = useState<JobAnalysisResponse | null>(null);
  const [authSession, setAuthSession] = useState<DashboardAuthSession | null>(
    initialAuthSession
  );
  const [company, setCompany] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [jobText, setJobText] = useState("");
  const [openclaw, setOpenclaw] = useState<OpenClawStatus | null>(null);
  const [report, setReport] = useState<ApplicationReport | null>(null);
  const [reportHistory, setReportHistory] = useState<ReportHistoryItem[]>([]);
  const [resume, setResume] = useState<ResumeUploadResponse | null>(null);
  const [resumeProfile, setResumeProfile] = useState<ResumeProfile | null>(null);
  const [role, setRole] = useState("");
  const [usage, setUsage] = useState<UsageSummaryResponse | null>(null);
  const [workflowTrace, setWorkflowTrace] = useState<AgentWorkflowTrace | null>(null);

  const loadStatus = useCallback(async () => {
    setIsLoadingStatus(true);
    const status = await fetchDashboardStatus();
    setAuthSession(status.auth);
    setHealth(status.health);
    setOpenclaw(status.openclaw);
    setReportHistory(status.reports);
    setUsage(status.usage);
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
      setOpenclaw(status.openclaw);
      setReportHistory(status.reports);
      setUsage(status.usage);
      setIsLoadingHistory(false);
      setIsLoadingStatus(false);
    }

    void loadInitialStatus();

    return () => {
      isMounted = false;
    };
  }, []);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setErrorMessage(null);
    setFile(event.target.files?.[0] ?? null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }

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
      setResume(nextResume);
      setResumeProfile(await fetchResumeProfile(nextResume.resume_id));
      setAnalysis(null);
      setReport(null);
      setWorkflowTrace(null);
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
      return;
    }

    setErrorMessage(null);
    setIsAnalyzing(true);
    setAnalysis(null);
    setReport(null);
    setWorkflowTrace(null);

    try {
      const response = await fetch("/api/jobs/analyze", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify({
          resume_id: resume.resume_id,
          job_text: jobText,
          company: company || null,
          role: role || null
        })
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const nextAnalysis = (await response.json()) as JobAnalysisResponse;
      setAnalysis(nextAnalysis);
      await loadReport(nextAnalysis.report_id);
      setReportHistory(await fetchReportHistory());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Job analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function loadReport(reportId: number) {
    const [reportResponse, traceResponse, usageSummary] = await Promise.all([
      fetch(`/api/reports/${reportId}`, { cache: "no-store" }),
      fetch(`/api/reports/${reportId}/trace`, { cache: "no-store" }),
      fetchUsageSummary()
    ]);

    if (!reportResponse.ok) {
      throw new Error(await readApiError(reportResponse));
    }

    setReport((await reportResponse.json()) as ApplicationReport);
    setUsage(usageSummary);

    if (traceResponse.ok) {
      const tracePayload = (await traceResponse.json()) as ReportWorkflowTraceResponse;
      setWorkflowTrace(tracePayload.trace);
    } else {
      setWorkflowTrace(null);
    }
  }

  async function handleSelectReport(item: ReportHistoryItem) {
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
      const [profile] = await Promise.all([
        fetchResumeProfile(item.resume_id),
        loadReport(item.report_id)
      ]);
      setResumeProfile(profile);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Report history load failed");
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
                Application review console
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Upload a resume, compare it with a job description, and inspect the validated
                report before moving the same flow into OpenClaw WebChat.
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
          <div className="mt-4">
            <HealthStrip health={health} isLoading={isLoadingStatus} />
          </div>
        </header>

        {errorMessage && (
          <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
            {errorMessage}
          </div>
        )}

        <div className="grid gap-4 xl:grid-cols-[24rem_1fr]">
          <div className="space-y-4">
            <ResumeUploadCard
              fileName={file?.name ?? ""}
              isUploading={isUploading}
              onFileChange={handleFileChange}
              onSubmit={handleUpload}
              resume={resume}
            />
            <ReportHistoryCard
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

          <div className="grid gap-4 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <JobAnalysisCard
              company={company}
              isAnalyzing={isAnalyzing}
              jobText={jobText}
              onCompanyChange={setCompany}
              onJobTextChange={setJobText}
              onRoleChange={setRole}
              onSampleJob={() => {
                setJobText(SAMPLE_JOB_TEXT);
                setCompany("NovaHire AI");
                setRole("Backend Engineer");
              }}
              onSubmit={handleAnalyze}
              resumeReady={Boolean(resume)}
              role={role}
            />
            <ReportViewer
              analysis={analysis}
              report={report}
              workflowTrace={workflowTrace}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
