/**
 * Repository Header Component
 * Shows repository metadata with branch selector and sync button
 */

import { GitBranch, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/features/ui/primitives";
import { useDeleteRepository, useSyncCommits } from "../hooks";
import type { Repository } from "../types";

interface RepositoryHeaderProps {
  projectId: string;
  repository: Repository;
  selectedBranch: string;
  onBranchChange: (branch: string) => void;
}

export const RepositoryHeader = ({
  projectId,
  repository,
  selectedBranch,
  onBranchChange,
}: RepositoryHeaderProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const syncMutation = useSyncCommits(projectId);
  const deleteMutation = useDeleteRepository(projectId);

  const handleSync = () => {
    syncMutation.mutate({ branch_name: selectedBranch });
  };

  const handleDelete = () => {
    if (showDeleteConfirm) {
      deleteMutation.mutate();
      setShowDeleteConfirm(false);
    } else {
      setShowDeleteConfirm(true);
      setTimeout(() => setShowDeleteConfirm(false), 3000);
    }
  };

  return (
    <div className="border-b border-white/10 bg-zinc-900/30 p-4">
      <div className="flex items-center justify-between">
        {/* Repository info */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/20 to-purple-500/20">
            <GitBranch className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="font-medium text-white">{repository.repo_name}</h2>
            <p className="text-sm text-zinc-400">{repository.repo_url}</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Branch selector - simplified for now */}
          <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-cyan-400" />
              <span className="text-sm text-white">{selectedBranch}</span>
            </div>
          </div>

          {/* Sync button */}
          <Button
            variant="ghost"
            onClick={handleSync}
            disabled={syncMutation.isPending}
            className="border-cyan-500/30"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
            Sync
          </Button>

          {/* Delete button */}
          <Button
            variant="ghost"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className={showDeleteConfirm ? "border-red-500/50 bg-red-500/10 text-red-400" : ""}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {showDeleteConfirm ? "Click to confirm" : "Remove"}
          </Button>
        </div>
      </div>
    </div>
  );
};
