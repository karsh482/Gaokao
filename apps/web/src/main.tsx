import { FormEvent, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  BookOpenText,
  Database,
  FileText,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Table2,
  Trash2,
} from "lucide-react";
import {
  ChatMessage,
  PolicyQueryResponse,
  QueryResponse,
  queryAdmission,
  queryPolicy,
} from "./api";
import "./styles.css";

type Mode = "admission" | "policy";

type AdmissionChatMessage = ChatMessage & {
  id: string;
  result?: QueryResponse;
};

type AdmissionConversation = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  examProvince: string;
  planYear: number;
  messages: AdmissionChatMessage[];
};

type AdmissionChatState = {
  conversations: AdmissionConversation[];
  activeConversationId: string;
};

const DEFAULT_EXAM_PROVINCE = "贵州";
const DEFAULT_PLAN_YEAR = 2026;
const DEFAULT_CONVERSATION_TITLE = "新对话";
const MAX_ADMISSION_CONVERSATIONS = 30;
const ADMISSION_CONVERSATIONS_STORAGE_KEY = "gaokaoAdmissionConversations";
const ADMISSION_ACTIVE_CONVERSATION_STORAGE_KEY = "gaokaoAdmissionActiveConversation";
const ADMISSION_PROMPTS = [
  "贵州物理类 位次10000 能不能上贵州大学？",
  "580分可以报哪些公办计算机专业？",
  "贵州大学法学近年录取位次怎么样？",
  "历史类 12000 位次有什么稳妥选择？",
];

function App() {
  const [mode, setMode] = useState<Mode>("admission");
  const [admissionChatState, setAdmissionChatState] = useState(loadAdmissionChatState);
  const [apiKey, setApiKey] = useState(localStorage.getItem("gaokaoApiKey") ?? "");
  const [gpuRentApiKey, setGpuRentApiKey] = useState(
    localStorage.getItem("gaokaoGpuRentApiKey") ?? "",
  );
  const activeAdmissionConversation = useMemo(
    () =>
      admissionChatState.conversations.find(
        (conversation) => conversation.id === admissionChatState.activeConversationId,
      ) ?? admissionChatState.conversations[0],
    [admissionChatState],
  );

  useEffect(() => {
    try {
      localStorage.setItem(
        ADMISSION_CONVERSATIONS_STORAGE_KEY,
        JSON.stringify(admissionChatState.conversations.slice(0, MAX_ADMISSION_CONVERSATIONS)),
      );
      localStorage.setItem(
        ADMISSION_ACTIVE_CONVERSATION_STORAGE_KEY,
        admissionChatState.activeConversationId,
      );
    } catch {
      // Ignore localStorage quota or privacy-mode failures; the active chat can still continue.
    }
  }, [admissionChatState]);

  function updateApiKey(value: string) {
    setApiKey(value);
    localStorage.setItem("gaokaoApiKey", value);
  }

  function updateGpuRentApiKey(value: string) {
    setGpuRentApiKey(value);
    localStorage.setItem("gaokaoGpuRentApiKey", value);
  }

  function startNewAdmissionConversation() {
    const conversation = createAdmissionConversation();
    setAdmissionChatState((current) => {
      const active = current.conversations.find(
        (item) => item.id === current.activeConversationId,
      );
      if (active && active.messages.length === 0 && active.title === DEFAULT_CONVERSATION_TITLE) {
        return { ...current, activeConversationId: active.id };
      }
      return {
        activeConversationId: conversation.id,
        conversations: [conversation, ...current.conversations].slice(0, MAX_ADMISSION_CONVERSATIONS),
      };
    });
  }

  function selectAdmissionConversation(conversationId: string) {
    setAdmissionChatState((current) => ({ ...current, activeConversationId: conversationId }));
  }

  function deleteAdmissionConversation(conversationId: string) {
    setAdmissionChatState((current) => {
      const conversations = current.conversations.filter(
        (conversation) => conversation.id !== conversationId,
      );
      if (conversations.length === current.conversations.length) {
        return current;
      }
      if (!conversations.length) {
        const conversation = createAdmissionConversation();
        return {
          activeConversationId: conversation.id,
          conversations: [conversation],
        };
      }
      return {
        activeConversationId:
          current.activeConversationId === conversationId
            ? conversations[0].id
            : current.activeConversationId,
        conversations,
      };
    });
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

        {mode === "admission" && (
          <AdmissionConversationNav
            activeConversationId={activeAdmissionConversation?.id}
            conversations={admissionChatState.conversations}
            onNewConversation={startNewAdmissionConversation}
            onDeleteConversation={deleteAdmissionConversation}
            onSelectConversation={selectAdmissionConversation}
          />
        )}

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

        <label className="field">
          <span>
            <Settings size={15} />
            ai-gpurent Key
          </span>
          <input
            value={gpuRentApiKey}
            onChange={(event) => updateGpuRentApiKey(event.target.value)}
            placeholder="用于 LLM token 计费"
            type="password"
          />
        </label>
      </aside>

      <section className="workspace">
        {mode === "admission" ? (
          <AdmissionPanel
            activeConversation={activeAdmissionConversation}
            apiKey={apiKey}
            gpuRentApiKey={gpuRentApiKey}
            onNewConversation={startNewAdmissionConversation}
            setChatState={setAdmissionChatState}
          />
        ) : (
          <PolicyPanel apiKey={apiKey} gpuRentApiKey={gpuRentApiKey} />
        )}
      </section>
    </main>
  );
}

function AdmissionConversationNav({
  activeConversationId,
  conversations,
  onNewConversation,
  onDeleteConversation,
  onSelectConversation,
}: {
  activeConversationId?: string;
  conversations: AdmissionConversation[];
  onNewConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
  onSelectConversation: (conversationId: string) => void;
}) {
  return (
    <section className="sidebarHistory" aria-label="录取查询历史对话">
      <button className="newConversationButton" onClick={onNewConversation} type="button">
        <Plus size={17} />
        新对话
      </button>
      <div className="sidebarHistoryTitle">历史对话</div>
      <div className="sidebarConversationList">
        {conversations.map((conversation) => (
          <div
            className={
              conversation.id === activeConversationId
                ? "sidebarConversationItem active"
                : "sidebarConversationItem"
            }
            key={conversation.id}
          >
            <button
              className="sidebarConversationSelect"
              onClick={() => onSelectConversation(conversation.id)}
              type="button"
            >
              <MessageSquare size={15} />
              <span>{conversation.title}</span>
              <small>{formatConversationTime(conversation.updatedAt)}</small>
            </button>
            <button
              aria-label={`删除对话：${conversation.title}`}
              className="sidebarConversationDelete"
              onClick={() => onDeleteConversation(conversation.id)}
              title="删除对话"
              type="button"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdmissionPanel({
  activeConversation,
  apiKey,
  gpuRentApiKey,
  onNewConversation,
  setChatState,
}: {
  activeConversation?: AdmissionConversation;
  apiKey: string;
  gpuRentApiKey: string;
  onNewConversation: () => void;
  setChatState: React.Dispatch<React.SetStateAction<AdmissionChatState>>;
}) {
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [pendingConversationId, setPendingConversationId] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const messages = activeConversation?.messages ?? [];
  const loading = pendingConversationId !== null;
  const activeConversationLoading = pendingConversationId === activeConversation?.id;

  useEffect(() => {
    const list = messageListRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, [activeConversation?.id, activeConversationLoading, messages.length]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  }, [question]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || !activeConversation || pendingConversationId) {
      return;
    }
    const conversationId = activeConversation.id;
    const userMessage: AdmissionChatMessage = {
      id: createMessageId(),
      role: "user",
      content: trimmedQuestion,
    };
    const history = toQueryHistory(messages);
    setChatState((current) =>
      patchAdmissionConversation(current, conversationId, (conversation) => ({
        ...conversation,
        title: getNextConversationTitle(conversation, trimmedQuestion),
        updatedAt: Date.now(),
        messages: [...conversation.messages, userMessage],
      })),
    );
    setQuestion("");
    setPendingConversationId(conversationId);
    setError("");
    try {
      const response = await queryAdmission(
        {
          question: trimmedQuestion,
          exam_province: DEFAULT_EXAM_PROVINCE,
          plan_year: resolveAdmissionPlanYear(trimmedQuestion),
          history,
        },
        apiKey,
        gpuRentApiKey,
      );
      setChatState((current) =>
        patchAdmissionConversation(current, conversationId, (conversation) => ({
          ...conversation,
          updatedAt: Date.now(),
          messages: [
            ...conversation.messages,
            {
              id: createMessageId(),
              role: "assistant",
              content: response.answer || response.summary || "暂无可展示答案。",
              result: response,
            },
          ],
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPendingConversationId(null);
    }
  }

  function startNewConversation() {
    onNewConversation();
    setError("");
    setQuestion("");
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function usePrompt(prompt: string) {
    setQuestion(prompt);
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  return (
    <div className="page admissionPage">
      <section className={messages.length === 0 ? "chatPanel emptyChat" : "chatPanel"}>
        <div className="messageList" ref={messageListRef}>
          {messages.length === 0 ? (
            <div className="assistantEmptyState">
              <div className="assistantMark">
                <Sparkles size={24} />
              </div>
              <h2>2026高考志愿AI智能助手</h2>
              <form className="chatComposer centerComposer" onSubmit={submit} ref={formRef}>
                <textarea
                  aria-label="输入志愿咨询问题"
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder="询问分数、位次、院校、专业或志愿梯度"
                  ref={textareaRef}
                  rows={2}
                  value={question}
                />
                <button disabled={loading || !question.trim()} title="发送" type="submit">
                  {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
                </button>
              </form>
              <div className="promptGrid">
                {ADMISSION_PROMPTS.map((prompt) => (
                  <button key={prompt} onClick={() => usePrompt(prompt)} type="button">
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <ChatBubble message={message} key={message.id} />
            ))
          )}
          {activeConversationLoading && (
            <div className="chatMessage assistant loadingMessage">
              <div className="messageAvatar">AI</div>
              <div className="messageBody inlineStatus">
                <Loader2 className="spin" size={18} />
                <span>正在查询...</span>
              </div>
            </div>
          )}
        </div>

        {messages.length > 0 && (
          <div className="composerDock">
            {error && <ErrorMessage message={error} />}
            <form className="chatComposer" onSubmit={submit} ref={formRef}>
              <textarea
                aria-label="输入志愿咨询问题"
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="询问分数、位次、院校、专业或志愿梯度"
                ref={textareaRef}
                rows={2}
                value={question}
              />
              <button disabled={loading || !question.trim()} title="发送" type="submit">
                {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              </button>
            </form>
          </div>
        )}

        {messages.length === 0 && error && (
          <div className="emptyErrorDock">
            <ErrorMessage message={error} />
          </div>
        )}

        <footer className="chatFooter">
          <div className="scopeFields scopeSummary" aria-label="查询范围">
            <div className="scopeBadge">
              <span>考试省份</span>
              <strong>{DEFAULT_EXAM_PROVINCE}</strong>
            </div>
          </div>
        </footer>
      </section>
    </div>
  );
}

function ChatBubble({ message }: { message: AdmissionChatMessage }) {
  return (
    <article className={`chatMessage ${message.role}`}>
      <div className="messageAvatar">{message.role === "user" ? "我" : "AI"}</div>
      <div className="messageBody">
        <p>{message.content}</p>
        {message.result && <AdmissionResult result={message.result} compact />}
      </div>
    </article>
  );
}

function PolicyPanel({
  apiKey,
  gpuRentApiKey,
}: {
  apiKey: string;
  gpuRentApiKey: string;
}) {
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
          gpuRentApiKey,
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

function AdmissionResult({ result, compact = false }: { result: QueryResponse; compact?: boolean }) {
  return (
    <div className={compact ? "resultStack compact" : "resultStack"}>
      {!compact && <AnswerBlock answer={result.answer} summary={result.summary} />}
      <MetaStrip
        items={[
          ["记录数", String(result.row_count)],
          ["省份", result.exam_province],
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
      Object.keys(row).forEach((key) => {
        if (!HIDDEN_RESULT_COLUMNS.has(key)) {
          names.add(key);
        }
      });
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

function loadAdmissionChatState(): AdmissionChatState {
  const fallbackConversation = createAdmissionConversation();
  try {
    const rawConversations = localStorage.getItem(ADMISSION_CONVERSATIONS_STORAGE_KEY);
    const activeConversationId = localStorage.getItem(ADMISSION_ACTIVE_CONVERSATION_STORAGE_KEY);
    const parsed = rawConversations ? JSON.parse(rawConversations) : null;
    const conversations = Array.isArray(parsed)
      ? parsed.map(normalizeAdmissionConversation).filter((item): item is AdmissionConversation => item !== null)
      : [];
    if (!conversations.length) {
      return {
        activeConversationId: fallbackConversation.id,
        conversations: [fallbackConversation],
      };
    }
    const sortedConversations = conversations
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_ADMISSION_CONVERSATIONS);
    return {
      activeConversationId:
        activeConversationId && sortedConversations.some((item) => item.id === activeConversationId)
          ? activeConversationId
          : sortedConversations[0].id,
      conversations: sortedConversations,
    };
  } catch {
    return {
      activeConversationId: fallbackConversation.id,
      conversations: [fallbackConversation],
    };
  }
}

function normalizeAdmissionConversation(value: unknown): AdmissionConversation | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const item = value as Partial<AdmissionConversation>;
  if (typeof item.id !== "string") {
    return null;
  }
  const createdAt = typeof item.createdAt === "number" ? item.createdAt : Date.now();
  const updatedAt = typeof item.updatedAt === "number" ? item.updatedAt : createdAt;
  return {
    id: item.id,
    title: typeof item.title === "string" && item.title.trim() ? item.title : DEFAULT_CONVERSATION_TITLE,
    createdAt,
    updatedAt,
    examProvince:
      typeof item.examProvince === "string" && item.examProvince.trim()
        ? item.examProvince
        : DEFAULT_EXAM_PROVINCE,
    planYear: DEFAULT_PLAN_YEAR,
    messages: Array.isArray(item.messages)
      ? item.messages
          .map(normalizeAdmissionMessage)
          .filter((message): message is AdmissionChatMessage => message !== null)
      : [],
  };
}

function normalizeAdmissionMessage(value: unknown): AdmissionChatMessage | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const item = value as Partial<AdmissionChatMessage>;
  if ((item.role !== "user" && item.role !== "assistant") || typeof item.content !== "string") {
    return null;
  }
  return {
    id: typeof item.id === "string" ? item.id : createMessageId(),
    role: item.role,
    content: item.content,
    result: item.result,
  };
}

function createAdmissionConversation(): AdmissionConversation {
  const now = Date.now();
  return {
    id: createMessageId(),
    title: DEFAULT_CONVERSATION_TITLE,
    createdAt: now,
    updatedAt: now,
    examProvince: DEFAULT_EXAM_PROVINCE,
    planYear: DEFAULT_PLAN_YEAR,
    messages: [],
  };
}

function resolveAdmissionPlanYear(question: string): number | undefined {
  if (isProgramCatalogQuestion(question)) {
    return DEFAULT_PLAN_YEAR;
  }
  return undefined;
}

function isProgramCatalogQuestion(question: string): boolean {
  return [
    "招生计划",
    "计划人数",
    "计划招生",
    "招生人数",
    "招生名额",
    "招收人数",
    "招多少",
    "招几人",
    "招几个人",
    "招几个",
    "招几名",
    "招聘人数",
    "专业目录",
    "开设哪些专业",
    "开设什么专业",
    "有哪些专业",
    "专业有哪些",
    "招收哪些专业",
    "招哪些专业",
    "招什么专业",
    "选科要求",
    "科目要求",
    "学费",
    "学制",
  ].some((keyword) => question.includes(keyword));
}

function patchAdmissionConversation(
  state: AdmissionChatState,
  conversationId: string,
  update: (conversation: AdmissionConversation) => AdmissionConversation,
): AdmissionChatState {
  const conversations = state.conversations.map((conversation) =>
    conversation.id === conversationId ? update(conversation) : conversation,
  );
  return {
    ...state,
    conversations: conversations.sort((a, b) => b.updatedAt - a.updatedAt),
  };
}

function getNextConversationTitle(conversation: AdmissionConversation, question: string): string {
  if (conversation.title !== DEFAULT_CONVERSATION_TITLE || conversation.messages.length > 0) {
    return conversation.title;
  }
  return question.length > 22 ? `${question.slice(0, 22)}...` : question;
}

function formatConversationTime(timestamp: number): string {
  const date = new Date(timestamp);
  const today = new Date();
  const isSameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();
  if (isSameDay) {
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
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
  enrollment_type: "招生类型",
  admission_program: "专项计划",
  selection_requirements: "选科要求",
  enrollment_plan_count: "招生计划数",
  plan_count_2025: "2025计划数",
  plan_count_2026: "2026计划数",
  plan_count_change: "计划变化",
  change_type: "变化类型",
  record_count_2025: "2025匹配记录数",
  record_count_2026: "2026匹配记录数",
  comparison_note: "对比口径",
  filing_count: "投档人数",
  admitted_count: "录取人数",
  min_score: "最低分",
  min_rank: "最低位次",
  tuition: "学费",
  duration: "学制",
  source_page: "来源页码",
  source_file_name: "来源文件",
  language: "外语语种要求",
  remarks: "备注",
  school_location: "院校所在地",
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

const HIDDEN_RESULT_COLUMNS = new Set([
  "source_school_name",
  "school_code_in_exam_province",
  "major_code_in_exam_province",
  "admission_track",
  "language",
  "remarks",
  "school_location",
  "source_file_id",
  "source_file_name",
  "source_page",
  "source_column",
  "source_line_start",
  "source_line_end",
  "extraction_method",
  "confidence",
  "matched_record_count",
  "matched_enrollment_plan_count",
  "exam_province",
  "plan_year",
]);

const COLUMN_ORDER = [
  "school_name",
  "major_name",
  "batch",
  "subject_category",
  "enrollment_type",
  "admission_program",
  "selection_requirements",
  "enrollment_plan_count",
  "plan_count_2025",
  "plan_count_2026",
  "plan_count_change",
  "change_type",
  "duration",
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
    program_catalog_lookup: "招生计划查询",
    program_plan_change_lookup: "招生计划变化对比",
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
  return `${item.label}，数据来源：${source}，范围：${item.exam_province}${fields}${note}`;
}

function formatDataSource(source: string): string {
  const mapping: Record<string, string> = {
    "staging.admission_records": "投档录取数据",
    "staging.score_segments": "一分一段数据",
    "staging.program_catalog_records": "招生专业目录/招生计划数据",
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

function toQueryHistory(messages: AdmissionChatMessage[]): ChatMessage[] {
  return messages
    .map((message) => ({
      role: message.role,
      content: message.content,
    }))
    .slice(-8);
}

function createMessageId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

createRoot(document.getElementById("root")!).render(<App />);
