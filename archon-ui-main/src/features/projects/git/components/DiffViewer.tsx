/**
 * Diff Viewer Component
 * Side-by-side view of code changes between commits
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, FileIcon, FileText, AlertTriangle } from "lucide-react";

export interface DiffHunk {
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  context: string;
  diff_text: string;
  additions: number;
  deletions: number;
}

export interface FileDiff {
  path: string;
  old_path?: string | null;
  status: "added" | "deleted" | "modified" | "renamed";
  language?: string | null;
  additions: number;
  deletions: number;
  is_binary: boolean;
  hunks: DiffHunk[];
}

export interface StructuredDiff {
  from_commit: string;
  to_commit: string;
  files_changed: number;
  additions: number;
  deletions: number;
  files: FileDiff[];
}

interface DiffViewerProps {
  diff: StructuredDiff;
}

interface FileDiffViewProps {
  file: FileDiff;
  defaultExpanded?: boolean;
}

/**
 * Get color for file status
 */
const getStatusColor = (status: FileDiff["status"]) => {
  switch (status) {
    case "added":
      return "text-green-400";
    case "deleted":
      return "text-red-400";
    case "modified":
      return "text-blue-400";
    case "renamed":
      return "text-purple-400";
    default:
      return "text-zinc-400";
  }
};

/**
 * Get status label
 */
const getStatusLabel = (status: FileDiff["status"]) => {
  switch (status) {
    case "added":
      return "ADDED";
    case "deleted":
      return "DELETED";
    case "modified":
      return "MODIFIED";
    case "renamed":
      return "RENAMED";
    default:
      return status.toUpperCase();
  }
};

/**
 * Parse diff text into lines with metadata
 */
const parseDiffLines = (diffText: string) => {
  const lines = diffText.split("\n");
  return lines.map((line) => {
    if (line.startsWith("+")) {
      return { type: "addition" as const, content: line.substring(1) };
    }
    if (line.startsWith("-")) {
      return { type: "deletion" as const, content: line.substring(1) };
    }
    if (line.startsWith("@@")) {
      return { type: "hunk-header" as const, content: line };
    }
    return { type: "context" as const, content: line.startsWith(" ") ? line.substring(1) : line };
  });
};

/**
 * Individual file diff view
 */
const FileDiffView = ({ file, defaultExpanded = false }: FileDiffViewProps) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-lg border border-white/10 bg-zinc-900/50">
      {/* File header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-white/5"
        type="button"
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown className="h-4 w-4 text-zinc-400" /> : <ChevronRight className="h-4 w-4 text-zinc-400" />}

          {file.is_binary ? (
            <FileIcon className="h-4 w-4 text-zinc-400" />
          ) : (
            <FileText className="h-4 w-4 text-zinc-400" />
          )}

          <code className="font-mono text-sm text-white">{file.path}</code>

          {file.old_path && file.old_path !== file.path && (
            <span className="font-mono text-xs text-zinc-500">← {file.old_path}</span>
          )}

          <span className={`rounded bg-zinc-800/50 px-2 py-0.5 text-xs font-medium ${getStatusColor(file.status)}`}>
            {getStatusLabel(file.status)}
          </span>

          {file.language && (
            <span className="rounded bg-purple-500/20 px-2 py-0.5 text-xs text-purple-300">{file.language}</span>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs">
          {file.additions > 0 && <span className="text-green-400">+{file.additions}</span>}
          {file.deletions > 0 && <span className="text-red-400">-{file.deletions}</span>}
        </div>
      </button>

      {/* File diff content */}
      {expanded && (
        <div className="border-t border-white/10">
          {file.is_binary ? (
            <div className="flex items-center gap-2 p-4 text-sm text-zinc-400">
              <AlertTriangle className="h-4 w-4" />
              <span>Binary file - diff not available</span>
            </div>
          ) : file.hunks.length === 0 ? (
            <div className="p-4 text-sm text-zinc-400">No changes to display</div>
          ) : (
            <div className="overflow-x-auto">
              {file.hunks.map((hunk, hunkIdx) => (
                <div key={hunkIdx} className="border-b border-white/5 last:border-b-0">
                  {/* Hunk header */}
                  {hunk.context && (
                    <div className="bg-blue-500/10 px-4 py-1 font-mono text-xs text-blue-300">{hunk.context}</div>
                  )}

                  {/* Diff lines */}
                  <div className="font-mono text-xs">
                    {parseDiffLines(hunk.diff_text).map((line, lineIdx) => (
                      <div
                        key={lineIdx}
                        className={`flex ${
                          line.type === "addition"
                            ? "bg-green-500/10 text-green-300"
                            : line.type === "deletion"
                              ? "bg-red-500/10 text-red-300"
                              : line.type === "hunk-header"
                                ? "bg-blue-500/10 text-blue-300"
                                : "text-zinc-400"
                        }`}
                      >
                        <div className="w-12 flex-shrink-0 select-none px-2 py-0.5 text-right text-zinc-500">
                          {line.type !== "hunk-header" && lineIdx + 1}
                        </div>
                        <div className="flex-1 px-2 py-0.5">
                          <pre className="whitespace-pre-wrap break-all">{line.content || " "}</pre>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Main diff viewer component
 */
export const DiffViewer = ({ diff }: DiffViewerProps) => {
  const [expandAll, setExpandAll] = useState(false);

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex items-center justify-between rounded-lg border border-white/10 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-zinc-400">
            <span className="font-medium text-white">{diff.files_changed}</span> file{diff.files_changed !== 1 && "s"} changed
          </span>
          <span className="text-green-400">
            <span className="font-medium">+{diff.additions}</span> addition{diff.additions !== 1 && "s"}
          </span>
          <span className="text-red-400">
            <span className="font-medium">-{diff.deletions}</span> deletion{diff.deletions !== 1 && "s"}
          </span>
        </div>

        <button
          onClick={() => setExpandAll(!expandAll)}
          className="rounded border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-white/10"
          type="button"
        >
          {expandAll ? "Collapse All" : "Expand All"}
        </button>
      </div>

      {/* File diffs */}
      <div className="space-y-2">
        {diff.files.length === 0 ? (
          <div className="rounded-lg border border-white/10 bg-zinc-900/50 p-8 text-center text-zinc-400">
            No changes between these commits
          </div>
        ) : (
          diff.files.map((file, idx) => <FileDiffView key={idx} file={file} defaultExpanded={expandAll} />)
        )}
      </div>
    </div>
  );
};
