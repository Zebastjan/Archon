/**
 * Git Repository Query Hooks
 * TanStack Query hooks for git repository operations
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DISABLED_QUERY_KEY, STALE_TIMES } from "@/features/shared/config/queryPatterns";
import { useToast } from "@/features/shared/hooks/useToast";
import { repositoryService } from "../services";
import type {
  BranchesResponse,
  CommitsPaginationResponse,
  FileContentResponse,
  FileTreeResponse,
  InitializeRepositoryRequest,
  Repository,
  RepositoryMetadata,
  SyncCommitsRequest,
} from "../types";

// Query keys factory
export const repositoryKeys = {
  all: ["repository"] as const,
  byProject: (projectId: string) => ["projects", projectId, "repository"] as const,
  branches: (projectId: string) => ["projects", projectId, "repository", "branches"] as const,
  commits: (projectId: string, branch?: string) =>
    ["projects", projectId, "repository", "commits", branch] as const,
  tree: (projectId: string, commitSha: string, pathPrefix?: string) =>
    ["projects", projectId, "repository", "tree", commitSha, pathPrefix] as const,
  file: (projectId: string, commitSha: string, filePath: string) =>
    ["projects", projectId, "repository", "file", commitSha, filePath] as const,
};

/**
 * Get repository metadata for a project
 */
export function useProjectRepository(projectId: string | undefined) {
  return useQuery<Repository | null>({
    queryKey: projectId ? repositoryKeys.byProject(projectId) : DISABLED_QUERY_KEY,
    queryFn: () => (projectId ? repositoryService.getRepository(projectId) : Promise.reject("No project ID")),
    enabled: !!projectId,
    staleTime: STALE_TIMES.normal,
  });
}

/**
 * Get all branches in the repository
 */
export function useRepositoryBranches(projectId: string | undefined) {
  return useQuery<BranchesResponse>({
    queryKey: projectId ? repositoryKeys.branches(projectId) : DISABLED_QUERY_KEY,
    queryFn: () => (projectId ? repositoryService.getBranches(projectId) : Promise.reject("No project ID")),
    enabled: !!projectId,
    staleTime: STALE_TIMES.normal,
  });
}

/**
 * Get commit history for repository
 */
export function useRepositoryCommits(
  projectId: string | undefined,
  options?: {
    branch_name?: string;
    limit?: number;
    offset?: number;
  },
) {
  return useQuery<CommitsPaginationResponse>({
    queryKey: projectId ? repositoryKeys.commits(projectId, options?.branch_name) : DISABLED_QUERY_KEY,
    queryFn: () =>
      projectId ? repositoryService.getCommits(projectId, options) : Promise.reject("No project ID"),
    enabled: !!projectId,
    staleTime: STALE_TIMES.normal,
  });
}

/**
 * Get file tree at a specific commit
 */
export function useFileTree(
  projectId: string | undefined,
  commitSha: string | undefined,
  pathPrefix?: string,
) {
  return useQuery<FileTreeResponse>({
    queryKey:
      projectId && commitSha
        ? repositoryKeys.tree(projectId, commitSha, pathPrefix)
        : DISABLED_QUERY_KEY,
    queryFn: () =>
      projectId && commitSha
        ? repositoryService.getFileTree(projectId, commitSha, pathPrefix)
        : Promise.reject("Missing project ID or commit SHA"),
    enabled: !!projectId && !!commitSha,
    staleTime: STALE_TIMES.static, // File trees don't change for a given commit
  });
}

/**
 * Get file content at a specific commit
 */
export function useFileContent(
  projectId: string | undefined,
  commitSha: string | undefined,
  filePath: string | undefined,
) {
  return useQuery<FileContentResponse>({
    queryKey:
      projectId && commitSha && filePath
        ? repositoryKeys.file(projectId, commitSha, filePath)
        : DISABLED_QUERY_KEY,
    queryFn: () =>
      projectId && commitSha && filePath
        ? repositoryService.getFileContent(projectId, commitSha, filePath)
        : Promise.reject("Missing required parameters"),
    enabled: !!projectId && !!commitSha && !!filePath,
    staleTime: STALE_TIMES.static, // File content doesn't change for a given commit
  });
}

/**
 * Initialize repository mutation
 */
export function useInitializeRepository(projectId: string) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation<RepositoryMetadata, Error, InitializeRepositoryRequest>({
    mutationFn: (request: InitializeRepositoryRequest) =>
      repositoryService.initializeRepository(projectId, request),
    onSuccess: (data: RepositoryMetadata) => {
      // Invalidate repository query to refetch metadata
      // Use refetchType: 'all' to ensure refetch happens even if no active observer
      queryClient.invalidateQueries({
        queryKey: repositoryKeys.byProject(projectId),
        refetchType: 'all'
      });
      showToast(`Repository "${data.repo_name}" initialized successfully!`, "success");
    },
    onError: (error: Error) => {
      const errorMessage = error instanceof Error ? error.message : String(error);
      showToast(`Failed to initialize repository: ${errorMessage}`, "error");
    },
  });
}

/**
 * Delete repository mutation
 */
export function useDeleteRepository(projectId: string) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation<void, Error>({
    mutationFn: () => repositoryService.deleteRepository(projectId),
    onSuccess: () => {
      // Clear repository data from cache
      queryClient.setQueryData(repositoryKeys.byProject(projectId), null);
      // Invalidate commits query
      queryClient.invalidateQueries({ queryKey: repositoryKeys.commits(projectId) });
      showToast("Repository removed successfully!", "success");
    },
    onError: (error: Error) => {
      const errorMessage = error instanceof Error ? error.message : String(error);
      showToast(`Failed to delete repository: ${errorMessage}`, "error");
    },
  });
}

/**
 * Sync commits mutation
 */
export function useSyncCommits(projectId: string) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation<
    {
      commit_count: number;
      branch: string;
    },
    Error,
    SyncCommitsRequest | undefined
  >({
    mutationFn: (request?: SyncCommitsRequest) => repositoryService.syncCommits(projectId, request),
    onSuccess: (data: { commit_count: number; branch: string }) => {
      // Invalidate commits query to refetch
      queryClient.invalidateQueries({ queryKey: repositoryKeys.commits(projectId) });
      // Invalidate repository metadata (last_crawled_at, etc.)
      queryClient.invalidateQueries({ queryKey: repositoryKeys.byProject(projectId) });
      showToast(`Synced ${data.commit_count} commits from "${data.branch}"!`, "success");
    },
    onError: (error: Error) => {
      const errorMessage = error instanceof Error ? error.message : String(error);
      showToast(`Failed to sync commits: ${errorMessage}`, "error");
    },
  });
}
