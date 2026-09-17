"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

const QUICK_PROMPTS = [
  "What phone do I own?",
  "Should I buy iPhone or Samsung?",
  "Is my router affected by anything?",
  "What bills do I have coming up?",
];

interface ChatMessage {
  role: string;
  text: string;
  sources?: any[];
  evidence?: any[];
  entities?: any[];
}

interface ChatSummary {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  last_message: string | null;
}

function renderInlineText(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(<strong key={match.index} className="font-semibold text-ink">{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("[")) {
      const linkMatch = token.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (linkMatch) {
        parts.push(
          <a
            key={match.index}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-dusty-deep font-medium underline hover:text-ink transition-colors"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        parts.push(token);
      }
    } else {
      parts.push(token);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

function FormattedMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2) {
        const headerCells = tableLines[0]
          .split("|")
          .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
          .map((c) => c.trim());
        const startDataIdx = tableLines[1].includes("---") ? 2 : 1;
        const rowCells = tableLines.slice(startDataIdx).map((row) =>
          row
            .split("|")
            .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
            .map((c) => c.trim())
        );

        elements.push(
          <div key={`table-${i}`} className="my-2 overflow-x-auto rounded-lg border border-line">
            <table className="min-w-full text-xs border-collapse">
              <thead>
                <tr className="bg-surface border-b border-line text-ink">
                  {headerCells.map((cell, hIdx) => (
                    <th key={hIdx} className="px-2.5 py-1.5 text-left font-semibold border-r border-line last:border-r-0">
                      {renderInlineText(cell)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rowCells.map((row, rIdx) => (
                  <tr key={rIdx} className="border-b border-line last:border-b-0 hover:bg-surface/50">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-2.5 py-1.5 border-r border-line last:border-r-0 text-ink-soft">
                        {renderInlineText(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    if (trimmed.startsWith("#")) {
      const titleText = trimmed.replace(/^#+\s*/, "");
      elements.push(
        <h4 key={`h-${i}`} className="mt-2 mb-1 font-semibold text-xs text-ink tracking-tight">
          {renderInlineText(titleText)}
        </h4>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || /^\d+\.\s/.test(trimmed)) {
      const listItems: string[] = [];

      while (
        i < lines.length &&
        (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* ") || /^\d+\.\s/.test(lines[i].trim()))
      ) {
        listItems.push(lines[i].trim().replace(/^[-*]\s*/, "").replace(/^\d+\.\s*/, ""));
        i++;
      }

      elements.push(
        <ul key={`ul-${i}`} className="my-1.5 space-y-1 pl-4 text-xs list-disc text-ink-soft">
          {listItems.map((item, lIdx) => (
            <li key={lIdx} className="leading-snug">
              {renderInlineText(item)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    elements.push(
      <p key={`p-${i}`} className="my-1 text-xs leading-relaxed text-ink">
        {renderInlineText(trimmed)}
      </p>
    );
    i++;
  }

  return <div className="space-y-1 text-xs">{elements}</div>;
}

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: "Hello! How can I help you today?" },
  ]);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatToDelete, setChatToDelete] = useState<ChatSummary | null>(null);

  const loadChats = () => {
    api
      .listChats()
      .then((d) => setChats(d.chats))
      .catch(() => setChats([]));
  };

  useEffect(() => {
    if (open) {
      loadChats();
    }
  }, [open]);

  const startNewChat = () => {
    setConversationId(null);
    setMessages([{ role: "assistant", text: "Hello! How can I help you today?" }]);
    setError(null);
    setShowSidebar(false);
  };

  const selectChat = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const history = await api.getChat(id);
      setConversationId(history.id);
      setMessages(
        history.messages.map((m: any) => ({
          role: m.role,
          text: m.content,
        }))
      );
      setShowSidebar(false);
    } catch (err) {
      setError("Could not load chat history.");
    } finally {
      setBusy(false);
    }
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete) return;
    try {
      await api.deleteChat(chatToDelete.id);
      if (conversationId === chatToDelete.id) {
        startNewChat();
      }
      loadChats();
    } catch (err) {
      setError("Could not delete chat.");
    } finally {
      setChatToDelete(null);
    }
  };

  const sendQuery = async (queryText: string) => {
    if (!queryText.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.chatAssistant(queryText.trim(), conversationId || undefined);
      setConversationId(result.conversation_id);
      setMessages((current) => [
        ...current,
        { role: "user", text: queryText.trim() },
        {
          role: "assistant",
          text: result.answer,
          sources: result.sources,
          evidence: result.evidence,
          entities: result.entities,
        },
      ]);
      setQuestion("");
      loadChats();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    await sendQuery(question);
  };

  return (
    <aside className="fixed bottom-5 right-5 z-50 font-sans">
      {open && (
        <div className="mb-3 flex h-[min(75vh,620px)] w-[min(calc(100vw-2rem),460px)] flex-col card overflow-hidden shadow-lift">
          {/* Header Bar */}
          <div className="flex items-center justify-between border-b border-line bg-ink px-4 py-3 text-paper">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSidebar((v) => !v)}
                className="rounded-lg border border-paper/20 px-2 py-1 text-xs text-paper/90 hover:bg-paper/10"
                title="View Chat History"
              >
                {showSidebar ? "Chat" : "History"}
              </button>
              <div>
                <p className="text-sm font-semibold tracking-normal">MOSAIC Assistant</p>
                <p className="text-[11px] text-paper/70">Personal Data + Live Web Research</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={startNewChat}
                className="rounded-lg bg-paper/15 px-2.5 py-1 text-xs font-medium text-paper hover:bg-paper/25"
                title="New Chat"
              >
                + New
              </button>
              <button
                onClick={() => setOpen(false)}
                className="rounded-lg p-1.5 text-paper/80 hover:bg-paper/10 hover:text-paper"
                aria-label="Close Assistant"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>

          {/* Body Content */}
          <div className="relative flex flex-1 overflow-hidden">
            {/* Sidebar View */}
            {showSidebar ? (
              <div className="w-full space-y-2 overflow-y-auto bg-surface p-4 text-sm">
                <div className="flex items-center justify-between border-b border-line pb-2">
                  <span className="label">Saved Conversations</span>
                  <button
                    onClick={startNewChat}
                    className="text-xs font-medium text-dusty-deep hover:underline"
                  >
                    + Start New Chat
                  </button>
                </div>
                {chats.length === 0 ? (
                  <p className="py-8 text-center text-xs text-ink-faint">No previous chats found.</p>
                ) : (
                  <div className="space-y-2">
                    {chats.map((c) => (
                      <div
                        key={c.id}
                        className={`group flex items-center justify-between rounded-lg border p-2.5 transition-colors ${
                          c.id === conversationId
                            ? "border-dusty bg-dusty-soft/40"
                            : "border-line bg-paper hover:bg-line/20"
                        }`}
                      >
                        <button
                          onClick={() => selectChat(c.id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <p className="truncate text-xs font-medium text-ink">{c.title}</p>
                          <p className="mt-0.5 truncate text-[11px] text-ink-faint">
                            {c.last_message || "No messages"}
                          </p>
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setChatToDelete(c);
                          }}
                          className="ml-2 text-ink-faint hover:text-accent"
                          title="Delete Chat"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Main Chat Stream */
              <div className="flex flex-1 flex-col overflow-hidden bg-paper">
                <div className="flex-1 space-y-3 overflow-y-auto px-3.5 py-4 text-sm leading-relaxed">
                  {messages.map((message, index) => (
                    <div key={index} className="space-y-1">
                      <div
                        className={`max-w-[92%] rounded-xl px-3.5 py-2.5 text-sm ${
                          message.role === "user"
                            ? "ml-auto bg-ink text-paper whitespace-pre-wrap"
                            : "mr-auto border border-line bg-surface text-ink"
                        }`}
                      >
                        {message.role === "user" ? message.text : <FormattedMarkdown content={message.text} />}
                      </div>

                      {/* Render Evidence & Sources badges if present */}
                      {message.role === "assistant" && ((message.sources && message.sources.length > 0) || (message.evidence && message.evidence.length > 0)) && (
                        <div className="mr-auto max-w-[92%] space-y-1 px-1 text-[11px]">
                          {message.sources && message.sources.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1 text-ink-faint">
                              <span className="font-medium text-ink-soft">Sources:</span>
                              {message.sources.map((s, idx) => (
                                <span
                                  key={idx}
                                  className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 ${
                                    s.is_web ? "border-dusty/40 bg-dusty-soft text-dusty-deep" : "border-sage/40 bg-sage-soft text-sage-deep"
                                  }`}
                                >
                                  {s.is_web ? "🌐 Web" : "📄 Record"}: {s.name}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                  {error && <p className="mt-2 text-xs text-accent">{error}</p>}
                </div>

                {messages.length <= 2 && (
                  <div className="flex flex-wrap gap-1.5 border-t border-line bg-paper px-3 py-2">
                    {QUICK_PROMPTS.map((prompt, i) => (
                      <button
                        key={i}
                        onClick={() => sendQuery(prompt)}
                        disabled={busy}
                        className="rounded-md border border-line bg-surface px-2.5 py-1 text-[11px] text-ink-soft hover:bg-line/40"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                )}

                <form onSubmit={ask} className="flex flex-col gap-2 border-t border-line bg-surface p-3">
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask anything or search your data..."
                    aria-label="Ask MOSAIC Assistant"
                    className="min-w-0 flex-1 rounded-lg border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-dusty"
                  />
                  <button className="btn-primary w-full rounded-lg" disabled={busy}>
                    {busy ? "Thinking..." : "Send Message"}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {chatToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/20 backdrop-blur-sm p-4">
          <div className="card max-w-sm p-5 space-y-4 shadow-lift">
            <h3 className="font-serif text-lg text-ink">Delete Chat Confirmation</h3>
            <p className="text-xs text-ink-soft">
              Are you sure you want to delete <strong className="text-ink">{chatToDelete.title}</strong>? Your personal Life Graph items and documents will NOT be deleted.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setChatToDelete(null)}
                className="btn-ghost text-xs px-3 py-1.5"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteChat}
                className="btn-primary bg-accent text-white hover:bg-accent-deep text-xs px-3 py-1.5"
              >
                Delete Chat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Toggle Button */}
      <button
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Close MOSAIC Assistant" : "Open MOSAIC Assistant"}
        className="ml-auto flex h-12 w-12 items-center justify-center rounded-xl bg-ink text-paper shadow-lift hover:bg-ink-soft transition-colors"
      >
        {open ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
    </aside>
  );
}
