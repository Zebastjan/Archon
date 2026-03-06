/**
 * Commit List Component
 * Displays commit history in a scrollable list
 */

import { GitCommit, Search, RefreshCw } from "lucide-react";
import { useState, useEffect } from "react";
import { Input, Button } from "@/features/ui/primitives";
import { useRepositoryCommits } from "../hooks";
import type { Commit } from "../types";
import { CommitCard } from "./CommitCard";

interface CommitListProps {
  projectId: string;
  branch: string;
  selectedCommitSha?: string;
  onSelectCommit: (sha: string) => void;
}

export const CommitList = ({ projectId, branch, selectedCommitSha, onSelectCommit }: CommitListProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [allCommits, setAllCommits] = useState<Commit[]>([]);
  const COMMITS_PER_PAGE = 50;

  // Reset offset and accumulated commits when branch changes
  useEffect(() => {
    setOffset(0);
    setAllCommits([]);
  }, [branch]);

  // Fetch commits
  const { data, isLoading, isFetching } = useRepositoryCommits(projectId, {
    branch_name: branch,
    limit: COMMITS_PER_PAGE,
    offset: offset,
  });

  // Accumulate commits as pages load
  useEffect(() => {
    if (data?.commits) {
      setAllCommits((prev) => (offset === 0 ? data.commits : [...prev, ...data.commits]));
    }
  }, [data, offset]);

  const commits = allCommits;
  const filteredCommits = commits.filter((commit: Commit) =>
    searchQuery
      ? commit.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        commit.commit_sha.toLowerCase().includes(searchQuery.toLowerCase()) ||
        commit.author_name.toLowerCase().includes(searchQuery.toLowerCase())
      : true,
  );

  return (
    <div className="flex h-full flex-col rounded-lg border border-white/10 bg-zinc-900/50 backdrop-blur-xl">
      {/* Header */}
      <div className="border-b border-white/10 p-4">
        <div className="mb-3 flex items-center gap-2">
          <GitCommit className="h-5 w-5 text-cyan-400" />
          <h3 className="font-medium text-white">Commits</h3>
          <span className="ml-auto text-sm text-zinc-400">
            {data?.pagination?.total || 0} commits
          </span>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input
            type="text"
            placeholder="Search commits..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9"
          />
        </div>
      </div>

      {/* Commit list */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading && (
          <div className="flex h-32 items-center justify-center">
            <div className="text-sm text-zinc-400">Loading commits...</div>
          </div>
        )}

        {!isLoading && filteredCommits.length === 0 && (
          <div className="flex h-32 items-center justify-center">
            <div className="text-sm text-zinc-400">
              {searchQuery ? "No commits found" : "No commits available"}
            </div>
          </div>
        )}

        {!isLoading && filteredCommits.length > 0 && (
          <div className="space-y-2">
            {filteredCommits.map((commit) => (
              <CommitCard
                key={commit.id}
                commit={commit}
                isSelected={commit.commit_sha === selectedCommitSha}
                onClick={() => onSelectCommit(commit.commit_sha)}
              />
            ))}
          </div>
        )}

        {/* Load More button */}
        {data?.pagination?.has_more && !isLoading && (
          <div className="mt-3 px-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOffset(offset + COMMITS_PER_PAGE)}
              disabled={isFetching}
              className="w-full border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
            >
              {isFetching ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                `Load More (${(data.pagination.total || 0) - commits.length} remaining)`
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
