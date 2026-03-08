/**
 * Repository Header Component
 * Shows repository metadata with branch selector and sync button
 */

import { GitBranch, RefreshCw, Trash2, FlaskConical } from "lucide-react";
import { useState } from "react";
import { Button } from "@/features/ui/primitives";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/features/ui/primitives/select";
import { useDeleteRepository, useSyncCommits, useGitBranches } from "../hooks";
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
  const { data: branchesData } = useGitBranches(projectId);
  const branches = branchesData?.branches || [selectedBranch];

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
            {repository.metadata?.is_test_fixture && (
              <div className="mt-1 flex items-center gap-1">
                <span className="inline-flex items-center rounded-full bg-purple-500/20 px-2 py-0.5 text-xs font-medium text-purple-300">
                  <FlaskConical className="mr-1 h-3 w-3" />
                  Test Fixture: {repository.metadata.fixture_name}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Branch selector */}
          <Select
            value={selectedBranch}
            onValueChange={onBranchChange}
          >
            <SelectTrigger className="w-[200px]">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-cyan-400" />
                <SelectValue placeholder="Select branch" />
              </div>
            </SelectTrigger>
            <SelectContent>
              {branches.map((branch) => (
                <SelectItem key={branch} value={branch}>
                  <div className="flex items-center justify-between w-full">
                    <span>{branch}</span>
                    {branch === branchesData?.default_branch && (
                      <span className="ml-2 text-xs text-cyan-400">(default)</span>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

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
