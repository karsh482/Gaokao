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

const admissionExamples = [
  "贵州物理类 9500名，能上哪些大学？",
  "贵州物理类 位次10000 能不能上贵州大学？",
  "贵州物理类 580分，可以报哪些学校？",
  "贵州历史类 12000名，有哪些稳一点的学校？",
];

const policyExamples = [
  "北京大学基础医学有哪些二级学科研究方向？",
  "北京大学本科招生章程里对录取规则怎么说明？",
  "北京大学招生简章里元培学院有什么特点？",
];

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
  const [question, setQuestion] = useState(admissionExamples[0]);
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
      <QueryHeader
        title="录取查询"
        description="用自然语言查询投档录取数据，系统会返回答案、明细和 SQL。"
      />
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
      <ExampleBar examples={admissionExamples} onPick={setQuestion} />
      {error && <ErrorMessage message={error} />}
      {result && <AdmissionResult result={result} />}
    </div>
  );
}

function PolicyPanel({ apiKey }: { apiKey: string }) {
  const [question, setQuestion] = useState(policyExamples[0]);
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
      <QueryHeader
        title="政策问答"
        description="检索招生章程、政策文档和本地 RAG 知识库。"
      />
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
      <ExampleBar examples={policyExamples} onPick={setQuestion} />
      {error && <ErrorMessage message={error} />}
      {result && <PolicyResultView result={result} />}
    </div>
  );
}

function QueryHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="queryHeader">
      <h2>{title}</h2>
      <p>{description}</p>
    </header>
  );
}

function ExampleBar({
  examples,
  onPick,
}: {
  examples: string[];
  onPick: (example: string) => void;
}) {
  return (
    <div className="examples">
      {examples.map((example) => (
        <button key={example} onClick={() => onPick(example)} type="button">
          {example}
        </button>
      ))}
    </div>
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
          ["模板", result.template_name ?? "LLM SQL"],
        ]}
      />
      <DataTable rows={result.rows} />
      <Details title="口径说明" icon={<FileText size={17} />}>
        <List values={result.notes} />
      </Details>
      <Details title="引用来源" icon={<BookOpenText size={17} />}>
        <List values={result.citations.map((item) => `${item.label} (${item.source})`)} />
      </Details>
      <Details title="SQL" icon={<Database size={17} />}>
        <pre>{result.sql ?? "未执行 SQL"}</pre>
      </Details>
      <Details title="完整响应" icon={<Table2 size={17} />}>
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
    return Array.from(names);
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
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{formatCell(row[column])}</td>
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

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
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
