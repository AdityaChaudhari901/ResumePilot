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
    <Panel eyebrow="Step 01" title="Resume dossier">
      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-foreground">Resume file</span>
          <input
            accept=".pdf,.docx,.txt,.md,.markdown"
            className="block w-full rounded-md border border-border bg-surface-inset px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            onChange={onFileChange}
            type="file"
          />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="min-h-5 text-sm text-muted-foreground">
            {fileName || "PDF, DOCX, TXT, Markdown"}
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
        <div className="mt-4 rounded-md border border-border bg-surface p-3">
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
