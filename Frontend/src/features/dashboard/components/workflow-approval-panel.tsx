"use client";

import {
  AlertTriangle,
  FileText,
  MessageSquareText,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { useEffect, useId, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  WorkflowApproval,
  WorkflowApprovalDecision
} from "@/features/dashboard/types";

interface WorkflowApprovalPanelProps {
  approval: WorkflowApproval;
  isSubmitting: boolean;
  onDecision: (decision: WorkflowApprovalDecision) => void;
}

export function WorkflowApprovalPanel({
  approval,
  isSubmitting,
  onDecision
}: WorkflowApprovalPanelProps) {
  const titleId = useId();
  const descriptionId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const questionCount = approval.proposal.interview_questions.reduce(
    (total, group) => total + group.questions.length,
    0
  );

  useEffect(() => {
    headingRef.current?.focus();
  }, [approval.id]);

  return (
    <section
      aria-busy={isSubmitting}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="rounded-lg border border-warning/35 bg-warning/5 p-4 shadow-sm"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-warning/25 bg-warning/10 text-warning">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3
                className="text-base font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
                id={titleId}
                ref={headingRef}
                tabIndex={-1}
              >
                {approval.title}
              </h3>
              <Badge tone="warning">Your decision is required</Badge>
            </div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground" id={descriptionId}>
              {approval.message}
            </p>
          </div>
        </div>
      </div>

      {approval.warning_codes.length > 0 ? (
        <div className="mt-4 rounded-md border border-warning/25 bg-surface p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
            Validation notes
          </div>
          <ul className="mt-2 flex flex-wrap gap-2" aria-label="Live draft validation notes">
            {approval.warning_codes.map((code) => (
              <li key={code}>
                <Badge tone="warning">{formatWarningCode(code)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <ProposalSection
          icon={<FileText className="h-4 w-4 text-primary" aria-hidden="true" />}
          title="Executive summary"
        >
          <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
            {approval.proposal.executive_summary}
          </p>
        </ProposalSection>

        <ProposalSection
          icon={<FileText className="h-4 w-4 text-primary" aria-hidden="true" />}
          title="Cover letter"
        >
          <div
            aria-label="Live draft cover letter preview"
            className="pr-2 md:max-h-64 md:overflow-y-auto"
            tabIndex={0}
          >
            <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
              {approval.proposal.cover_letter}
            </p>
          </div>
        </ProposalSection>

        <div className="xl:col-span-2">
          <ProposalSection
            icon={<MessageSquareText className="h-4 w-4 text-primary" aria-hidden="true" />}
            title={`Interview preparation · ${questionCount} question${questionCount === 1 ? "" : "s"}`}
          >
            {approval.proposal.interview_questions.length > 0 ? (
              <div className="grid gap-3 lg:grid-cols-2">
                {approval.proposal.interview_questions.map((group, groupIndex) => (
                  <div
                    className="rounded-md border border-border bg-background p-3"
                    key={`${group.category}-${groupIndex}`}
                  >
                    <h5 className="text-sm font-semibold text-foreground">{group.category}</h5>
                    <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm leading-6 text-muted-foreground">
                      {group.questions.map((question, questionIndex) => (
                        <li key={`${question}-${questionIndex}`}>{question}</li>
                      ))}
                    </ol>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                The live draft does not propose additional interview questions.
              </p>
            )}
          </ProposalSection>
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3 rounded-md border border-primary/20 bg-primary/5 p-3">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-xs leading-5 text-muted-foreground">
          This decision applies only to the live AI summary, cover letter, and interview
          preparation. It does not accept tailored résumé bullets or unlock exports; review those
          separately in the Tailored résumé workspace.
        </p>
      </div>

      <div className="mt-4 flex flex-col-reverse gap-2 border-t border-warning/20 pt-4 sm:flex-row sm:justify-end">
        <Button
          className="w-full sm:w-auto"
          disabled={isSubmitting}
          onClick={() => onDecision("reject")}
          type="button"
          variant="secondary"
        >
          Keep deterministic report
        </Button>
        <Button
          className="w-full sm:w-auto"
          disabled={isSubmitting}
          onClick={() => onDecision("approve")}
          type="button"
        >
          Approve live draft
        </Button>
      </div>

      <p aria-live="polite" className="sr-only">
        {isSubmitting ? "Submitting your live draft decision." : ""}
      </p>
    </section>
  );
}

function ProposalSection({
  children,
  icon,
  title
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <article className="h-full rounded-md border border-border bg-surface p-3">
      <div className="flex items-center gap-2">
        {icon}
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      </div>
      <div className="mt-2">{children}</div>
    </article>
  );
}

function formatWarningCode(code: string): string {
  return code
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
