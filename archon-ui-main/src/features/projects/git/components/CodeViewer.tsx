/**
 * Code Viewer Component
 * Displays file content with syntax highlighting
 */

import { Copy, FileCode, Maximize2 } from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "@/features/ui/primitives";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/features/ui/primitives/dialog";
import Prism from "prismjs";
import "prismjs/themes/prism-tomorrow.css";

// Import common language support
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-tsx";
import "prismjs/components/prism-python";
import "prismjs/components/prism-java";
import "prismjs/components/prism-c";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-csharp";
import "prismjs/components/prism-go";
import "prismjs/components/prism-rust";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-json";
import "prismjs/components/prism-yaml";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-sql";
import "prismjs/components/prism-css";

interface CodeViewerProps {
  content: string;
  filePath: string;
  language?: string;
  isLoading: boolean;
}

export const CodeViewer = ({ content, filePath, language, isLoading }: CodeViewerProps) => {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Apply syntax highlighting when content, language, or modal state changes
  useEffect(() => {
    Prism.highlightAll();
  }, [content, language, isExpanded]);

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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(true)}
            className="text-zinc-400 hover:text-white"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            <Copy className="mr-2 h-4 w-4" />
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
      </div>

      {/* Code content */}
      <div className="flex-1 overflow-auto p-4">
        <pre className="text-sm">
          <code className={language ? `language-${language}` : "text-zinc-300"}>
            {content}
          </code>
        </pre>
      </div>

      {/* Expand Modal */}
      <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileCode className="h-4 w-4 text-cyan-400" />
              <span>{filePath.split("/").pop()}</span>
              <span className="text-xs text-zinc-500">({filePath})</span>
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto rounded-lg border border-white/10 bg-zinc-950/50">
            <pre className="text-sm p-4">
              <code className={language ? `language-${language}` : "text-zinc-300"}>
                {content}
              </code>
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
