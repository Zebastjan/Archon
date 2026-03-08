/**
 * Commit Search Component
 * Semantic search interface for Git commits with filters
 */

import { Search, Filter, X, Calendar, Tag, AlertTriangle, Shield } from "lucide-react";
import { useState } from "react";
import type { CommitSearchFilters } from "../services/semanticSearchService";

interface CommitSearchProps {
  onSearch: (query: string, filters: CommitSearchFilters) => void;
  isLoading?: boolean;
  defaultBranch?: string;
  repoId?: string;
}

export const CommitSearch = ({
  onSearch,
  isLoading = false,
  defaultBranch,
  repoId,
}: CommitSearchProps) => {
  const [query, setQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<CommitSearchFilters>({
    repo_id: repoId,
    branch: defaultBranch,
  });

  const handleSearch = () => {
    if (query.trim()) {
      onSearch(query, filters);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const clearFilters = () => {
    setFilters({
      repo_id: repoId,
      branch: defaultBranch,
    });
  };

  const hasActiveFilters = () => {
    return !!(
      filters.since ||
      filters.until ||
      filters.intent?.length ||
      filters.risk?.length ||
      filters.author ||
      filters.breaking_only ||
      filters.security_only
    );
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Search commits semantically... (e.g., 'performance improvements', 'bug fixes in auth')"
            className="w-full rounded-lg border border-white/10 bg-zinc-900/50 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50"
            disabled={isLoading}
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={isLoading || !query.trim()}
          className="rounded-lg bg-gradient-to-r from-cyan-500 to-purple-500 px-6 py-2.5 text-sm font-medium text-white transition-all hover:shadow-lg hover:shadow-cyan-500/25 disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
        >
          {isLoading ? "Searching..." : "Search"}
        </button>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`rounded-lg border px-4 py-2.5 text-sm font-medium transition-all ${
            showFilters || hasActiveFilters()
              ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-400"
              : "border-white/10 bg-zinc-900/50 text-zinc-400 hover:text-white"
          }`}
          type="button"
        >
          <Filter className="h-4 w-4" />
        </button>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="rounded-lg border border-white/10 bg-zinc-900/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Search Filters</h3>
            {hasActiveFilters() && (
              <button
                onClick={clearFilters}
                className="text-xs text-zinc-400 hover:text-white"
                type="button"
              >
                Clear all
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Branch filter */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                <Tag className="h-3.5 w-3.5" />
                Branch
              </label>
              <input
                type="text"
                value={filters.branch || ""}
                onChange={(e) => setFilters({ ...filters, branch: e.target.value })}
                placeholder={defaultBranch || "main"}
                className="w-full rounded border border-white/10 bg-zinc-900 px-3 py-1.5 text-sm text-white placeholder-zinc-600 outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Author filter */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Author
              </label>
              <input
                type="text"
                value={filters.author || ""}
                onChange={(e) => setFilters({ ...filters, author: e.target.value })}
                placeholder="Author name or email"
                className="w-full rounded border border-white/10 bg-zinc-900 px-3 py-1.5 text-sm text-white placeholder-zinc-600 outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Date range - Since */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                <Calendar className="h-3.5 w-3.5" />
                Since
              </label>
              <input
                type="date"
                value={filters.since || ""}
                onChange={(e) => setFilters({ ...filters, since: e.target.value })}
                className="w-full rounded border border-white/10 bg-zinc-900 px-3 py-1.5 text-sm text-white outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Date range - Until */}
            <div>
              <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                <Calendar className="h-3.5 w-3.5" />
                Until
              </label>
              <input
                type="date"
                value={filters.until || ""}
                onChange={(e) => setFilters({ ...filters, until: e.target.value })}
                className="w-full rounded border border-white/10 bg-zinc-900 px-3 py-1.5 text-sm text-white outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Intent filter */}
            <div className="col-span-2">
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Commit Intent
              </label>
              <div className="flex flex-wrap gap-2">
                {["feature", "bugfix", "refactor", "security-fix", "performance", "docs", "test", "chore"].map(
                  (intent) => (
                    <button
                      key={intent}
                      onClick={() => {
                        const current = filters.intent || [];
                        const updated = current.includes(intent)
                          ? current.filter((i) => i !== intent)
                          : [...current, intent];
                        setFilters({ ...filters, intent: updated.length > 0 ? updated : undefined });
                      }}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                        filters.intent?.includes(intent)
                          ? "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/50"
                          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white"
                      }`}
                      type="button"
                    >
                      {intent}
                    </button>
                  ),
                )}
              </div>
            </div>

            {/* Risk level filter */}
            <div className="col-span-2">
              <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                Risk Level
              </label>
              <div className="flex gap-2">
                {["high", "medium", "low"].map((risk) => (
                  <button
                    key={risk}
                    onClick={() => {
                      const current = filters.risk || [];
                      const updated = current.includes(risk)
                        ? current.filter((r) => r !== risk)
                        : [...current, risk];
                      setFilters({ ...filters, risk: updated.length > 0 ? updated : undefined });
                    }}
                    className={`flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                      filters.risk?.includes(risk)
                        ? risk === "high"
                          ? "bg-red-500/20 text-red-300 ring-1 ring-red-500/50"
                          : risk === "medium"
                            ? "bg-yellow-500/20 text-yellow-300 ring-1 ring-yellow-500/50"
                            : "bg-green-500/20 text-green-300 ring-1 ring-green-500/50"
                        : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white"
                    }`}
                    type="button"
                  >
                    {risk.charAt(0).toUpperCase() + risk.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Special filters */}
            <div className="col-span-2 flex gap-3">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.breaking_only || false}
                  onChange={(e) =>
                    setFilters({ ...filters, breaking_only: e.target.checked || undefined })
                  }
                  className="h-4 w-4 rounded border-white/10 bg-zinc-900 text-cyan-500 focus:ring-2 focus:ring-cyan-500/50 focus:ring-offset-0"
                />
                <span className="text-xs text-zinc-300">Breaking changes only</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={filters.security_only || false}
                  onChange={(e) =>
                    setFilters({ ...filters, security_only: e.target.checked || undefined })
                  }
                  className="h-4 w-4 rounded border-white/10 bg-zinc-900 text-cyan-500 focus:ring-2 focus:ring-cyan-500/50 focus:ring-offset-0"
                />
                <span className="flex items-center gap-1.5 text-xs text-zinc-300">
                  <Shield className="h-3.5 w-3.5" />
                  Security-related only
                </span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Active filters display */}
      {hasActiveFilters() && !showFilters && (
        <div className="flex flex-wrap gap-2">
          {filters.intent?.map((intent) => (
            <span
              key={intent}
              className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300"
            >
              Intent: {intent}
              <button
                onClick={() => {
                  const updated = filters.intent?.filter((i) => i !== intent);
                  setFilters({ ...filters, intent: updated?.length ? updated : undefined });
                }}
                className="hover:text-cyan-100"
                type="button"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          {filters.risk?.map((risk) => (
            <span
              key={risk}
              className="inline-flex items-center gap-1.5 rounded-full bg-yellow-500/10 px-2.5 py-1 text-xs text-yellow-300"
            >
              Risk: {risk}
              <button
                onClick={() => {
                  const updated = filters.risk?.filter((r) => r !== risk);
                  setFilters({ ...filters, risk: updated?.length ? updated : undefined });
                }}
                className="hover:text-yellow-100"
                type="button"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          {filters.since && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 px-2.5 py-1 text-xs text-purple-300">
              Since: {filters.since}
              <button
                onClick={() => setFilters({ ...filters, since: undefined })}
                className="hover:text-purple-100"
                type="button"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
          {filters.until && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 px-2.5 py-1 text-xs text-purple-300">
              Until: {filters.until}
              <button
                onClick={() => setFilters({ ...filters, until: undefined })}
                className="hover:text-purple-100"
                type="button"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  );
};
