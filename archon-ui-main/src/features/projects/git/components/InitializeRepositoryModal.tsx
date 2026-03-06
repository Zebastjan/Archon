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
  const [formData, setFormData] = useState({
    repoPath: "",
    branchName: "",
    initializeIfNeeded: false,
    createInitialCommit: false,
    initialCommitMessage: "Initial commit",
    gitAuthorName: "",
    gitAuthorEmail: "",
  });
  const [error, setError] = useState<string | null>(null);

  const initializeMutation = useInitializeRepository(projectId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.repoPath.trim()) {
      setError("Repository path is required");
      return;
    }

    try {
      const metadata = await initializeMutation.mutateAsync({
        repo_path: formData.repoPath.trim(),
        branch_name: formData.branchName.trim() || undefined,
        initialize_if_needed: formData.initializeIfNeeded,
        create_initial_commit: formData.createInitialCommit,
        initial_commit_message: formData.initialCommitMessage.trim() || undefined,
        git_author_name: formData.gitAuthorName.trim() || undefined,
        git_author_email: formData.gitAuthorEmail.trim() || undefined,
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
              value={formData.repoPath}
              onChange={(e) => setFormData((prev) => ({ ...prev, repoPath: e.target.value }))}
              placeholder="/repos/your-repo-name"
              className="w-full font-mono"
            />
            <p className="mt-1.5 text-xs text-gray-400">
              Enter container path (e.g., <code className="text-cyan-400">/repos/syllablaze</code>).
              Your <code className="text-gray-300">~/dev</code> directory is mounted at{" "}
              <code className="text-gray-300">/repos</code> in the container.
            </p>
          </div>

          <div>
            <label htmlFor="branch-name" className="mb-2 block text-sm font-medium text-zinc-300">
              Branch Name (Optional)
            </label>
            <Input
              id="branch-name"
              type="text"
              value={formData.branchName}
              onChange={(e) => setFormData((prev) => ({ ...prev, branchName: e.target.value }))}
              placeholder="main"
              className="w-full"
            />
            <p className="mt-1 text-xs text-zinc-500">Leave empty to auto-detect default branch</p>
          </div>

          {/* Git initialization checkbox */}
          <div className="flex items-center space-x-2 mt-3">
            <input
              type="checkbox"
              id="initializeIfNeeded"
              checked={formData.initializeIfNeeded}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, initializeIfNeeded: e.target.checked }))
              }
              className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
            />
            <label htmlFor="initializeIfNeeded" className="text-sm text-gray-300">
              Initialize as new Git repository if not already one
            </label>
          </div>

          {/* Conditional: Show commit options if initializing */}
          {formData.initializeIfNeeded && (
            <div className="mt-4 p-4 border border-gray-700 rounded-lg bg-gray-800/50">
              <p className="text-sm text-gray-300 font-medium mb-3">
                Initial Commit Options (Optional)
              </p>

              {/* Create initial commit toggle */}
              <div className="flex items-center space-x-2 mb-3">
                <input
                  type="checkbox"
                  id="createInitialCommit"
                  checked={formData.createInitialCommit}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, createInitialCommit: e.target.checked }))
                  }
                  className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
                />
                <label htmlFor="createInitialCommit" className="text-sm text-gray-400">
                  Create initial commit
                </label>
              </div>

              {/* Commit configuration (only if creating commit) */}
              {formData.createInitialCommit && (
                <div className="space-y-3 pl-6">
                  <div>
                    <label htmlFor="commitMessage" className="block text-sm text-gray-400 mb-1">
                      Commit Message
                    </label>
                    <Input
                      id="commitMessage"
                      value={formData.initialCommitMessage}
                      onChange={(e) =>
                        setFormData((prev) => ({ ...prev, initialCommitMessage: e.target.value }))
                      }
                      placeholder="Initial commit"
                      className="text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="authorName" className="block text-sm text-gray-400 mb-1">
                      Author Name (optional)
                    </label>
                    <Input
                      id="authorName"
                      value={formData.gitAuthorName}
                      onChange={(e) =>
                        setFormData((prev) => ({ ...prev, gitAuthorName: e.target.value }))
                      }
                      placeholder="Uses git config default"
                      className="text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="authorEmail" className="block text-sm text-gray-400 mb-1">
                      Author Email (optional)
                    </label>
                    <Input
                      id="authorEmail"
                      value={formData.gitAuthorEmail}
                      onChange={(e) =>
                        setFormData((prev) => ({ ...prev, gitAuthorEmail: e.target.value }))
                      }
                      placeholder="Uses git config default"
                      className="text-sm"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

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
