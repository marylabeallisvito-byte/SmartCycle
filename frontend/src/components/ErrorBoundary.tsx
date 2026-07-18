"use client";

/* ============================================================
   SmartCycle — ErrorBoundary
   ============================================================

   Catches React rendering errors and displays a friendly
   fallback UI instead of a blank white page.

   Usage:
     <ErrorBoundary>
       <YourComponent />
     </ErrorBoundary>
============================================================ */

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  resetKey: number;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, resetKey: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  handleReset = () => {
    this.setState((prev) => ({
      hasError: false,
      error: null,
      errorInfo: null,
      resetKey: prev.resetKey + 1,
    }));
  };

  handleReload = () => {
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-[#06060c] p-8">
          <div className="surface-card max-w-lg p-8 text-center">
            {/* Icon */}
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#ef4444]/10">
              <AlertTriangle className="h-8 w-8 text-[#ef4444]" />
            </div>

            {/* Message */}
            <h1 className="mb-2 text-xl font-semibold text-[#e2e8f0]">
              系统错误 · System Error
            </h1>
            <p className="mb-4 text-sm text-[#94a3b8]">
              Something went wrong rendering this page. This is likely a
              client-side issue — your data on the server is safe.
            </p>

            {/* Error details */}
            {this.state.error && (
              <div className="mb-6 rounded-lg bg-[#0a0a14] border border-[#1e2948] p-4 text-left">
                <p className="mb-1 text-xs font-medium text-[#ef4444]">
                  {this.state.error.name}
                </p>
                <p className="text-xs text-[#94a3b8] font-mono break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={this.handleReset}
                className="inline-flex items-center gap-2 rounded-lg bg-[#00d4ff]/10 border border-[#00d4ff]/30 px-4 py-2 text-sm font-medium text-[#00d4ff] hover:bg-[#00d4ff]/20 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Try Again
              </button>
              <button
                onClick={this.handleReload}
                className="inline-flex items-center gap-2 rounded-lg bg-[#141428] border border-[#1e2948] px-4 py-2 text-sm font-medium text-[#e2e8f0] hover:bg-[#1a1a33] transition-colors"
              >
                <Home className="h-4 w-4" />
                Reload Page
              </button>
            </div>

            <p className="mt-6 text-2xs text-[#64748b]">
              SmartCycle (金仕达·智循) v0.3.0 · If this persists, contact your
              system administrator.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div key={this.state.resetKey} className="contents">
        {this.props.children}
      </div>
    );
  }
}
