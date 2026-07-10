import { FileUp, Loader2 } from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { ResumeUploadResponse } from "@/features/dashboard/types";

interface ResumeUploadCardProps {
  fileName: string;
  isUploading: boolean;
  resume: ResumeUploadResponse | null;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ResumeUploadCard({
  fileName,
  isUploading,
  onFileChange,
  onSubmit,
  resume
}: ResumeUploadCardProps) {
  return (
    <Panel eyebrow="Step 03" title="Resume upload">
      <form className="space-y-5" onSubmit={onSubmit}>
        <label className="block rounded-2xl border border-dashed border-border-strong bg-surface p-5 transition-colors focus-within:border-primary focus-within:bg-primary/5 sm:p-7">
          <span className="flex items-center gap-3 text-sm font-bold text-foreground">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-primary-foreground">
              <FileUp className="h-5 w-5" aria-hidden="true" />
            </span>
            <span>
              Resume file
              <span className="mt-1 block text-xs font-normal leading-5 text-muted-foreground">
                PDF, DOCX, TXT, Markdown
              </span>
            </span>
          </span>
          <input
            accept=".pdf,.docx,.txt,.md,.markdown"
            className="mt-5 block w-full rounded-lg border border-border bg-surface-inset px-3 py-2.5 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-foreground file:px-3 file:py-1.5 file:text-sm file:font-bold file:text-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            onChange={onFileChange}
            type="file"
          />
        </label>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-h-5 text-sm text-muted-foreground">
            {fileName ? `Selected: ${fileName}` : "Choose one resume file to continue."}
          </p>
          <Button
            disabled={isUploading || !fileName}
            icon={
              isUploading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <FileUp className="h-4 w-4" aria-hidden="true" />
              )
            }
            type="submit"
          >
            Upload
          </Button>
        </div>
      </form>

      {resume && (
        <div className="mt-5 rounded-xl border border-validation/30 bg-validation/10 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">
                {resume.candidate_name || "Candidate profile"}
              </p>
              <p className="text-xs text-muted-foreground">Resume ID {resume.resume_id}</p>
            </div>
            <Badge tone="success">{resume.status}</Badge>
          </div>
          {resume.warnings.length > 0 && (
            <p className="mt-3 text-xs text-warning">
              {resume.warnings.length} parser warning{resume.warnings.length === 1 ? "" : "s"}
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}
