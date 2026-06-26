export type QueryResponse = {
  question: string;
  answer: string | null;
  sql: string | null;
  row_count: number;
  summary: string;
  rows: Record<string, unknown>[];
  exam_province: string;
  plan_year: number;
  subject_category: string | null;
  availability: {
    available: boolean;
    reasons: string[];
    message: string;
    ignored_metric_conditions: string[];
  };
  notes: string[];
  citations: Array<{
    source: string;
    label: string;
    fields: string[];
    exam_province: string;
    plan_year: number;
    note: string;
  }>;
  coverage_warnings: Array<{
    field: string;
    label: string;
    coverage_ratio: number;
    message: string;
  }>;
  template_name: string | null;
};

export type PolicyQueryResponse = {
  question: string;
  answer: string | null;
  result_count: number;
  results: PolicyResult[];
  citations: PolicyCitation[];
  notes: string[];
};

export type PolicyResult = {
  id: number;
  title: string;
  category: string;
  snippet: string;
  similarity: number;
  source_url: string | null;
  school_name: string | null;
  document_year: number | null;
  page_number: number | null;
  page_side: string | null;
  heading_path: string[];
  table_title: string | null;
  context_text: string | null;
  context_chunk_ids: string[];
};

export type PolicyCitation = {
  title: string;
  category: string;
  source_url: string | null;
  school_name: string | null;
  document_year: number | null;
  page_number: number | null;
  page_side: string | null;
  heading_path: string[];
  table_title: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type QueryPayload = {
  question: string;
  exam_province?: string;
  plan_year?: number;
  history?: ChatMessage[];
};

type PolicyPayload = {
  question: string;
  school?: string;
  year?: number;
  category?: string;
  province?: string;
  top_k?: number;
  include_context?: boolean;
};

export async function queryAdmission(
  payload: QueryPayload,
  apiKey: string,
  gpuRentApiKey: string,
): Promise<QueryResponse> {
  return requestJson<QueryResponse>("/query", payload, apiKey, gpuRentApiKey);
}

export async function queryPolicy(
  payload: PolicyPayload,
  apiKey: string,
  gpuRentApiKey: string,
): Promise<PolicyQueryResponse> {
  return requestJson<PolicyQueryResponse>("/policy/query", payload, apiKey, gpuRentApiKey);
}

async function requestJson<T>(
  path: string,
  body: unknown,
  apiKey: string,
  gpuRentApiKey: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json; charset=utf-8",
  };
  if (apiKey.trim()) {
    headers["X-API-Key"] = apiKey.trim();
  }
  if (gpuRentApiKey.trim()) {
    headers["X-GPURent-API-Key"] = gpuRentApiKey.trim();
  }

  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const text = await response.text();
  const data = parseJson(text);
  if (!response.ok) {
    const message =
      getErrorDetail(data) ??
      normalizeErrorText(text) ??
      response.statusText ??
      "请求失败";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  if (data === null) {
    throw new Error("后端返回空响应。");
  }
  return data as T;
}

function parseJson(text: string): unknown | null {
  if (!text.trim()) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function getErrorDetail(data: unknown): unknown | null {
  if (typeof data !== "object" || data === null || !("detail" in data)) {
    return null;
  }
  return (data as { detail: unknown }).detail;
}

function normalizeErrorText(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.includes("ECONNREFUSED") || trimmed.includes("Internal Server Error")) {
    return "API 服务不可达或内部错误。请确认 FastAPI 已在 127.0.0.1:8000 启动。";
  }
  return trimmed.replace(/<[^>]+>/g, "").trim() || null;
}
