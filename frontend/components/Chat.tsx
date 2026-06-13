"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { createSession, clearSession, streamChat } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { Message, RetrievalInfo } from "@/lib/types";

function friendlyError(err: unknown, arabic: boolean): string {
  if (!(err instanceof Error))
    return arabic ? "حدث خطأ. حاول مرة أخرى." : "Something went wrong. Please try again.";
  if (err.name === "AbortError") return "";
  if (err.message.includes("429"))
    return arabic ? "عدد الطلبات كبير. انتظر قليلًا قبل طرح سؤال آخر." : "Too many requests. Please wait a moment before asking again.";
  if (err.message.includes("401") || err.message.includes("403"))
    return arabic ? "تعذر التحقق من الهوية. حدّث الصفحة." : "Authentication error. Please refresh the page.";
  if (err.message.includes("500"))
    return arabic ? "حدث خطأ في الخادم. حاول مرة أخرى بعد قليل." : "Server error. Please try again in a moment.";
  if (
    err.message.includes("Failed to fetch") ||
    err.message.includes("NetworkError")
  )
    return arabic ? "تعذر الوصول إلى الخادم. تحقق من الاتصال." : "Could not reach the server. Check your connection.";
  return arabic ? `خطأ: ${err.message}` : `Error: ${err.message}`;
}

function containsArabic(value: string): boolean {
  return /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/.test(value);
}

// ── Retrieval Panel ─────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score > 0.7 ? "#00c9a7" : score > 0.5 ? "#ffd93d" : "#ff6b6b";
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-20 h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--border)" }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>
        {score.toFixed(2)} / 1.00
      </span>
    </div>
  );
}

function RetrievalPanel({ info }: { info: RetrievalInfo }) {
  const [open, setOpen] = useState(false);
  const dc = info.decomposed ?? {};
  const filters = dc.filters ?? {};
  const hitCount = info.semantic_hits?.length ?? 0;

  return (
    <div className="chat-retrieval">
      <button
        onClick={() => setOpen((o) => !o)}
        className="chat-retrieval__trigger"
      >
        <span>
          <span className="font-semibold">Retrieval process</span>
          <span className="ml-2" style={{ color: "var(--accent)" }}>
            {info.layers_used?.join(", ")}
          </span>
          {hitCount > 0 && (
            <span className="ml-2">{hitCount} semantic hits</span>
          )}
        </span>
        <span aria-hidden>{open ? "Close" : "Open"}</span>
      </button>

      {open && (
        <div
          className="p-3 space-y-3"
          style={{
            background: "var(--bg-alt)",
            borderTop: "1px solid var(--border)",
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div
                className="font-semibold mb-1.5"
                style={{ color: "var(--text)" }}
              >
                Query decomposition
              </div>
              <div className="space-y-1" style={{ color: "var(--muted)" }}>
                <div>
                  Aggregation needed:
                  <span
                    className={`ml-1 font-semibold ${info.needs_agg ? "text-yellow-400" : "text-green-400"}`}
                  >
                    {info.needs_agg ? "Yes" : "No"}
                  </span>
                </div>
                {Object.keys(filters).length > 0 && (
                  <div>
                    Filters:{" "}
                    <span className="text-purple-400">
                      {JSON.stringify(filters)}
                    </span>
                  </div>
                )}
                {dc.analysis_types?.length > 0 && (
                  <div>
                    Analysis:{" "}
                    <span className="text-blue-400">
                      {dc.analysis_types.join(", ")}
                    </span>
                  </div>
                )}
                {dc.resolved_question &&
                  dc.resolved_question !== dc.semantic_query && (
                    <div
                      className="mt-1 italic"
                      style={{ color: "var(--muted)" }}
                    >
                      Resolved: {dc.resolved_question.slice(0, 120)}
                    </div>
                  )}
              </div>
            </div>
            <div>
              <div
                className="font-semibold mb-1.5"
                style={{ color: "var(--text)" }}
              >
                Layers used
              </div>
              <div className="space-y-1">
                {(info.layers_used ?? []).map((l) => (
                  <div key={l} className="flex items-center gap-1.5">
                    <span style={{ color: "var(--muted)" }}>{l}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {info.semantic_hits?.length > 0 && (
            <div>
              <div
                className="font-semibold mb-1.5"
                style={{ color: "var(--text)" }}
              >
                Top {info.semantic_hits.length} semantic matches
              </div>
              <div className="space-y-1.5">
                {info.semantic_hits.map((h, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 py-1 border-b"
                    style={{ borderColor: "var(--code-bg)" }}
                  >
                    <ScoreBar score={h.score} />
                    <div className="flex-1 min-w-0">
                      <span
                        className="font-semibold truncate block"
                        style={{ color: "var(--text)" }}
                      >
                        {h.title}
                      </span>
                      <span style={{ color: "var(--muted)" }}>
                        {[h.company, h.country, h.timeline]
                          .filter(Boolean)
                          .join(", ")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {info.sql_snippet && (
            <div>
              <div
                className="font-semibold mb-1"
                style={{ color: "var(--text)" }}
              >
                SQL / Pandas result (preview)
              </div>
              <pre
                className="overflow-x-auto p-2 rounded text-xs leading-relaxed"
                style={{
                  background: "var(--card)",
                  color: "var(--muted)",
                  border: "1px solid var(--border)",
                }}
              >
                {info.sql_snippet}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Markdown renderer — safe, no dangerouslySetInnerHTML ─────────────────────

function BotMessage({
  content,
  streaming,
}: {
  content: string;
  streaming?: boolean;
}) {
  return (
    <div
      className="text-sm leading-relaxed"
      dir="auto"
      lang={containsArabic(content) ? "ar" : undefined}
      style={{ color: "var(--text)" }}
    >
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc list-inside mb-2 space-y-0.5">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside mb-2 space-y-0.5">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li style={{ color: "var(--text)" }}>{children}</li>
          ),
          strong: ({ children }) => (
            <strong style={{ color: "var(--text)" }}>{children}</strong>
          ),
          em: ({ children }) => (
            <em style={{ color: "var(--accent)" }}>{children}</em>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes("language-");
            return isBlock ? (
              <pre
                className="overflow-x-auto p-3 rounded my-2 text-xs"
                style={{
                  background: "var(--bg-alt)",
                  border: "1px solid var(--border)",
                  color: "var(--muted)",
                }}
              >
                <code>{children}</code>
              </pre>
            ) : (
              <code
                className="px-1 py-0.5 rounded text-xs"
                style={{ background: "var(--card-alt)", color: "#f97316" }}
              >
                {children}
              </code>
            );
          },
          h1: ({ children }) => (
            <h1
              className="text-base font-bold mb-2 mt-3"
              style={{ color: "var(--text)" }}
            >
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2
              className="text-sm font-bold mb-1.5 mt-3"
              style={{ color: "var(--text)" }}
            >
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3
              className="text-xs font-bold mb-1 mt-2"
              style={{ color: "var(--text)" }}
            >
              {children}
            </h3>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className="border-l-2 pl-3 my-2 italic"
              style={{ borderColor: "var(--accent)", color: "var(--muted)" }}
            >
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2">
              <table
                className="text-xs w-full border-collapse"
                style={{ borderColor: "var(--border)" }}
              >
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th
              className="px-2 py-1 text-left font-semibold border"
              style={{
                borderColor: "var(--border)",
                background: "var(--card-alt)",
                color: "var(--text)",
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              className="px-2 py-1 border"
              style={{ borderColor: "var(--border)", color: "var(--muted)" }}
            >
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
      {streaming && <span className="chat-stream-caret" />}
    </div>
  );
}

function ResponsePending({
  arabic,
  datasetCount,
  evidenceFound,
}: {
  arabic: boolean;
  datasetCount: number;
  evidenceFound: boolean;
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setElapsedSeconds((current) => current + 1);
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  const title = evidenceFound
    ? arabic
      ? "تم العثور على الأدلة"
      : "Evidence found"
    : arabic
      ? "جارٍ البحث في البيانات المحددة"
      : "Searching selected data";
  const description = evidenceFound
    ? arabic
      ? "جارٍ إعداد إجابة مستندة إلى أفضل النتائج."
      : "Preparing a grounded response from the strongest matches."
    : elapsedSeconds >= 10
      ? arabic
        ? "ما زلنا نراجع الأدلة. يستغرق هذا وقتًا أطول من المعتاد."
        : "Still reviewing the evidence. This is taking longer than usual."
      : elapsedSeconds >= 4
        ? arabic
          ? "جارٍ مراجعة أفضل النتائج قبل الإجابة."
          : "Reviewing the strongest matches before answering."
        : arabic
          ? "جارٍ العثور على الوظائف وإشارات السوق ذات الصلة."
          : "Finding relevant postings and market signals.";

  return (
    <div className="chat-message-row">
      <div
        className="chat-waiting"
        dir={arabic ? "rtl" : "ltr"}
        lang={arabic ? "ar" : "en"}
        role="status"
        aria-live="polite"
      >
        <div className="chat-waiting__header">
          <div>
            <p className="chat-waiting__title">{title}</p>
            <p className="chat-waiting__description">{description}</p>
          </div>
          <span className="chat-waiting__elapsed" aria-hidden="true">
            {elapsedSeconds}s
          </span>
        </div>
        <div className="chat-waiting__trace" aria-hidden="true">
          <span />
        </div>
        <div className="chat-waiting__meta" aria-hidden="true">
          <span>
            {arabic
              ? `${datasetCount || "كل"} مصادر بيانات`
              : `${datasetCount || "All"} datasets`}
          </span>
          <span>
            {evidenceFound
              ? arabic
                ? "جارٍ صياغة الإجابة"
                : "Composing answer"
              : arabic
                ? "جارٍ استرجاع الأدلة"
                : "Retrieving evidence"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Main Chat ────────────────────────────────────────────────────────────────

interface MessageWithId extends Message {
  id: string;
}

interface Props {
  selectedDumps: string[];
  model: string;
}

export default function Chat({ selectedDumps, model }: Props) {
  const { lang, dir } = useLanguage();
  const arabic = lang === "ar";
  const [sessionId, setSessionId] = useState<string>("");
  const [sessionError, setSessionError] = useState<string>("");
  const [messages, setMessages] = useState<MessageWithId[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [searching, setSearching] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messageIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    createSession()
      .then((id) => {
        if (!cancelled) setSessionId(id);
      })
      .catch(() => {
        if (!cancelled) {
          const currentArabic = document.documentElement.lang === "ar";
          setSessionError(currentArabic ? "تعذر الاتصال بالخادم. حدّث الصفحة." : "Could not connect to server. Please refresh the page.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: streaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, searching, streaming]);

  function makeId() {
    messageIdRef.current += 1;
    return `message-${messageIdRef.current}`;
  }

  function stopStreaming() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setSearching(false);
    setMessages((prev) => {
      const copy = [...prev];
      if (copy.length && copy[copy.length - 1].streaming) {
        copy[copy.length - 1] = { ...copy[copy.length - 1], streaming: false };
      }
      return copy;
    });
  }

  async function send(question: string) {
    if (!question.trim()) return;
    if (!sessionId) {
      setSessionError(arabic ? "لا يوجد اتصال بالخادم. حدّث الصفحة." : "Not connected to server. Please refresh the page.");
      return;
    }
    if (streaming) stopStreaming();

    setInput("");
    setTimeout(() => inputRef.current?.focus(), 0);

    const userMsg: MessageWithId = {
      id: makeId(),
      role: "user",
      content: question,
    };
    const asstMsg: MessageWithId = {
      id: makeId(),
      role: "assistant",
      content: "",
      streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, asstMsg]);
    setStreaming(true);
    setSearching(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const event of streamChat(
        question,
        sessionId,
        model,
        selectedDumps,
        controller.signal,
      )) {
        if (event.type === "retrieval") {
          setSearching(false);
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = {
              ...copy[copy.length - 1],
              retrieval: event.info,
            };
            return copy;
          });
        } else if (event.type === "token") {
          setSearching(false);
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = {
              ...copy[copy.length - 1],
              content: copy[copy.length - 1].content + event.token,
            };
            return copy;
          });
        }
      }
    } catch (e: unknown) {
      setSearching(false);
      const msg = friendlyError(e, arabic);
      if (msg) {
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            ...copy[copy.length - 1],
            content: msg,
            streaming: false,
          };
          return copy;
        });
      }
    } finally {
      abortRef.current = null;
      setSearching(false);
      setMessages((prev) => {
        const copy = [...prev];
        if (copy.length && copy[copy.length - 1].streaming) {
          copy[copy.length - 1] = {
            ...copy[copy.length - 1],
            streaming: false,
          };
        }
        return copy;
      });
      setStreaming(false);
    }
  }

  async function handleClear() {
    if (streaming) stopStreaming();
    if (sessionId) await clearSession(sessionId);
    setMessages([]);
  }

  if (sessionError) {
    return (
      <div className="app-state" dir={dir} lang={lang}>
        <div className="space-y-3">
          <div className="app-state__title">{sessionError}</div>
          <button
            onClick={() => {
              setSessionError("");
              createSession()
                .then(setSessionId)
                .catch(() =>
                  setSessionError(
                    arabic ? "ما زال الاتصال متعذرًا. تحقق من تشغيل الخادم." : "Still cannot connect. Check if the server is running.",
                  ),
                );
            }}
            className="app-secondary-button focus-ring"
          >
            {arabic ? "إعادة الاتصال" : "Retry connection"}
          </button>
        </div>
      </div>
    );
  }

  const latestMessage = messages[messages.length - 1];
  const waitingForFirstToken = Boolean(
    streaming && latestMessage?.role === "assistant" && !latestMessage.content,
  );
  const latestQuestion =
    [...messages].reverse().find((message) => message.role === "user")
      ?.content ?? "";
  const pendingInArabic = containsArabic(latestQuestion);

  return (
    <div className="chat-workspace" dir={dir} lang={lang}>
      {/* Header */}
      <div className="chat-workspace__header">
        <div>
          <h1>{arabic ? "اسأل عن سوق العمل" : "Ask the market"}</h1>
          <p>
            {selectedDumps.length
              ? arabic ? `${selectedDumps.length} مجموعات بيانات محددة` : `${selectedDumps.length} datasets selected`
              : arabic ? "جميع البيانات" : "All data"}
            {model && (
              <>
                {arabic ? "، " : ", "}
                <bdi dir="ltr">{model.split("/").pop()}</bdi>
              </>
            )}
            {!sessionId ? arabic ? "، جارٍ الاتصال" : ", connecting" : ""}
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleClear}
            className="app-secondary-button focus-ring"
          >
            {arabic ? "مسح المحادثة" : "Clear chat"}
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <h2>{arabic ? "ابدأ بسؤال بحثي." : "Start with a research question."}</h2>
            <p>
              {arabic ? "اسأل عن الوظائف أو المهارات أو الرواتب أو جهات التوظيف أو القطاعات أو التغيرات بمرور الوقت." : "Ask about roles, skills, salaries, employers, sectors, or change over time."}
            </p>
            <div className="chat-empty__prompts">
              {(arabic ? [
                "ما المهارات الأكثر طلبًا في وظائف البيانات؟",
                "قارن الطلب على التوظيف بين الدول المحددة.",
                "ما بيانات الرواتب المتاحة للوظائف العليا؟",
              ] : [
                "Which skills appear most often in data roles?",
                "Compare hiring demand across selected countries.",
                "What salary evidence is available for senior roles?",
              ]).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void send(prompt)}
                  className="focus-ring"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, index) => (
          <div key={m.id}>
            {m.role === "assistant" &&
              m.retrieval &&
              m.retrieval.layers_used.length > 0 && (
                <RetrievalPanel info={m.retrieval} />
              )}

            {!(waitingForFirstToken && index === messages.length - 1) && (
              <div
                className={`chat-message-row ${m.role === "user" ? "chat-message-row--user" : ""}`}
              >
                <div
                  className={`chat-message ${m.role === "user" ? "chat-message--user" : "chat-message--assistant"}`}
                  dir="auto"
                  lang={containsArabic(m.content) ? "ar" : undefined}
                >
                  {m.role === "assistant" ? (
                    <BotMessage content={m.content} streaming={m.streaming} />
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {waitingForFirstToken && (
          <ResponsePending
            arabic={pendingInArabic}
            datasetCount={selectedDumps.length}
            evidenceFound={Boolean(latestMessage?.retrieval)}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-composer">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="chat-composer__form"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder={
              streaming
                ? arabic ? "اكتب سؤالًا جديدًا لإيقاف الإجابة الحالية" : "Type a new question to interrupt the response"
                : arabic ? "اسأل عن سوق العمل في دول الخليج" : "Ask about the GCC job market"
            }
            rows={1}
            dir="auto"
            lang={containsArabic(input) ? "ar" : undefined}
            disabled={!!sessionError}
            className="chat-composer__input focus-ring"
          />
          {streaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              className="app-secondary-button focus-ring"
            >
              {arabic ? "إيقاف" : "Stop"}
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || !sessionId}
              className="app-primary-button focus-ring"
            >
              {arabic ? "إرسال" : "Send"}
            </button>
          )}
        </form>
        <div className="chat-composer__hint">
          {streaming
            ? arabic ? "يبدأ Enter سؤالًا جديدًا ويوقف الإجابة الحالية. يلغي زر الإيقاف الإجابة." : "Enter interrupts with a new question. Stop cancels the response."
            : arabic ? "يرسل Enter السؤال. يبدأ Shift+Enter سطرًا جديدًا." : "Enter sends. Shift+Enter starts a new line."}
        </div>
      </div>
    </div>
  );
}
