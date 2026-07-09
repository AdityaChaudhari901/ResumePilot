import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  Plus,
  Trash2
} from "lucide-react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type {
  JobPreviewResponse,
  JobPreviewStatus,
  JobProfile,
  JobSkill
} from "@/features/dashboard/types";

interface JobEvidenceReviewCardProps {
  preview: JobPreviewResponse;
  onBack: () => void;
  onContinue: (profile: JobProfile) => Promise<void> | void;
}

type SkillGroupName = "required" | "preferred";

export function JobEvidenceReviewCard({
  onBack,
  onContinue,
  preview
}: JobEvidenceReviewCardProps) {
  const [profile, setProfile] = useState<JobProfile>(preview.profile);
  const [responsibilitiesText, setResponsibilitiesText] = useState(
    preview.profile.responsibilities.join("\n")
  );

  const reviewedProfile = useMemo(
    () => sanitizeProfile(profile, responsibilitiesText),
    [profile, responsibilitiesText]
  );
  const hasActionableSkills =
    reviewedProfile.required_skills.length > 0 || reviewedProfile.preferred_skills.length > 0;
  const statusTone = statusBadgeTone(preview.status);
  const statusLabel = statusBadgeLabel(preview.status);

  return (
    <Panel
      action={<Badge tone={statusTone}>{statusLabel}</Badge>}
      eyebrow="Step 02"
      title="Review job evidence"
    >
      <div className="space-y-5">
        {preview.status !== "ready" ? (
          <div className="rounded-lg border border-warning/25 bg-warning/10 p-4" role="status">
            <div className="flex gap-3">
              <AlertTriangle
                className="mt-0.5 h-5 w-5 shrink-0 text-warning"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-semibold text-foreground">
                  Job evidence needs review
                </p>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  ResumePilot fetched the page, but some job evidence is incomplete. Edit the
                  fields below before continuing, or continue with a warning if the listing does
                  not expose requirements.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <section className="grid gap-3 md:grid-cols-3" aria-label="Job extraction summary">
          <SummaryTile
            icon={<BriefcaseBusiness className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Parser"
            value={preview.parser}
          />
          <SummaryTile
            icon={<FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Readable text"
            value={`${preview.raw_text_char_count.toLocaleString()} chars`}
          />
          <SummaryTile
            icon={<CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />}
            label="Quality"
            value={statusLabel}
          />
        </section>

        <section className="grid gap-4 md:grid-cols-2" aria-label="Editable job basics">
          <label className="block">
            <span className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
              <BriefcaseBusiness className="h-4 w-4 text-primary" aria-hidden="true" />
              Role
            </span>
            <input
              className="h-11 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
              onChange={(event) => updateProfileField(setProfile, "role_title", event.target.value)}
              placeholder="Backend Engineer"
              value={profile.role_title ?? ""}
            />
          </label>
          <label className="block">
            <span className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
              <Building2 className="h-4 w-4 text-primary" aria-hidden="true" />
              Company
            </span>
            <input
              className="h-11 w-full rounded-md border border-border bg-surface-inset px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
              onChange={(event) => updateProfileField(setProfile, "company", event.target.value)}
              placeholder="Company name"
              value={profile.company ?? ""}
            />
          </label>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <EditableSkillGroup
            group="required"
            onAdd={() => addSkill(setProfile, "required")}
            onRemove={(skillId) => removeSkill(setProfile, "required", skillId)}
            onUpdate={(skillId, patch) => updateSkill(setProfile, "required", skillId, patch)}
            skills={profile.required_skills}
            title="Required skills"
          />
          <EditableSkillGroup
            group="preferred"
            onAdd={() => addSkill(setProfile, "preferred")}
            onRemove={(skillId) => removeSkill(setProfile, "preferred", skillId)}
            onUpdate={(skillId, patch) => updateSkill(setProfile, "preferred", skillId, patch)}
            skills={profile.preferred_skills}
            title="Preferred skills"
          />
        </section>

        <section>
          <div className="mb-3 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Responsibilities</h3>
          </div>
          <textarea
            className="min-h-32 w-full rounded-md border border-border bg-surface-inset px-3 py-2 text-sm leading-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
            onChange={(event) => setResponsibilitiesText(event.target.value)}
            placeholder="One responsibility per line"
            value={responsibilitiesText}
          />
        </section>

        {preview.quality_checks.length > 0 ? (
          <section>
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Extraction quality</h3>
            </div>
            <div className="space-y-2">
              {preview.quality_checks.map((check) => (
                <div className="rounded-md border border-border bg-surface p-3" key={check.code}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={qualityTone(check.status)}>{check.status}</Badge>
                    <span className="text-sm font-medium text-foreground">{check.code}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{check.message}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <Button
            icon={<ArrowLeft className="h-4 w-4" aria-hidden="true" />}
            onClick={onBack}
            variant="secondary"
          >
            Edit job URL
          </Button>
          <Button
            icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
            onClick={() => void onContinue(reviewedProfile)}
          >
            {hasActionableSkills ? "Save and continue" : "Continue with warning"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

function SummaryTile({
  icon,
  label,
  value
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
          {label}
        </p>
      </div>
      <p className="mt-2 truncate text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

interface EditableSkillGroupProps {
  group: SkillGroupName;
  skills: JobSkill[];
  title: string;
  onAdd: () => void;
  onRemove: (skillId: string) => void;
  onUpdate: (skillId: string, patch: Partial<JobSkill>) => void;
}

function EditableSkillGroup({
  group,
  onAdd,
  onRemove,
  onUpdate,
  skills,
  title
}: EditableSkillGroupProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-validation" aria-hidden="true" />
          <h3 className="text-sm font-semibold">{title}</h3>
        </div>
        <Button
          className="h-8 px-3 text-xs"
          icon={<Plus className="h-3.5 w-3.5" aria-hidden="true" />}
          onClick={onAdd}
          variant="secondary"
        >
          Add
        </Button>
      </div>
      <div className="space-y-2">
        {skills.map((skill) => (
          <div className="rounded-md border border-border bg-surface p-3" key={skill.id}>
            <div className="flex items-start gap-2">
              <label className="min-w-0 flex-1">
                <span className="sr-only">{group} skill name</span>
                <input
                  className="h-10 w-full rounded-md border border-border bg-surface-inset px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
                  onChange={(event) => onUpdate(skill.id, { name: event.target.value })}
                  placeholder="Skill name"
                  value={skill.name}
                />
              </label>
              <Button
                aria-label={`Remove ${skill.name || group} skill`}
                className="h-10 w-10 px-0"
                icon={<Trash2 className="h-4 w-4" aria-hidden="true" />}
                onClick={() => onRemove(skill.id)}
                variant="ghost"
              />
            </div>
            <label className="mt-2 block">
              <span className="sr-only">{group} skill evidence</span>
              <textarea
                className="min-h-20 w-full rounded-md border border-border bg-surface-inset px-3 py-2 text-xs leading-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35"
                onChange={(event) => onUpdate(skill.id, { evidence_text: event.target.value })}
                placeholder="Evidence text from the job listing"
                value={skill.evidence_text}
              />
            </label>
          </div>
        ))}
        {skills.length === 0 ? (
          <div className="rounded-md border border-border bg-surface p-3 text-sm leading-6 text-muted-foreground">
            No {group} skills yet. Add truthful skills only if the job listing supports them.
          </div>
        ) : null}
      </div>
    </section>
  );
}

function updateProfileField(
  setProfile: Dispatch<SetStateAction<JobProfile>>,
  field: "role_title" | "company",
  value: string
) {
  setProfile((current) => ({
    ...current,
    [field]: value
  }));
}

function addSkill(
  setProfile: Dispatch<SetStateAction<JobProfile>>,
  group: SkillGroupName
) {
  setProfile((current) => {
    const key = group === "required" ? "required_skills" : "preferred_skills";
    const nextIndex = current[key].length + 1;
    const nextSkill: JobSkill = {
      confidence: "medium",
      evidence_text: "",
      id: `reviewed_${group}_${String(nextIndex).padStart(3, "0")}`,
      importance: group,
      name: ""
    };
    return {
      ...current,
      [key]: [...current[key], nextSkill]
    };
  });
}

function removeSkill(
  setProfile: Dispatch<SetStateAction<JobProfile>>,
  group: SkillGroupName,
  skillId: string
) {
  setProfile((current) => {
    const key = group === "required" ? "required_skills" : "preferred_skills";
    return {
      ...current,
      [key]: current[key].filter((skill) => skill.id !== skillId)
    };
  });
}

function updateSkill(
  setProfile: Dispatch<SetStateAction<JobProfile>>,
  group: SkillGroupName,
  skillId: string,
  patch: Partial<JobSkill>
) {
  setProfile((current) => {
    const key = group === "required" ? "required_skills" : "preferred_skills";
    return {
      ...current,
      [key]: current[key].map((skill) =>
        skill.id === skillId ? { ...skill, ...patch } : skill
      )
    };
  });
}

function sanitizeProfile(profile: JobProfile, responsibilitiesText: string): JobProfile {
  const requiredSkills = sanitizeSkills(profile.required_skills, "required");
  const preferredSkills = sanitizeSkills(profile.preferred_skills, "preferred");
  return {
    ...profile,
    company: blankToNull(profile.company),
    keywords: uniqueStrings([
      ...profile.keywords,
      ...requiredSkills.map((skill) => skill.name),
      ...preferredSkills.map((skill) => skill.name)
    ]),
    preferred_skills: preferredSkills,
    required_skills: requiredSkills,
    responsibilities: responsibilitiesText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
    role_title: blankToNull(profile.role_title)
  };
}

function sanitizeSkills(skills: JobSkill[], group: SkillGroupName): JobSkill[] {
  return skills
    .map((skill, index) => ({
      ...skill,
      evidence_text: skill.evidence_text.trim() || `${group} skill added during review.`,
      id: skill.id || `reviewed_${group}_${String(index + 1).padStart(3, "0")}`,
      importance: group,
      name: skill.name.trim()
    }))
    .filter((skill) => skill.name.length > 0);
}

function blankToNull(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed.length > 0 ? trimmed : null;
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean))).sort();
}

function qualityTone(status: "pass" | "warn" | "fail") {
  if (status === "pass") {
    return "success";
  }
  if (status === "fail") {
    return "danger";
  }
  return "warning";
}

function statusBadgeTone(status: JobPreviewStatus) {
  if (status === "ready") {
    return "success";
  }
  if (status === "blocked_private" || status === "too_short" || status === "missing_requirements") {
    return "danger";
  }
  return "warning";
}

function statusBadgeLabel(status: JobPreviewStatus): string {
  const labels: Record<JobPreviewStatus, string> = {
    blocked_private: "Blocked/private",
    missing_requirements: "Missing requirements",
    needs_review: "Needs review",
    ready: "Evidence extracted",
    too_short: "Too short"
  };
  return labels[status];
}
