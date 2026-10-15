import { headers as getRequestHeaders } from "next/headers";

export type ScanStatus = "queued" | "running" | "completed" | "failed";
export type FindingSeverity = "error" | "warning" | "info";
export type FindingConfidence = "high" | "medium" | "low";
export type ApiErrorKind = "forbidden" | "unavailable" | "error";

export interface Finding {
  id: string;
  fingerprint: string;
  ruleId: string;
  severity: FindingSeverity;
  confidence: FindingConfidence;
  message: string;
  why: string;
  suggestion: string;
  file: string;
  line: number;
  col: number;
  endLine: number;
  endCol: number;
  metadata: Record<string, unknown>;
}

export interface ScanSummary {
  id: string;
  scanKey: string;
  repositoryId: string;
  branchId: string | null;
  commitId: string | null;
  status: ScanStatus;
  analyzerVersion: string;
  findingCount: number;
  createdAt: string;
}

export interface Scan extends ScanSummary {
  findings: Finding[];
  branchName: string | null;
  commitSha: string | null;
  commitMessage: string | null;
  pullRequest: PullRequestContext | null;
}

export interface Page<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  pages: number;
}

export interface RepositorySummary {
  id: string;
  provider: string;
  fullName: string;
  defaultBranch: string | null;
  findingCount: number;
  riskScore: number | null;
  updatedAt: string | null;
  latestScan: ScanSummary | null;
}

export interface TrendPoint {
  date: string;
  findingCount: number;
  errorCount: number;
  scanCount: number;
}

export interface BaselineComparison {
  available: boolean;
  reference: string | null;
  newFindings: number;
  resolvedFindings: number;
  unchangedFindings: number;
}

export interface PullRequestContext {
  number: number;
  title: string | null;
  url: string | null;
  headSha: string;
  status: "open" | "merged" | "closed" | "unknown";
}

export interface RepositoryDetail extends RepositorySummary {
  trend: TrendPoint[];
  scans: Page<ScanSummary>;
  recentFindings: Finding[];
  baseline: BaselineComparison | null;
  pullRequests: PullRequestContext[];
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly details: unknown;

  constructor(
    message: string,
    kind: ApiErrorKind,
    status: number | null,
    details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.details = details;
  }
}

export type LoadResult<T> =
  | { status: "success"; data: T }
  | { status: "error"; error: ApiError };

interface FindingResponse {
  id: string;
  fingerprint: string;
  rule_id: string;
  severity: FindingSeverity;
  confidence: FindingConfidence;
  message: string;
  why: string;
  suggestion: string;
  file: string;
  line: number;
  col: number;
  end_line: number;
  end_col: number;
  metadata: Record<string, unknown>;
}

interface ScanSummaryResponse {
  id: string;
  scan_key: string;
  repository_id: string;
  branch_id: string | null;
  commit_id: string | null;
  status: ScanStatus;
  analyzer_version: string;
  finding_count: number;
  created_at: string;
}

interface PullRequestContextResponse {
  number: number;
  title: string | null;
  url: string | null;
  head_sha: string;
  status: PullRequestContext["status"];
}

interface ScanResponse extends ScanSummaryResponse {
  findings: FindingResponse[];
  branch_name?: string | null;
  commit_sha?: string | null;
  commit_message?: string | null;
  pull_request?: PullRequestContextResponse | null;
}

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

interface RepositorySummaryResponse {
  id: string;
  provider: string;
  full_name: string;
  default_branch: string | null;
  finding_count: number;
  risk_score: number | null;
  updated_at: string | null;
  latest_scan: ScanSummaryResponse | null;
}

interface TrendPointResponse {
  date: string;
  finding_count: number;
  error_count: number;
  scan_count: number;
}

interface BaselineComparisonResponse {
  available: boolean;
  reference: string | null;
  new_findings: number;
  resolved_findings: number;
  unchanged_findings: number;
}

interface RepositoryDetailResponse {
  repository: RepositorySummaryResponse;
  trend: TrendPointResponse[];
  scans: PageResponse<ScanSummaryResponse>;
  recent_findings: FindingResponse[];
  baseline: BaselineComparisonResponse | null;
  pull_requests: PullRequestContextResponse[];
}

const apiBaseUrl = (): string => {
  const configured =
    process.env.AGENTGUARD_API_URL ?? process.env.NEXT_PUBLIC_AGENTGUARD_API_URL;
  return (configured ?? "http://localhost:8000").replace(/\/$/, "");
};

const forwardedRequestHeaders = (): Headers => {
  const incoming = getRequestHeaders();
  const forwarded = new Headers();
  const authorization = incoming.get("authorization");
  const cookie = incoming.get("cookie");

  if (authorization) forwarded.set("authorization", authorization);
  if (cookie) forwarded.set("cookie", cookie);
  return forwarded;
};

const errorKindForStatus = (status: number): ApiErrorKind => {
  if (status === 401 || status === 403) return "forbidden";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  return "error";
};

const messageFromDetails = (details: unknown): string | null => {
  if (typeof details !== "object" || details === null) return null;
  if (!("detail" in details)) return null;
  const detail = details.detail;
  return typeof detail === "string" ? detail : null;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = forwardedRequestHeaders();
  headers.set("accept", "application/json");

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      headers
    });

    if (!response.ok) {
      let details: unknown;
      try {
        details = await response.json();
      } catch {
        details = undefined;
      }
      throw new ApiError(
        messageFromDetails(details) ?? `The API returned HTTP ${response.status}.`,
        errorKindForStatus(response.status),
        response.status,
        details
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const message = error instanceof Error ? error.message : "The API request failed.";
    throw new ApiError(
      `The dashboard service could not be reached: ${message}`,
      "unavailable",
      null,
      error
    );
  }
}

const mapFinding = (finding: FindingResponse): Finding => ({
  id: finding.id,
  fingerprint: finding.fingerprint,
  ruleId: finding.rule_id,
  severity: finding.severity,
  confidence: finding.confidence,
  message: finding.message,
  why: finding.why,
  suggestion: finding.suggestion,
  file: finding.file,
  line: finding.line,
  col: finding.col,
  endLine: finding.end_line,
  endCol: finding.end_col,
  metadata: finding.metadata
});

const mapScanSummary = (scan: ScanSummaryResponse): ScanSummary => ({
  id: scan.id,
  scanKey: scan.scan_key,
  repositoryId: scan.repository_id,
  branchId: scan.branch_id,
  commitId: scan.commit_id,
  status: scan.status,
  analyzerVersion: scan.analyzer_version,
  findingCount: scan.finding_count,
  createdAt: scan.created_at
});

const mapPage = <TResponse, T>(
  page: PageResponse<TResponse>,
  mapItem: (item: TResponse) => T
): Page<T> => ({
  items: page.items.map(mapItem),
  page: page.page,
  pageSize: page.page_size,
  total: page.total,
  pages: page.pages
});

const mapPullRequest = (
  pullRequest: PullRequestContextResponse
): PullRequestContext => ({
  number: pullRequest.number,
  title: pullRequest.title,
  url: pullRequest.url,
  headSha: pullRequest.head_sha,
  status: pullRequest.status
});

const mapRepository = (repository: RepositorySummaryResponse): RepositorySummary => ({
  id: repository.id,
  provider: repository.provider,
  fullName: repository.full_name,
  defaultBranch: repository.default_branch,
  findingCount: repository.finding_count,
  riskScore: repository.risk_score,
  updatedAt: repository.updated_at,
  latestScan: repository.latest_scan ? mapScanSummary(repository.latest_scan) : null
});

const mapScan = (scan: ScanResponse): Scan => ({
  ...mapScanSummary(scan),
  findings: scan.findings.map(mapFinding),
  branchName: scan.branch_name ?? null,
  commitSha: scan.commit_sha ?? null,
  commitMessage: scan.commit_message ?? null,
  pullRequest: scan.pull_request ? mapPullRequest(scan.pull_request) : null
});

export async function getRepositories(page = 1, pageSize = 50): Promise<Page<RepositorySummary>> {
  const response = await requestJson<PageResponse<RepositorySummaryResponse>>(
    `/api/v1/repositories?page=${page}&page_size=${pageSize}`
  );
  return mapPage(response, mapRepository);
}

export async function getRepository(repositoryId: string): Promise<RepositoryDetail> {
  const response = await requestJson<RepositoryDetailResponse>(
    `/api/v1/repositories/${encodeURIComponent(repositoryId)}`
  );
  const repository = mapRepository(response.repository);
  return {
    ...repository,
    trend: response.trend.map((point) => ({
      date: point.date,
      findingCount: point.finding_count,
      errorCount: point.error_count,
      scanCount: point.scan_count
    })),
    scans: mapPage(response.scans, mapScanSummary),
    recentFindings: response.recent_findings.map(mapFinding),
    baseline: response.baseline
      ? {
          available: response.baseline.available,
          reference: response.baseline.reference,
          newFindings: response.baseline.new_findings,
          resolvedFindings: response.baseline.resolved_findings,
          unchangedFindings: response.baseline.unchanged_findings
        }
      : null,
    pullRequests: response.pull_requests.map(mapPullRequest)
  };
}

export async function getRepositoryScans(
  repositoryId: string,
  page = 1,
  pageSize = 20
): Promise<Page<ScanSummary>> {
  const response = await requestJson<PageResponse<ScanSummaryResponse>>(
    `/api/v1/repositories/${encodeURIComponent(repositoryId)}/scans?page=${page}&page_size=${pageSize}`
  );
  return mapPage(response, mapScanSummary);
}

export async function getScan(scanId: string): Promise<Scan> {
  const response = await requestJson<ScanResponse>(
    `/api/v1/scans/${encodeURIComponent(scanId)}`
  );
  return mapScan(response);
}

export async function loadApi<T>(operation: () => Promise<T>): Promise<LoadResult<T>> {
  try {
    return { status: "success", data: await operation() };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", error };
    }
    return {
      status: "error",
      error: new ApiError("The dashboard request failed.", "error", null, error)
    };
  }
}
