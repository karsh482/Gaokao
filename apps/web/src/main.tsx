import { FormEvent, ReactNode, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  BookOpenText,
  Database,
  FileText,
  Loader2,
  Search,
  Settings,
  Table2,
} from "lucide-react";
import {
  PolicyQueryResponse,
  QueryResponse,
  queryAdmission,
  queryPolicy,
} from "./api";
import "./styles.css";

type Mode = "admission" | "policy";

function App() {
  const [mode, setMode] = useState<Mode>("admission");
  const [apiKey, setApiKey] = useState(localStorage.getItem("gaokaoApiKey") ?? "");

  function updateApiKey(value: string) {
    setApiKey(value);
    localStorage.setItem("gaokaoApiKey", value);
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">G</div>
          <div>
            <h1>Gaokao AI 查询台</h1>
            <p>结构化录取查询与政策 RAG</p>
          </div>
        </div>

        <nav className="modeNav" aria-label="查询模式">
          <button
            className={mode === "admission" ? "active" : ""}
            onClick={() => setMode("admission")}
            type="button"
          >
            <Database size={18} />
            录取查询
          </button>
          <button
            className={mode === "policy" ? "active" : ""}
            onClick={() => setMode("policy")}
            type="button"
          >
            <BookOpenText size={18} />
            政策问答
          </button>
        </nav>

        <label className="field">
          <span>
            <Settings size={15} />
            API Key
          </span>
          <input
            value={apiKey}
            onChange={(event) => updateApiKey(event.target.value)}
            placeholder="本地未启用鉴权可留空"
            type="password"
          />
        </label>
      </aside>

      <section className="workspace">
        {mode === "admission" ? (
          <AdmissionPanel apiKey={apiKey} />
        ) : (
          <PolicyPanel apiKey={apiKey} />
        )}
      </section>
    </main>
  );
}

function AdmissionPanel({ apiKey }: { apiKey: string }) {
  const [question, setQuestion] = useState("");
  const [examProvince, setExamProvince] = useState("贵州");
  const [planYear, setPlanYear] = useState(2025);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setResult(
        await queryAdmission(
          {
            question,
            exam_province: examProvince || undefined,
            plan_year: planYear || undefined,
          },
          apiKey,
        ),
      );
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <QueryHeader title="志愿咨询" />
      <form className="queryForm" onSubmit={submit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={4}
        />
        <div className="formGrid">
          <label>
            <span>考试省份</span>
            <input value={examProvince} onChange={(event) => setExamProvince(event.target.value)} />
          </label>
          <label>
            <span>招生年份</span>
            <input
              value={planYear}
              onChange={(event) => setPlanYear(Number(event.target.value))}
              type="number"
            />
          </label>
          <button disabled={loading || !question.trim()} type="submit">
            {loading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            查询
          </button>
        </div>
      </form>
      {error && <ErrorMessage message={error} />}
      {result && <AdmissionResult result={result} />}
    </div>
  );
}

function PolicyPanel({ apiKey }: { apiKey: string }) {
  const [question, setQuestion] = useState("");
  const [school, setSchool] = useState("北京大学");
  const [year, setYear] = useState(2026);
  const [category, setCategory] = useState("university_admission_chapter");
  const [result, setResult] = useState<PolicyQueryResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      setResult(
        await queryPolicy(
          {
            question,
            school: school || undefined,
            year: year || undefined,
            category: category || undefined,
            top_k: 5,
            include_context: true,
          },
          apiKey,
        ),
      );
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <QueryHeader title="政策问答" />
      <form className="queryForm" onSubmit={submit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={4}
        />
        <div className="formGrid">
          <label>
            <span>学校</span>
            <input value={school} onChange={(event) => setSchool(event.target.value)} />
          </label>
          <label>
            <span>年份</span>
            <input
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              type="number"
            />
          </label>
          <label>
            <span>类别</span>
            <input value={category} onChange={(event) => setCategory(event.target.value)} />
          </label>
          <button disabled={loading || !question.trim()} type="submit">
            {loading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            查询
          </button>
        </div>
      </form>
      {error && <ErrorMessage message={error} />}
      {result && <PolicyResultView result={result} />}
    </div>
  );
}

function QueryHeader({ title }: { title: string }) {
  return (
    <header className="queryHeader">
      <h2>{title}</h2>
    </header>
  );
}

function AdmissionResult({ result }: { result: QueryResponse }) {
  return (
    <div className="resultStack">
      <AnswerBlock answer={result.answer} summary={result.summary} />
      <MetaStrip
        items={[
          ["记录数", String(result.row_count)],
          ["省份", result.exam_province],
          ["年份", String(result.plan_year)],
          ["科类", result.subject_category ?? "未限定"],
          ["查询方式", formatTemplateName(result.template_name)],
        ]}
      />
      <DataTable rows={result.rows} />
      <Details title="口径说明" icon={<FileText size={17} />}>
        <List values={result.notes} />
      </Details>
      <Details title="引用来源" icon={<BookOpenText size={17} />}>
        <List values={result.citations.map(formatAdmissionCitation)} />
      </Details>
      <Details title="调试信息" icon={<Database size={17} />}>
        <pre>{result.sql ?? "未执行 SQL"}</pre>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </Details>
    </div>
  );
}

function PolicyResultView({ result }: { result: PolicyQueryResponse }) {
  return (
    <div className="resultStack">
      <AnswerBlock answer={result.answer} summary={`检索到 ${result.result_count} 条候选片段。`} />
      <Details title="候选片段" icon={<BookOpenText size={17} />} defaultOpen>
        <div className="chunkList">
          {result.results.map((item) => (
            <article className="chunkItem" key={item.id}>
              <div className="chunkMeta">
                <strong>{item.title}</strong>
                <span>{formatSource(item)}</span>
              </div>
              <p>{item.snippet}</p>
              {item.context_text && <pre>{item.context_text}</pre>}
            </article>
          ))}
        </div>
      </Details>
      <Details title="引用来源" icon={<FileText size={17} />}>
        <List values={result.citations.map(formatCitation)} />
      </Details>
      <Details title="口径说明" icon={<AlertCircle size={17} />}>
        <List values={result.notes} />
      </Details>
      <Details title="完整响应" icon={<Table2 size={17} />}>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </Details>
    </div>
  );
}

function AnswerBlock({ answer, summary }: { answer: string | null; summary: string }) {
  return (
    <section className="answerBlock">
      <h3>回答</h3>
      <p>{answer || summary || "暂无可展示答案。"}</p>
      {answer && summary && <small>{summary}</small>}
    </section>
  );
}

function MetaStrip({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="metaStrip">
      {items.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = useMemo(() => {
    const names = new Set<string>();
    rows.slice(0, 30).forEach((row) => {
      Object.keys(row).forEach((key) => names.add(key));
    });
    return Array.from(names).sort(compareColumns);
  }, [rows]);

  if (!rows.length) {
    return <div className="emptyState">暂无明细数据。</div>;
  }

  return (
    <section className="tablePanel">
      <div className="panelTitle">
        <Table2 size={17} />
        明细数据
      </div>
      <div className="tableScroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{formatColumnLabel(column)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{formatCell(row[column], column)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Details({
  title,
  icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="detailsPanel" open={defaultOpen}>
      <summary>
        {icon}
        {title}
      </summary>
      <div>{children}</div>
    </details>
  );
}

function List({ values }: { values: string[] }) {
  if (!values.length) {
    return <p className="muted">暂无。</p>;
  }
  return (
    <ul className="plainList">
      {values.map((value, index) => (
        <li key={`${value}-${index}`}>{value}</li>
      ))}
    </ul>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="errorBox">
      <AlertCircle size={18} />
      <span>{message}</span>
    </div>
  );
}

const COLUMN_LABELS: Record<string, string> = {
  school_name: "院校",
  source_school_name: "院校原始名称",
  school_code_in_exam_province: "院校代码",
  major_name: "专业",
  major_code_in_exam_province: "专业代码",
  batch: "批次",
  subject_category: "科类",
  admission_track: "招生赛道",
  admission_program: "专项计划",
  selection_requirements: "选科要求",
  enrollment_plan_count: "招生计划数",
  filing_count: "投档人数",
  admitted_count: "录取人数",
  min_score: "最低分",
  min_rank: "最低位次",
  tuition: "学费",
  duration: "学制",
  source_page: "来源页码",
  candidate_rank: "考生位次",
  candidate_score: "考生分数",
  rank_gap: "位次差",
  score_gap: "分差",
  confidence_band: "参考档位",
  confidence_note: "说明",
  city: "院校所在城市",
  ownership: "办学性质",
  province_name: "院校所在省份",
  school_type: "院校类型",
  education_level: "办学层次",
  is_double_first_class: "双一流",
  score_label: "分数段",
  score: "分数",
  score_type: "分数口径",
  segment_name: "分段类别",
  segment_count: "本段人数",
  cumulative_count: "累计人数",
  cumulative_ratio: "累计比例",
  exam_province: "考试省份",
  plan_year: "年份",
};

const COLUMN_ORDER = [
  "school_name",
  "major_name",
  "batch",
  "subject_category",
  "admission_program",
  "selection_requirements",
  "min_score",
  "min_rank",
  "candidate_score",
  "candidate_rank",
  "score_gap",
  "rank_gap",
  "confidence_band",
  "tuition",
  "city",
  "ownership",
];

function formatCell(value: unknown, column?: string): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (column === "is_double_first_class") {
    return value ? "是" : "否";
  }
  if (column === "cumulative_ratio" && typeof value === "number") {
    return `${value}%`;
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  if (column === "confidence_band") {
    return formatConfidenceBand(String(value));
  }
  return String(value);
}

function formatColumnLabel(column: string): string {
  return COLUMN_LABELS[column] ?? humanizeColumn(column);
}

function humanizeColumn(column: string): string {
  return column.replace(/_/g, " ");
}

function compareColumns(a: string, b: string): number {
  const aIndex = COLUMN_ORDER.indexOf(a);
  const bIndex = COLUMN_ORDER.indexOf(b);
  if (aIndex !== -1 || bIndex !== -1) {
    if (aIndex === -1) {
      return 1;
    }
    if (bIndex === -1) {
      return -1;
    }
    return aIndex - bIndex;
  }
  return a.localeCompare(b, "zh-CN");
}

function formatConfidenceBand(value: string): string {
  if (value === "冲") {
    return "冲刺";
  }
  if (value === "稳") {
    return "稳妥";
  }
  if (value === "保") {
    return "保底";
  }
  return value;
}

function formatTemplateName(value: string | null): string {
  if (!value) {
    return "自然语言查询";
  }
  const mapping: Record<string, string> = {
    admission_search_lookup: "录取检索",
    semantic_admission_search: "录取检索",
    admission_feasibility_lookup: "录取可行性评估",
    semantic_admission_feasibility: "录取可行性评估",
    score_rank_filter: "分数位次筛选",
    multi_filter_lookup: "组合条件筛选",
    school_detail: "院校详情查询",
    major_lookup: "专业查询",
    region_school_lookup: "地区院校查询",
    selection_requirement_lookup: "选科要求查询",
  };
  return mapping[value] ?? value;
}

function formatAdmissionCitation(item: {
  label: string;
  source: string;
  fields: string[];
  exam_province: string;
  plan_year: number;
  note: string;
}) {
  const source = formatDataSource(item.source);
  const fields = item.fields.length
    ? `，涉及字段：${item.fields.map(formatColumnLabel).join("、")}`
    : "";
  const note = item.note ? `，说明：${item.note}` : "";
  return `${item.label}，数据来源：${source}，范围：${item.exam_province} ${item.plan_year}${fields}${note}`;
}

function formatDataSource(source: string): string {
  const mapping: Record<string, string> = {
    "staging.admission_records": "投档录取数据",
    "staging.score_segments": "一分一段数据",
    school: "院校主数据",
    province: "省份主数据",
  };
  return mapping[source] ?? source;
}

function formatSource(item: { page_number: number | null; page_side: string | null; similarity?: number }) {
  const page = item.page_number ? `第 ${item.page_number} 页` : "页码未知";
  const side = item.page_side ? ` ${item.page_side}` : "";
  const score = typeof item.similarity === "number" ? ` 相似度 ${item.similarity.toFixed(3)}` : "";
  return `${page}${side}${score}`;
}

function formatCitation(item: {
  title: string;
  page_number: number | null;
  page_side: string | null;
  source_url: string | null;
}) {
  const source = item.source_url ? ` ${item.source_url}` : "";
  return `${item.title} ${formatSource(item)}${source}`;
}

createRoot(document.getElementById("root")!).render(<App />);
