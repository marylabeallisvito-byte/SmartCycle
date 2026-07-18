"use client";

/* ============================================================
   SmartCycle — Advisor Copilot Chat Interface

   Features:
     • Streaming-style message bubbles
     • Compliance Shield badge (green/red based on agent verdict)
     • Expandable Agent Thought Process accordion
     • Mock API integration with the Phase 2 backend

   Visual: Dark Bloomberg-esque with neon accent borders.
============================================================ */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  Brain,
  ChevronDown,
  ChevronUp,
  Database,
  FileSearch,
  Loader2,
  Send,
  Shield,
  ShieldAlert,
  StopCircle,
  User,
  CheckCircle2,
  Circle,
  type LucideIcon,
} from "lucide-react";

import type { AgentTrace, ChatMessage } from "@/lib/mockData";
import type { PipelineProgress, PipelineStage } from "@/lib/useChat";

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  isLoading: boolean;
  selectedClientName?: string;
  onCancel?: () => void;
  progress?: PipelineProgress;
}

// ═══════════════════════════════════════════════════════════════
// Sub-component: Agent Thought Process Accordion
// ═══════════════════════════════════════════════════════════════

function AgentTraceAccordion({ trace }: { trace: AgentTrace }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-3 border-t border-[#1e2948]/60 pt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 text-xs font-medium text-[#94a3b8] hover:text-[#e2e8f0] transition-colors"
      >
        <Brain className="h-3.5 w-3.5 text-[#8b5cf6]" />
        Agent Thought Process
        {open ? (
          <ChevronUp className="ml-auto h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="ml-auto h-3.5 w-3.5" />
        )}
      </button>

      {open && (
        <div className="mt-3 space-y-3 animate-slide-up">
          {/* Step 1: Router */}
          <Step
            icon={<FileSearch className="h-3.5 w-3.5" />}
            label="Router"
            color="text-[#8b5cf6]"
            bg="bg-[#8b5cf6]/10"
          >
            <span className="data-badge">{trace.queryCategory}</span>
          </Step>

          {/* Step 2: Quantitative Researcher */}
          <Step
            icon={<Database className="h-3.5 w-3.5" />}
            label="Quantitative Researcher (FinRobot)"
            color="text-[#00d4ff]"
            bg="bg-[#00d4ff]/10"
          >
            <div className="text-xs text-[#94a3b8] space-y-1">
              {trace.rawData.marketData && (
                <div>
                  <span className="text-[#64748b]">Market Data: </span>
                  {Object.entries(trace.rawData.marketData).map(([k, v]) => (
                    <span key={k} className="text-[#00d4ff]">
                      {(v as Record<string, unknown>).nameCn as string || k}{" "}
                    </span>
                  ))}
                </div>
              )}
              {trace.rawData.ragContext && (
                <div>
                  <span className="text-[#64748b]">RAG Docs: </span>
                  {trace.rawData.ragContext.map((d, i) => (
                    <span key={i} className="text-[#e2e8f0]">
                      {d.title}
                      {i < trace.rawData.ragContext!.length - 1 ? ", " : ""}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </Step>

          {/* Step 3: Empathy Copilot */}
          <Step
            icon={<Bot className="h-3.5 w-3.5" />}
            label="Empathy Copilot (Draft)"
            color="text-[#f59e0b]"
            bg="bg-[#f59e0b]/10"
          >
            <p className="text-xs text-[#94a3b8] line-clamp-3">
              {trace.draftResponse}
            </p>
          </Step>

          {/* Step 4: Compliance Gatekeeper */}
          <Step
            icon={
              trace.complianceFlags.length === 0 ? (
                <Shield className="h-3.5 w-3.5" />
              ) : (
                <ShieldAlert className="h-3.5 w-3.5" />
              )
            }
            label="Compliance Gatekeeper (tradingagents)"
            color={
              trace.complianceFlags.length === 0
                ? "text-[#10b981]"
                : "text-[#ef4444]"
            }
            bg={
              trace.complianceFlags.length === 0
                ? "bg-[#10b981]/10"
                : "bg-[#ef4444]/10"
            }
          >
            {trace.complianceFlags.length === 0 ? (
              <span className="text-xs text-[#10b981] font-medium">
                ✅ Passed — {trace.revisionCount} revision(s)
              </span>
            ) : (
              <div className="space-y-1">
                {trace.complianceFlags.map((f, i) => (
                  <div key={i} className="text-xs">
                    <span
                      className={`font-mono font-medium ${
                        f.severity === "critical"
                          ? "text-[#ef4444]"
                          : "text-[#f59e0b]"
                      }`}
                    >
                      [{f.severity.toUpperCase()}]
                    </span>{" "}
                    <span className="text-[#94a3b8]">
                      {f.bannedPhrase} → {f.suggestion}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Step>
        </div>
      )}
    </div>
  );
}

/* ── Tiny step row within accordion ── */

function Step({
  icon,
  label,
  color,
  bg,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  bg: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-lg ${bg} p-2.5 border border-[#1e2948]/40`}>
      <div className={`mb-1.5 flex items-center gap-1.5 text-xs font-medium ${color}`}>
        {icon}
        {label}
      </div>
      {children}
    </div>
  );
}

/* ── Compliance Shield Badge ── */

function ComplianceShield({ passed }: { passed: boolean }) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium border animate-compliance-pass ${
        passed
          ? "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]"
          : "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]"
      }`}
    >
      {passed ? (
        <Shield className="h-3 w-3" />
      ) : (
        <ShieldAlert className="h-3 w-3" />
      )}
      {passed ? "Compliance Passed" : "Compliance Flagged"}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Main ChatInterface Component
   ═══════════════════════════════════════════════════════════════ */

export default function ChatInterface({
  messages,
  onSend,
  isLoading,
  selectedClientName,
  onCancel,
  progress,
}: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || isLoading) return;
      onSend(trimmed);
      setInput("");
    },
    [input, isLoading, onSend],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit],
  );

  // Auto-resize textarea on input
  const handleTextareaInput = useCallback(
    (e: React.FormEvent<HTMLTextAreaElement>) => {
      const el = e.currentTarget;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    },
    [],
  );

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <div className="flex items-center justify-between border-b border-[#1e2948] px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#00d4ff]/10">
            <Bot className="h-4 w-4 text-[#00d4ff]" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-[#e2e8f0]">
              Advisor Copilot
            </h2>
            {selectedClientName && (
              <p className="text-2xs text-[#64748b]">
                Client: {selectedClientName}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-2xs text-[#64748b]">
          <span className="status-dot status-dot-active" />
          SmartCycle Engine Online
        </div>
      </div>

      {/* ── Messages ── */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-5 py-4 space-y-4"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Loading indicator with progress + cancel */}
        {isLoading && (
          <div className="space-y-3 animate-fade-in">
            {/* Pipeline Progress Indicator */}
            {progress && progress.stage !== "idle" && (
              <PipelineProgressIndicator progress={progress} />
            )}

            {/* Loading spinner */}
            <div className="flex items-start gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#8b5cf6]/10">
                <Bot className="h-3.5 w-3.5 text-[#8b5cf6]" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl rounded-tl-md bg-[#141428] border border-[#1e2948] px-4 py-3">
                <Loader2 className="h-4 w-4 animate-spin text-[#8b5cf6]" />
                <span className="text-sm text-[#94a3b8]">
                  {progress?.detail || "Agents processing..."}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-[#1e2948] px-5 py-3"
      >
        <div className="flex items-end gap-3">
          <div className="relative flex-1">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleTextareaInput}
              rows={1}
              placeholder={
                selectedClientName
                  ? `Ask about ${selectedClientName}'s portfolio...`
                  : "Ask anything about markets, portfolios, or client strategy..."
              }
              className="w-full resize-none rounded-xl border border-[#1e2948] bg-[#0a0a14] px-4 py-2.5
                         text-sm text-[#e2e8f0] placeholder-[#64748b]
                         focus:border-[#00d4ff]/40 focus:outline-none focus:ring-1 focus:ring-[#00d4ff]/20
                         transition-colors"
              style={{ maxHeight: "120px" }}
              disabled={isLoading}
            />
          </div>
          {/* Cancel button (visible during loading) */}
          {isLoading && onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                         bg-[#ef4444]/20 border border-[#ef4444]/40 text-[#ef4444] transition-all
                         hover:bg-[#ef4444]/30 hover:shadow-neon-red"
              title="Cancel request"
              aria-label="Cancel current request"
            >
              <StopCircle className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                         bg-[#00d4ff] text-[#06060c] transition-all
                         hover:bg-[#00d4ff]/90 hover:shadow-neon-cyan
                         disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none"
              aria-label="Send message"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          )}
        </div>
        <p className="mt-2 text-2xs text-[#64748b]">
          Press <kbd className="rounded bg-[#141428] px-1 py-0.5 font-mono">Enter</kbd> to send ·{" "}
          <kbd className="rounded bg-[#141428] px-1 py-0.5 font-mono">Shift+Enter</kbd> for new line ·{" "}
          All responses screened by Compliance Agent
        </p>
      </form>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Pipeline Progress Indicator
// ═══════════════════════════════════════════════════════════════

const PIPELINE_STEPS: { stage: PipelineStage; label: string; icon: LucideIcon; color: string }[] = [
  { stage: "router", label: "Router", icon: FileSearch, color: "#8b5cf6" },
  { stage: "researcher", label: "Researcher", icon: Database, color: "#00d4ff" },
  { stage: "copilot", label: "Copilot", icon: Bot, color: "#f59e0b" },
  { stage: "compliance", label: "Compliance", icon: Shield, color: "#10b981" },
];

function PipelineProgressIndicator({ progress }: { progress: PipelineProgress }) {
  const currentIdx = PIPELINE_STEPS.findIndex((s) => s.stage === progress.stage);

  return (
    <div className="rounded-xl bg-[#0f0f1e] border border-[#1e2948] p-3">
      <p className="mb-2 text-2xs font-medium uppercase tracking-wider text-[#64748b]">
        Pipeline Progress
      </p>
      <div className="flex items-center gap-1.5">
        {PIPELINE_STEPS.map((step, i) => {
          const isActive = i === currentIdx;
          const isComplete = i < currentIdx;
          const isError = progress.stage === "error";
          const isCancelled = progress.stage === "cancelled";

          return (
            <div key={step.stage} className="flex items-center gap-1.5">
              {/* Step dot */}
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                    isError || isCancelled
                      ? "border-[#ef4444] bg-[#ef4444]/10"
                      : isActive
                      ? "border-[#00d4ff] bg-[#00d4ff]/10 shadow-[0_0_8px_rgba(0,212,255,0.3)]"
                      : isComplete
                      ? "border-[#10b981] bg-[#10b981]/10"
                      : "border-[#1e2948] bg-[#0a0a14]"
                  }`}
                  style={
                    isActive && !isError && !isCancelled
                      ? { borderColor: step.color }
                      : undefined
                  }
                >
                  {isComplete ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />
                  ) : isActive ? (
                    <step.icon
                      className="h-3.5 w-3.5"
                      style={{ color: step.color }}
                    />
                  ) : (
                    <Circle className="h-2 w-2 text-[#1e2948]" />
                  )}
                </div>
                {/* Label */}
                <span
                  className={`mt-1 text-[9px] font-medium whitespace-nowrap ${
                    isActive
                      ? "text-[#e2e8f0]"
                      : isComplete
                      ? "text-[#10b981]"
                      : "text-[#475569]"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {/* Connector line */}
              {i < PIPELINE_STEPS.length - 1 && (
                <div
                  className={`mb-4 h-0.5 w-6 rounded transition-colors duration-300 ${
                    i < currentIdx ? "bg-[#10b981]" : "bg-[#1e2948]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
      {/* Status text */}
      {progress.detail && (
        <p
          className={`mt-2 text-xs ${
            progress.stage === "error" || progress.stage === "cancelled"
              ? "text-[#ef4444]"
              : "text-[#94a3b8]"
          }`}
        >
          {progress.detail}
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Sub-component: Message Bubble
   ═══════════════════════════════════════════════════════════════ */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex items-start gap-3 animate-slide-up ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
          isUser ? "bg-[#3b82f6]/20" : "bg-[#8b5cf6]/10"
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-[#3b82f6]" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-[#8b5cf6]" />
        )}
      </div>

      {/* Content */}
      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "rounded-tr-md bg-[#1a1a33] border border-[#263355] text-[#e2e8f0]"
              : "rounded-tl-md bg-[#0f0f1e] border border-[#1e2948] text-[#e2e8f0]"
          }`}
        >
          {/* Simple markdown-esque rendering for bold */}
          {message.content.split("\n").map((line, i) => (
            <p key={i} className="min-h-[1.25rem]">
              {renderLine(line)}
            </p>
          ))}
        </div>

        {/* Compliance Shield + Agent Trace (assistant only) */}
        {!isUser && message.compliancePassed !== undefined && (
          <div className="mt-2">
            <ComplianceShield passed={message.compliancePassed} />
            {message.agentTrace && (
              <AgentTraceAccordion trace={message.agentTrace} />
            )}
          </div>
        )}

        {/* Timestamp */}
        <p
          className={`mt-1 text-2xs text-[#64748b] ${
            isUser ? "text-right" : ""
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

/* ── Inline markdown renderer (bold only for now) ── */

function renderLine(line: string): React.ReactNode {
  // Bold: **text**
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-[#00d4ff]">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}
