/**
 * Semantic Search Results Component
 * Displays commit search results with similarity scores and classification
 */

import { GitCommit, Calendar, User, TrendingUp, AlertCircle } from "lucide-react";
import type { CommitSearchResult } from "../services/semanticSearchService";
import { ClassificationBadges } from "./ClassificationBadges";

interface SemanticSearchResultsProps {
  results: CommitSearchResult[];
  isLoading?: boolean;
  query?: string;
  onSelectCommit?: (commitSha: string) => void;
  selectedCommitSha?: string;
}

export const SemanticSearchResults = ({
  results,
  isLoading = false,
  query,
  onSelectCommit,
  selectedCommitSha,
}: SemanticSearchResultsProps) => {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500/20 border-t-cyan-500" />
          <p className="text-sm text-zinc-400">Searching commits...</p>
        </div>
      </div>
    );
  }

  if (!query) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md text-center">
          <div className="mb-4 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/10 to-purple-500/10">
              <GitCommit className="h-8 w-8 text-cyan-400" />
            </div>
          </div>
          <h3 className="mb-2 text-lg font-medium text-white">Semantic Commit Search</h3>
          <p className="text-sm text-zinc-400">
            Search commits using natural language queries like "performance improvements",
            "bug fixes in authentication", or "security updates".
          </p>
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md text-center">
          <div className="mb-4 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-zinc-800/50">
              <AlertCircle className="h-8 w-8 text-zinc-500" />
            </div>
          </div>
          <h3 className="mb-2 text-lg font-medium text-white">No commits found</h3>
          <p className="text-sm text-zinc-400">
            No commits matched your search query "{query}". Try adjusting your filters or
            using different keywords.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Results header */}
      <div className="mb-4 flex items-center justify-between border-b border-white/5 pb-3">
        <div>
          <h3 className="text-sm font-medium text-white">
            {results.length} commit{results.length !== 1 ? "s" : ""} found
          </h3>
          <p className="text-xs text-zinc-400">for "{query}"</p>
        </div>
      </div>

      {/* Results list */}
      <div className="flex-1 space-y-3 overflow-y-auto">
        {results.map((result) => (
          <button
            key={result.commit_sha}
            onClick={() => onSelectCommit?.(result.commit_sha)}
            className={`w-full rounded-lg border p-4 text-left transition-all ${
              selectedCommitSha === result.commit_sha
                ? "border-cyan-500/50 bg-cyan-500/10"
                : "border-white/10 bg-zinc-900/30 hover:border-white/20 hover:bg-zinc-900/50"
            }`}
            type="button"
          >
            {/* Commit header */}
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <GitCommit className="h-4 w-4 text-cyan-400" />
                  <code className="text-xs text-cyan-400">{result.commit_sha.substring(0, 8)}</code>
                  {/* Similarity score */}
                  <div className="flex items-center gap-1 rounded-full bg-purple-500/10 px-2 py-0.5">
                    <TrendingUp className="h-3 w-3 text-purple-400" />
                    <span className="text-xs font-medium text-purple-300">
                      {(result.similarity_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <p className="line-clamp-2 text-sm text-white">{result.message}</p>
              </div>
            </div>

            {/* Classification badges */}
            {result.classification && (
              <div className="mb-3">
                <ClassificationBadges
                  classification={result.classification as any}
                  compact={true}
                />
              </div>
            )}

            {/* Commit metadata */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-400">
              <div className="flex items-center gap-1.5">
                <User className="h-3.5 w-3.5" />
                <span>{result.author}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                <span>
                  {new Date(result.commit_date).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>
              {result.branches.length > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="text-zinc-500">•</span>
                  <span className="max-w-[150px] truncate">
                    {result.branches.slice(0, 2).join(", ")}
                    {result.branches.length > 2 && ` +${result.branches.length - 2}`}
                  </span>
                </div>
              )}
            </div>

            {/* Diff summary if available */}
            {result.diff_summary && (
              <div className="mt-3 rounded border border-white/5 bg-black/20 p-2">
                <p className="line-clamp-2 text-xs text-zinc-400">{result.diff_summary}</p>
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};
