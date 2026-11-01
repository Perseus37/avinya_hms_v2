import { Component, ErrorInfo, ReactNode } from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";
import { Button } from "./Button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  moduleName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Clinical Workstation Render Error Caught:", error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center p-8 bg-slate-950 text-slate-100">
          <div className="w-14 h-14 rounded-2xl bg-rose-950/60 border border-rose-800 flex items-center justify-center text-rose-400 mb-4 shadow-xl">
            <AlertOctagon size={28} />
          </div>
          <h2 className="text-lg font-bold text-slate-100 mb-1">
            {this.props.fallbackTitle || "Clinical Component Exception"}
          </h2>
          <p className="text-xs text-slate-400 max-w-md text-center mb-4">
            An isolated rendering error occurred in this workspace. The rest of your clinical workstation and patient safety context remains safe and active.
          </p>
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-rose-300 max-w-lg overflow-x-auto mb-4">
            {this.state.error?.message || "Unknown rendering exception"}
          </div>
          <Button
            onClick={this.handleReset}
            className="flex items-center gap-1.5 text-xs bg-sky-600 hover:bg-sky-500 text-slate-950 font-bold"
          >
            <RotateCcw size={14} />
            <span>Recover Workspace</span>
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
