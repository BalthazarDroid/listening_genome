/**
 * Job and time wording for the import page, ported from the fork's GenomeSettings.vue.
 * Pure functions, so they are unit-tested without a DOM.
 */
import { t } from "../i18n";
import type { GenomeJob, GenomeJobName, GenomeJobs } from "../types";

/** The jobs in the order the status list shows them (the backend's own order). */
export const JOB_ORDER: GenomeJobName[] = [
  "rebuild",
  "enrichment",
  "lastfm_import",
  "apple_import",
  "duplicates",
  "discovery",
];

/**
 * "4 minutes ago" without a date library. Rounded rather than truncated: "59 seconds ago"
 * reading as "just now" is fine, "119 seconds ago" reading as "1 minute ago" is not.
 */
export function relativeTime(timestamp: number | null | undefined, nowSeconds: number): string {
  if (!timestamp) return "";
  const seconds = Math.max(0, nowSeconds - timestamp);
  if (seconds < 45) return t("settings.time_just_now");
  const minutes = Math.round(seconds / 60);
  if (minutes <= 1) return t("settings.time_minute_ago");
  if (minutes < 60) return t("settings.time_minutes_ago", { count: minutes });
  const hours = Math.round(minutes / 60);
  if (hours <= 1) return t("settings.time_hour_ago");
  if (hours < 24) return t("settings.time_hours_ago", { count: hours });
  const days = Math.round(hours / 24);
  if (days <= 1) return t("settings.time_day_ago");
  return t("settings.time_days_ago", { count: days });
}

/** Readable job name; an unknown id (a newer backend) falls back to the id itself. */
export function jobLabel(name: string): string {
  const label = t(`panel.job.${name}`);
  return label === `panel.job.${name}` ? name.replace(/_/g, " ") : label;
}

/** Readable job state. */
export function stateLabel(state: string): string {
  const label = t(`panel.state.${state}`);
  return label === `panel.state.${state}` ? state : label;
}

/** Every job the backend reported, known ones first in the backend's order, then any others. */
export function orderedJobs(jobs: GenomeJobs | Record<string, GenomeJob>): GenomeJob[] {
  const map = jobs as Record<string, GenomeJob>;
  const known = JOB_ORDER.filter((name) => map[name]).map((name) => ({ ...map[name], job: name }));
  const extra = Object.keys(map)
    .filter((name) => !(JOB_ORDER as string[]).includes(name))
    .map((name) => ({ ...map[name], job: name }));
  return [...known, ...extra];
}

export function anyRunning(jobs: Record<string, GenomeJob> | null | undefined): boolean {
  return !!jobs && Object.values(jobs).some((job) => job.state === "running");
}

/**
 * The line under a job: the server's own wording (never reworded), plus when it finished or
 * started. Idle jobs that never ran say so.
 */
export function jobDetail(job: GenomeJob, nowSeconds: number): string {
  if (job.state === "running") {
    const since = relativeTime(job.started_at, nowSeconds);
    const message = job.message || t("panel.job_working");
    return since ? t("panel.job_started", { message, when: since }) : message;
  }
  if (job.state === "idle" && !job.message) return t("panel.job_never");
  const when = relativeTime(job.finished_at ?? job.started_at, nowSeconds);
  if (!job.message) return when;
  return when ? t("settings.job_result_when", { message: job.message, when }) : job.message;
}
