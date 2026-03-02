/**
 * Code Viewer Component
 * Displays file content with syntax highlighting
 */

import { Copy, FileCode } from "lucide-react";
import { useState } from "react";
import { Button } from "@/features/ui/primitives";

interface CodeViewerProps {
  content: string;
  filePath: string;
  language?: string;
  isLoading: boolean;
}

export const CodeViewer = ({ content, filePath, language, isLoading }: CodeViewerProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-zinc-900/50 backdrop-blur-xl">
        <div className="text-sm text-zinc-400">Loading file...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-white/10 bg-zinc-900/50 backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 p-4">
        <div className="flex items-center gap-2">
          <FileCode className="h-5 w-5 text-cyan-400" />
          <div>
            <p className="text-sm font-medium text-white">{filePath.split("/").pop()}</p>
            <p className="text-xs text-zinc-500">{filePath}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {language && (
            <span className="rounded bg-purple-500/20 px-2 py-1 text-xs text-purple-300">
              {language}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            <Copy className="mr-2 h-4 w-4" />
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
      </div>

      {/* Code content */}
      <div className="flex-1 overflow-auto p-4">
        <pre className="text-sm">
          <code className="text-zinc-300">{content}</code>
        </pre>
      </div>
    </div>
  );
};
