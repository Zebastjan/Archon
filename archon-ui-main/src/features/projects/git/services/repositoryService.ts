/**
 * Git Repository Service
 * API client for git repository operations
 */

import { callAPIWithETag } from "../../../shared/api/apiClient";
import type {
  CommitsPaginationResponse,
  FileContentResponse,
  FileTreeResponse,
  InitializeRepositoryRequest,
  Repository,
  RepositoryMetadata,
  SyncCommitsRequest,
} from "../types";

export interface GitTestFixtureInfo {
  name: string;
  path: string;
  commit_count: number;
  branch_count: number;
  file_count: number;
  has_binary_files: boolean;
}

export interface GitTestFixtureCommit {
  sha: string;
  author_name: string;
  author_email: string;
  date: string;
  message: string;
}

export interface GitTestFixtureFile {
  path: string;
  sha: string;
  size: number;
  type: string;
  is_binary: boolean;
}

export interface GitTestFixtureDetails {
  name: string;
  branches: string[];
  commits: GitTestFixtureCommit[];
  files: GitTestFixtureFile[];
  default_branch: string;
}

export const repositoryService = {
  /**
   * Initialize a git repository for a project
   */
  async initializeRepository(
    projectId: string,
    request: InitializeRepositoryRequest,
  ): Promise<RepositoryMetadata> {
    try {
      const response = await callAPIWithETag<RepositoryMetadata>(
        `/api/projects/${projectId}/repository`,
        {
          method: "POST",
          body: JSON.stringify(request),
        },
      );
      return response;
    } catch (error) {
      console.error(`Failed to initialize repository for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Get repository metadata for a project
   */
  async getRepository(projectId: string): Promise<Repository | null> {
    try {
      const response = await callAPIWithETag<Repository | null>(
        `/api/projects/${projectId}/repository`,
      );
      return response;
    } catch (error) {
      console.error(`Failed to get repository for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Delete repository and all associated data
   */
  async deleteRepository(projectId: string): Promise<void> {
    try {
      await callAPIWithETag(`/api/projects/${projectId}/repository`, {
        method: "DELETE",
      });
    } catch (error) {
      console.error(`Failed to delete repository for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Get commit history for repository
   */
  async getCommits(
    projectId: string,
    options?: {
      branch_name?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<CommitsPaginationResponse> {
    try {
      const params = new URLSearchParams();
      if (options?.branch_name) params.append("branch_name", options.branch_name);
      if (options?.limit !== undefined) params.append("limit", options.limit.toString());
      if (options?.offset !== undefined) params.append("offset", options.offset.toString());

      const queryString = params.toString() ? `?${params.toString()}` : "";
      const response = await callAPIWithETag<CommitsPaginationResponse>(
        `/api/projects/${projectId}/repository/commits${queryString}`,
      );
      return response;
    } catch (error) {
      console.error(`Failed to get commits for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Sync commits from git repository to database
   */
  async syncCommits(projectId: string, request?: SyncCommitsRequest): Promise<{
    commit_count: number;
    branch: string;
  }> {
    try {
      const response = await callAPIWithETag<{
        commit_count: number;
        branch: string;
      }>(`/api/projects/${projectId}/repository/sync`, {
        method: "POST",
        body: request ? JSON.stringify(request) : undefined,
      });
      return response;
    } catch (error) {
      console.error(`Failed to sync commits for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Get file tree at a specific commit
   */
  async getFileTree(
    projectId: string,
    commitSha: string,
    pathPrefix?: string,
  ): Promise<FileTreeResponse> {
    try {
      const params = new URLSearchParams({ commit_sha: commitSha });
      if (pathPrefix) params.append("path_prefix", pathPrefix);

      const response = await callAPIWithETag<FileTreeResponse>(
        `/api/projects/${projectId}/repository/tree?${params.toString()}`,
      );
      return response;
    } catch (error) {
      console.error(`Failed to get file tree for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * Get file content at a specific commit
   */
  async getFileContent(
    projectId: string,
    commitSha: string,
    filePath: string,
  ): Promise<FileContentResponse> {
    try {
      const params = new URLSearchParams({
        commit_sha: commitSha,
        file_path: filePath,
      });

      const response = await callAPIWithETag<FileContentResponse>(
        `/api/projects/${projectId}/repository/file?${params.toString()}`,
      );
      return response;
    } catch (error) {
      console.error(`Failed to get file content for project ${projectId}:`, error);
      throw error;
    }
  },

  /**
   * List all available git test fixtures
   */
  async listGitTestFixtures(): Promise<GitTestFixtureInfo[]> {
    try {
      const response = await callAPIWithETag<GitTestFixtureInfo[]>(
        "/api/dev/git-test-fixtures",
      );
      return response;
    } catch (error) {
      console.error("Failed to list git test fixtures:", error);
      throw error;
    }
  },

  /**
   * Get details of a specific git test fixture
   */
  async getGitTestFixture(fixtureName: string): Promise<GitTestFixtureDetails> {
    try {
      const response = await callAPIWithETag<GitTestFixtureDetails>(
        `/api/dev/git-test-fixtures/${fixtureName}`,
      );
      return response;
    } catch (error) {
      console.error(`Failed to get git test fixture ${fixtureName}:`, error);
      throw error;
    }
  },
};
