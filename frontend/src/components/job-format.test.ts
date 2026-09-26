import { describe, expect, it } from "vitest";
import { anyRunning, jobDetail, jobLabel, orderedJobs, relativeTime, stateLabel } from "./job-format";
import type { GenomeJob } from "../types";

const NOW = 1_800_000_000;
const job = (o: Partial<GenomeJob> = {}): GenomeJob => ({
  job: "rebuild",
  state: "ok",
  message: "Rebuilt",
  started_at: NOW - 400,
  finished_at: NOW - 300,
  progress: null,
  ...o,
});

describe("relativeTime", () => {
  it.each([
    [null, ""],
    [NOW - 10, "just now"],
    [NOW - 80, "1 minute ago"],
    [NOW - 119, "2 minutes ago"],
    [NOW - 300, "5 minutes ago"],
    [NOW - 3600, "1 hour ago"],
    [NOW - 5 * 3600, "5 hours ago"],
    [NOW - 30 * 3600, "1 day ago"],
    [NOW - 4 * 86400, "4 days ago"],
    [NOW + 100, "just now"],
  ])("%s -> %s", (ts, expected) => {
    expect(relativeTime(ts as number | null, NOW)).toBe(expected);
  });
});

describe("labels", () => {
  it("names every known job and state, and falls back for unknown ones", () => {
    expect(jobLabel("lastfm_import")).toBe("Last.fm import");
    expect(jobLabel("export_db")).toBe("export db");
    expect(stateLabel("ok")).toBe("Done");
    expect(stateLabel("weird")).toBe("weird");
  });
});

describe("orderedJobs", () => {
  it("lists every job: known ones in backend order, unknown ones after", () => {
    const jobs = {
      discovery: job({ job: "discovery" }),
      extra_job: job({ job: "extra_job" }),
      rebuild: job(),
      apple_import: job({ job: "apple_import" }),
    };
    expect(orderedJobs(jobs).map((j) => j.job)).toEqual([
      "rebuild",
      "apple_import",
      "discovery",
      "extra_job",
    ]);
  });
  it("detects a running job", () => {
    expect(anyRunning({ a: job(), b: job({ state: "running" }) })).toBe(true);
    expect(anyRunning({ a: job() })).toBe(false);
    expect(anyRunning(null)).toBe(false);
  });
});

describe("jobDetail", () => {
  it("keeps the server's message and adds when it finished", () => {
    expect(jobDetail(job(), NOW)).toBe("Rebuilt · 5 minutes ago");
  });
  it("says when a running job started, with a fallback message", () => {
    expect(jobDetail(job({ state: "running", message: "", finished_at: null }), NOW)).toBe(
      "Working… · started 7 minutes ago",
    );
  });
  it("says an idle job without a message has not run", () => {
    expect(jobDetail(job({ state: "idle", message: "" }), NOW)).toBe("Not run yet");
  });
  it("shows an error message verbatim", () => {
    expect(jobDetail(job({ state: "error", message: "boom", finished_at: null }), NOW)).toBe(
      "boom · 7 minutes ago",
    );
  });
});
