/**
 * Git Tab Component
 * Main tab for git repository browsing within projects
 */

import { GitBranch, FileText, Tag, GitCompare } from "lucide-react";
import { useState } from "react";
import { InitializeRepositoryModal } from "./components/InitializeRepositoryModal";
import { CommitList } from "./components/CommitList";
import { FileTreeViewer } from "./components/FileTreeViewer";
import { RepositoryHeader } from "./components/RepositoryHeader";
import { ClassificationBadges } from "./components/ClassificationBadges";
import { DiffViewer } from "./components/DiffViewer";
import { useProjectRepository, useRepositoryCommits, useDiff } from "./hooks";

type ViewMode = "files" | "classification" | "compare";

interface GitTabProps {
  project?: {
    id: string;
    title: string;
  } | null;
}

export const GitTab = ({ project }: GitTabProps) => {
  const projectId = project?.id || "";

  // Fetch repository metadata
  const { data: repository, isLoading } = useProjectRepository(projectId);

  // UI state
  const [showInitModal, setShowInitModal] = useState(false);
  const [selectedCommitSha, setSelectedCommitSha] = useState<string | undefined>();
  const [selectedBranch, setSelectedBranch] = useState<string | undefined>();
  const [viewMode, setViewMode] = useState<ViewMode>("files");
  const [compareCommitSha, setCompareCommitSha] = useState<string | undefined>();

  // Fetch commits to get full metadata (for classification)
  const { data: commitsData } = useRepositoryCommits(projectId, {
    branch_name: selectedBranch || repository?.default_branch,
  });

  // Get selected commit details
  const selectedCommit = commitsData?.commits.find((c) => c.commit_sha === selectedCommitSha);

  // Fetch diff when in compare mode
  const { data: diffData } = useDiff(
    projectId,
    compareCommitSha,
    selectedCommitSha,
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-zinc-400">Loading repository...</div>
      </div>
    );
  }

  // Empty state - no repository initialized
  if (!repository) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/10 to-purple-500/10 backdrop-blur-xl">
          <GitBranch className="h-12 w-12 text-cyan-400" />
        </div>
        <div className="text-center">
          <h3 className="mb-2 text-lg font-medium text-white">No repository linked</h3>
          <p className="mb-6 max-w-md text-sm text-zinc-400">
            Link an existing Git repository to browse commits and explore your codebase directly in Archon.
          </p>
          <button
            onClick={() => setShowInitModal(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-500 px-6 py-3 text-sm font-medium text-white shadow-lg shadow-cyan-500/20 transition-all hover:shadow-cyan-500/30"
            type="button"
          >
            <GitBranch className="h-4 w-4" />
            Initialize Repository
          </button>
        </div>

        {showInitModal && (
          <InitializeRepositoryModal
            projectId={projectId}
            onClose={() => setShowInitModal(false)}
            onSuccess={(metadata) => {
              setSelectedBranch(metadata.default_branch);
              setShowInitModal(false);
            }}
          />
        )}
      </div>
    );
  }

  // Main two-panel layout
  return (
    <div className="flex h-full flex-col">
      {/* Repository header with branch selector and sync button */}
      <RepositoryHeader
        projectId={projectId}
        repository={repository}
        selectedBranch={selectedBranch || repository.default_branch}
        onBranchChange={setSelectedBranch}
      />

      {/* Two-panel layout: Commits (left) + Content (right) */}
      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        {/* Left panel - Commit list */}
        <div className="w-1/3 min-w-[300px] overflow-hidden">
          <CommitList
            projectId={projectId}
            branch={selectedBranch || repository.default_branch}
            selectedCommitSha={selectedCommitSha}
            onSelectCommit={(sha) => {
              setSelectedCommitSha(sha);
              // Auto-switch to classification view if commit has metadata
              const commit = commitsData?.commits.find((c) => c.commit_sha === sha);
              if (commit?.metadata && viewMode === "files") {
                setViewMode("classification");
              }
            }}
          />
        </div>

        {/* Right panel - Content viewer with mode toggle */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* View mode toggle */}
          <div className="mb-3 flex items-center justify-between">
            <div className="flex gap-1 rounded-lg bg-zinc-900/50 p-1">
              <button
                onClick={() => setViewMode("files")}
                className={`flex items-center gap-2 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === "files"
                    ? "bg-cyan-500/20 text-cyan-300"
                    : "text-zinc-400 hover:text-white"
                }`}
                type="button"
              >
                <FileText className="h-3.5 w-3.5" />
                Files
              </button>
              <button
                onClick={() => setViewMode("classification")}
                disabled={!selectedCommit?.metadata}
                className={`flex items-center gap-2 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === "classification"
                    ? "bg-purple-500/20 text-purple-300"
                    : selectedCommit?.metadata
                      ? "text-zinc-400 hover:text-white"
                      : "cursor-not-allowed text-zinc-600"
                }`}
                type="button"
              >
                <Tag className="h-3.5 w-3.5" />
                Classification
              </button>
              <button
                onClick={() => {
                  setViewMode("compare");
                  if (!compareCommitSha && selectedCommit?.parent_shas[0]) {
                    setCompareCommitSha(selectedCommit.parent_shas[0]);
                  }
                }}
                disabled={!selectedCommitSha}
                className={`flex items-center gap-2 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === "compare"
                    ? "bg-blue-500/20 text-blue-300"
                    : selectedCommitSha
                      ? "text-zinc-400 hover:text-white"
                      : "cursor-not-allowed text-zinc-600"
                }`}
                type="button"
              >
                <GitCompare className="h-3.5 w-3.5" />
                Compare
              </button>
            </div>

            {/* Compare mode: commit selector */}
            {viewMode === "compare" && selectedCommitSha && (
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <span>Comparing</span>
                <select
                  value={compareCommitSha || ""}
                  onChange={(e) => setCompareCommitSha(e.target.value)}
                  className="rounded border border-white/10 bg-zinc-900 px-2 py-1 text-xs text-white"
                >
                  <option value="">Select commit...</option>
                  {selectedCommit?.parent_shas.map((sha) => (
                    <option key={sha} value={sha}>
                      {sha.substring(0, 7)} (parent)
                    </option>
                  ))}
                  {commitsData?.commits
                    .filter((c) => c.commit_sha !== selectedCommitSha)
                    .slice(0, 10)
                    .map((c) => (
                      <option key={c.commit_sha} value={c.commit_sha}>
                        {c.commit_sha.substring(0, 7)} - {c.message.substring(0, 50)}
                      </option>
                    ))}
                </select>
                <span>→</span>
                <code className="rounded bg-cyan-500/20 px-2 py-1 text-cyan-300">
                  {selectedCommitSha.substring(0, 7)}
                </code>
              </div>
            )}
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-auto">
            {viewMode === "files" && (
              <FileTreeViewer
                projectId={projectId}
                commitSha={selectedCommitSha || repository.current_head_sha}
              />
            )}

            {viewMode === "classification" && selectedCommit?.metadata && (
              <div className="space-y-4">
                <div className="rounded-lg border border-white/10 bg-zinc-900/50 p-4">
                  <h3 className="mb-3 text-sm font-medium text-white">Classification Details</h3>
                  <ClassificationBadges classification={selectedCommit.metadata} compact={false} />

                  <div className="mt-4 space-y-2 text-sm">
                    <div className="flex items-start gap-2">
                      <span className="text-zinc-500">Reasoning:</span>
                      <span className="flex-1 text-zinc-300">{selectedCommit.metadata.reasoning}</span>
                    </div>
                    {selectedCommit.metadata.classification_model && (
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500">Model:</span>
                        <code className="text-xs text-zinc-400">{selectedCommit.metadata.classification_model}</code>
                      </div>
                    )}
                    {selectedCommit.metadata.classification_timestamp && (
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500">Classified:</span>
                        <span className="text-xs text-zinc-400">
                          {new Date(selectedCommit.metadata.classification_timestamp).toLocaleString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {viewMode === "classification" && !selectedCommit?.metadata && (
              <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-zinc-900/50 p-8 text-center">
                <div>
                  <Tag className="mx-auto mb-3 h-12 w-12 text-zinc-600" />
                  <p className="text-sm text-zinc-400">No classification data available for this commit</p>
                  <p className="mt-1 text-xs text-zinc-500">Use the classification API to analyze this commit</p>
                </div>
              </div>
            )}

            {viewMode === "compare" && diffData && (
              <DiffViewer diff={diffData} />
            )}

            {viewMode === "compare" && !compareCommitSha && (
              <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-zinc-900/50 p-8 text-center">
                <div>
                  <GitCompare className="mx-auto mb-3 h-12 w-12 text-zinc-600" />
                  <p className="text-sm text-zinc-400">Select a commit to compare with</p>
                </div>
              </div>
            )}

            {viewMode === "compare" && compareCommitSha && !diffData && (
              <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-zinc-900/50 p-8">
                <div className="text-sm text-zinc-400">Loading diff...</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
