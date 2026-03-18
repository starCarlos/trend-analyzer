const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:5060";

export type ContentSource = "all" | "newsnow" | "github";

export type BackfillTask = {
  source: string;
  task_type: string;
  status: string;
  message?: string | null;
};

export type BackfillJob = {
  id: number;
  status: string;
  error_message?: string | null;
  tasks: BackfillTask[];
};

export type SearchResponse = {
  keyword: {
    id: number;
    raw_query: string;
    normalized_query: string;
    kind: "github_repo" | "keyword";
    is_tracked: boolean;
  };
  availability: Record<string, string>;
  snapshot: {
    github_star_today?: number | null;
    newsnow_platform_count?: number | null;
    newsnow_item_count?: number | null;
    updated_at?: string | null;
  };
  trend: {
    period: {
      start?: string | null;
      end?: string | null;
    };
    series: {
      source: string;
      metric: string;
      source_type: string;
      points: Array<{ bucket_start: string; value: number }>;
    }[];
  };
  content_items: Array<{
    id: number;
    source: string;
    source_type: string;
    title: string;
    url?: string | null;
    summary?: string | null;
    author?: string | null;
    published_at?: string | null;
  }>;
  backfill_job?: BackfillJob | null;
};

export type BackfillStatusResponse = {
  job_id: number;
  status: string;
  tasks: BackfillTask[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function searchKeyword(query: string, period: string, contentSource: ContentSource = "all"): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, period, content_source: contentSource });
  return request<SearchResponse>(`/api/search?${params.toString()}`);
}

export function getBackfillStatus(keywordId: number): Promise<BackfillStatusResponse> {
  return request<BackfillStatusResponse>(`/api/keywords/${keywordId}/backfill-status`);
}

export async function setTracked(keywordId: number, tracked: boolean): Promise<void> {
  await request(`/api/keywords/${keywordId}/track`, {
    method: tracked ? "POST" : "DELETE",
  });
}
