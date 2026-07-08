import { AlertTriangle, CheckCircle2, ClipboardList, Download, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { Panel } from "@/components/ui/panel";
import type { ApplicationReport, JobAnalysisResponse } from "@/features/dashboard/types";
import { formatScore, scoreLabel, scoreTone } from "@/features/dashboard/utils/report";

interface ReportViewerProps {
  analysis: JobAnalysisResponse | null;
  markdown: string;
  report: ApplicationReport | null;
}

export function ReportViewer({ analysis, markdown, report }: ReportViewerProps) {
  if (!report || !analysis) {
    return (
      <Panel eyebrow="Step 03" title="Report">
        <div className="flex min-h-80 items-center justify-center rounded-md border border-dashed border-border bg-surface p-6 text-center">
          <div>
            <ClipboardList className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-foreground">No analysis yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload a resume and analyze a job to generate a report.
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  const matchTone = scoreTone(report.match_score);

  return (
    <Panel
      action={
        <ButtonLink
          download={`resumepilot-report-${analysis.report_id}.md`}
          href={`data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`}
          icon={<Download className="h-4 w-4" aria-hidden="true" />}
          variant="secondary"
        >
          Markdown
        </ButtonLink>
      }
      eyebrow={`Report ${analysis.report_id}`}
      title="Evidence-backed fit"
    >
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-[12rem_1fr]">
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
              Match score
            </p>
            <p className="mt-2 font-mono text-5xl font-semibold tabular-nums">
              {formatScore(report.match_score)}
            </p>
            <Badge className="mt-3" tone={matchTone}>
              {scoreLabel(report.match_score)}
            </Badge>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-sm font-semibold">Executive summary</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{report.executive_summary}</p>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <Metric label="Matched" value={report.matched_skills.length} />
          <Metric label="Missing" value={report.missing_skills.length} />
          <Metric label="Warnings" value={report.validation_warnings.length} />
        </div>

        <section className="grid gap-4 lg:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-validation" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Matched skills</h3>
            </div>
            <div className="space-y-2">
              {report.matched_skills.slice(0, 8).map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.skill}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.skill}</p>
                    <Badge tone="success">{item.match_type}</Badge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                    {item.job_evidence_text}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Missing or weak</h3>
            </div>
            <div className="space-y-2">
              {report.missing_skills.slice(0, 5).map((item) => (
                <div className="rounded-md border border-border bg-surface p-3" key={item.skill}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">{item.skill}</p>
                    <Badge tone={item.importance === "required" ? "danger" : "warning"}>
                      {item.importance}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.recommendation}</p>
                </div>
              ))}
              {report.missing_skills.length === 0 && (
                <div className="rounded-md border border-border bg-surface p-3 text-sm text-muted-foreground">
                  No missing skills found by the deterministic matcher.
                </div>
              )}
            </div>
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Tailored bullets</h3>
          </div>
          <div className="space-y-2">
            {report.tailored_bullets.map((item) => (
              <div className="rounded-md border border-border bg-surface p-3" key={item.bullet}>
                <p className="text-sm leading-6">{item.bullet}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.evidence_ids.map((evidenceId) => (
                    <Badge key={evidenceId} tone="primary">
                      {evidenceId}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </Panel>
  );
}

interface MetricProps {
  label: string;
  value: number;
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
