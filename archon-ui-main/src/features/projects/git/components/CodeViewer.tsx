/**
 * Code Viewer Component
 * Displays file content with syntax highlighting
 */

import { Copy, FileCode, Maximize2, Minimize2 } from "lucide-react";
import Prism from "prismjs";
import { useState } from "react";
import { Button } from "@/features/ui/primitives";

// Import Prism theme
import "prismjs/themes/prism-tomorrow.css";

// Import language components
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-tsx";
import "prismjs/components/prism-python";
import "prismjs/components/prism-java";
import "prismjs/components/prism-json";
import "prismjs/components/prism-yaml";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-sql";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-css";

interface CodeViewerProps {
  content: string;
  filePath: string;
  language?: string;
  isLoading: boolean;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export const CodeViewer = ({ content, filePath, language, isLoading, isExpanded, onToggleExpand }: CodeViewerProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Highlight code with Prism (with XSS protection)
  const highlightCode = (code: string, lang?: string): string => {
    try {
      // CRITICAL: Escape HTML entities FIRST for XSS prevention
      const escaped = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const language = lang?.toLowerCase() || "javascript";
      const grammar = Prism.languages[language] || Prism.languages.javascript;
      return Prism.highlight(escaped, grammar, language);
    } catch (error) {
      console.error("Prism highlighting failed:", error);
      // Return escaped code on error
      return code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
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
          {onToggleExpand && (
            <Button variant="ghost" size="sm" onClick={onToggleExpand}>
              {isExpanded ? (
                <>
                  <Minimize2 className="mr-2 h-4 w-4" />
                  Split View
                </>
              ) : (
                <>
                  <Maximize2 className="mr-2 h-4 w-4" />
                  Expand
                </>
              )}
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            <Copy className="mr-2 h-4 w-4" />
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
      </div>

      {/* Code content */}
      <div className="flex-1 overflow-auto p-4">
        <pre className="text-sm bg-black/30 border border-cyan-500/10 rounded-lg p-4">
          <code
            className={`language-${language || "javascript"} font-mono leading-relaxed`}
            dangerouslySetInnerHTML={{ __html: highlightCode(content, language) }}
          />
        </pre>
      </div>
    </div>
  );
};
