/**
 * Commit Card Component
 * Individual commit item in the list
 */

import { Calendar, User } from "lucide-react";
import type { Commit } from "../types";
import { CompactClassificationBadge } from "./ClassificationBadges";

interface CommitCardProps {
  commit: Commit;
  isSelected: boolean;
  onClick: () => void;
}

export const CommitCard = ({ commit, isSelected, onClick }: CommitCardProps) => {
  const shortSha = commit.commit_sha.substring(0, 7);
  const commitDate = new Date(commit.commit_date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg border p-3 text-left transition-all ${
        isSelected
          ? "border-cyan-500/50 bg-cyan-500/10 shadow-lg shadow-cyan-500/20"
          : "border-white/10 bg-white/5 hover:border-cyan-500/30 hover:bg-white/10"
      }`}
      type="button"
    >
      {/* SHA and branches */}
      <div className="mb-2 flex items-center gap-2">
        <code className="rounded bg-zinc-800/50 px-2 py-0.5 text-xs font-mono text-cyan-400">
          {shortSha}
        </code>
        {commit.branches.length > 0 && (
          <span className="rounded bg-purple-500/20 px-2 py-0.5 text-xs text-purple-300">
            {commit.branches[0]}
          </span>
        )}
      </div>

      {/* Commit message */}
      <p className="mb-2 line-clamp-2 text-sm font-medium text-white">{commit.message}</p>

      {/* Classification Badges (if available) */}
      {commit.metadata && (
        <div className="mb-2">
          <CompactClassificationBadge classification={commit.metadata} />
        </div>
      )}

      {/* Metadata */}
      <div className="flex items-center gap-4 text-xs text-zinc-400">
        <div className="flex items-center gap-1">
          <User className="h-3 w-3" />
          <span>{commit.author_name}</span>
        </div>
        <div className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          <span>{commitDate}</span>
        </div>
      </div>
    </button>
  );
};
