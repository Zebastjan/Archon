/**
 * Git Tab Component
 * Main tab for git repository browsing within projects
 */

import { GitBranch } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { InitializeRepositoryModal } from "./components/InitializeRepositoryModal";
import { CommitList } from "./components/CommitList";
import { FileTreeViewer } from "./components/FileTreeViewer";
import { RepositoryHeader } from "./components/RepositoryHeader";
import { useProjectRepository, repositoryKeys } from "./hooks";

interface GitTabProps {
  project?: {
    id: string;
    title: string;
  } | null;
}

export const GitTab = ({ project }: GitTabProps) => {
  const projectId = project?.id || "";
  const queryClient = useQueryClient();

  // Fetch repository metadata
  const { data: repository, isLoading } = useProjectRepository(projectId);

  // UI state
  const [showInitModal, setShowInitModal] = useState(false);
  const [selectedCommitSha, setSelectedCommitSha] = useState<string | undefined>();
  const [selectedBranch, setSelectedBranch] = useState<string | undefined>();

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
            onSuccess={async (metadata) => {
              // Wait for query to refetch before closing modal
              await queryClient.refetchQueries({
                queryKey: repositoryKeys.byProject(projectId)
              });
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

      {/* Two-panel layout: Commits (left) + File Tree (right) */}
      <div className="flex flex-1 gap-4 overflow-hidden p-4">
        {/* Left panel - Commit list */}
        <div className="w-1/3 min-w-[300px] overflow-hidden">
          <CommitList
            projectId={projectId}
            branch={selectedBranch || repository.default_branch}
            selectedCommitSha={selectedCommitSha}
            onSelectCommit={setSelectedCommitSha}
          />
        </div>

        {/* Right panel - File tree viewer */}
        <div className="flex-1 overflow-hidden">
          <FileTreeViewer
            projectId={projectId}
            commitSha={selectedCommitSha || repository.current_head_sha}
          />
        </div>
      </div>
    </div>
  );
};
