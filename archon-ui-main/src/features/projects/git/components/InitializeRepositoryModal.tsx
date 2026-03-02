/**
 * Initialize Repository Modal
 * Modal for linking an existing Git repository to a project
 */

import { AlertCircle, GitBranch, X } from "lucide-react";
import { useState } from "react";
import { Button, Input } from "@/features/ui/primitives";
import { useInitializeRepository } from "../hooks";
import type { RepositoryMetadata } from "../types";

interface InitializeRepositoryModalProps {
  projectId: string;
  onClose: () => void;
  onSuccess: (metadata: RepositoryMetadata) => void;
}

export const InitializeRepositoryModal = ({
  projectId,
  onClose,
  onSuccess,
}: InitializeRepositoryModalProps) => {
  const [repoPath, setRepoPath] = useState("");
  const [branchName, setbranchName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const initializeMutation = useInitializeRepository(projectId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!repoPath.trim()) {
      setError("Repository path is required");
      return;
    }

    try {
      const metadata = await initializeMutation.mutateAsync({
        repo_path: repoPath.trim(),
        branch_name: branchName.trim() || undefined,
      });
      onSuccess(metadata);
    } catch (err) {
      // Error is already handled by the mutation's onError
      // But we can show additional context in the modal
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-white/10 bg-zinc-900/90 p-6 shadow-2xl backdrop-blur-xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/20 to-purple-500/20">
              <GitBranch className="h-5 w-5 text-cyan-400" />
            </div>
            <h2 className="text-lg font-medium text-white">Initialize Repository</h2>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 transition-colors hover:text-white"
            type="button"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="repo-path" className="mb-2 block text-sm font-medium text-zinc-300">
              Repository Path
            </label>
            <Input
              id="repo-path"
              type="text"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="/path/to/your/repository"
              className="w-full"
            />
            <p className="mt-1 text-xs text-zinc-500">
              Full path to an existing Git repository on your filesystem
            </p>
          </div>

          <div>
            <label htmlFor="branch-name" className="mb-2 block text-sm font-medium text-zinc-300">
              Branch Name (Optional)
            </label>
            <Input
              id="branch-name"
              type="text"
              value={branchName}
              onChange={(e) => setbranchName(e.target.value)}
              placeholder="main"
              className="w-full"
            />
            <p className="mt-1 text-xs text-zinc-500">Leave empty to auto-detect default branch</p>
          </div>

          {/* Error message */}
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={onClose} type="button">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={initializeMutation.isPending}
              className="bg-gradient-to-r from-cyan-500 to-purple-500"
            >
              {initializeMutation.isPending ? "Initializing..." : "Initialize"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
