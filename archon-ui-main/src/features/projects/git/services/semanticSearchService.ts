/**
 * Git Semantic Search Service
 * API client for semantic commit search operations
 */

import { callAPIWithETag } from "../../../shared/api/apiClient";

export interface CommitSearchFilters {
  repo_id?: string;
  branch?: string;
  since?: string; // ISO date string
  until?: string; // ISO date string
  intent?: string[]; // e.g., ["feature", "bugfix"]
  risk?: string[]; // e.g., ["high", "medium", "low"]
  author?: string;
  breaking_only?: boolean;
  security_only?: boolean;
}

export interface CommitSearchResult {
  type: string;
  commit_sha: string;
  commit_id: string;
  repo_id: string;
  message: string;
  author: string;
  author_email: string;
  commit_date: string;
  branches: string[];
  classification: {
    intent?: string;
    risk_level?: string;
    breaking_change?: boolean;
    security_relevant?: boolean;
    confidence?: number;
  } | null;
  similarity_score: number;
  embedding_dimension: number;
  diff_summary?: string;
  content: string;
}

export interface GitCommitSearchResponse {
  query: string;
  results: CommitSearchResult[];
  count: number;
  filters: CommitSearchFilters;
}

export interface GitAwareSearchRequest {
  query: string;
  source?: string;
  match_count?: number;
  include_git_commits?: boolean;
  git_match_count?: number;
  repo_id?: string;
  branch?: string;
}

export interface GitAwareSearchResponse {
  query: string;
  document_results: any[];
  git_results: CommitSearchResult[];
  document_count: number;
  git_count: number;
  total_count: number;
  search_mode: string;
  reranking_applied: boolean;
  include_git_context: boolean;
}

export interface FileHistoryRequest {
  file_path: string;
  repo_id: string;
  match_count?: number;
  branch?: string;
}

export interface FileHistoryResponse {
  file_path: string;
  repo_id: string;
  branch?: string;
  commits: CommitSearchResult[];
  count: number;
}

export interface CommitContextResponse {
  commit_sha: string;
  message: string;
  author: string;
  author_email: string;
  commit_date: string;
  branches: string[];
  classification: any;
  parent_shas: string[];
  files_changed: number;
  files: Array<{
    path: string;
    is_binary: boolean;
  }>;
}

export const semanticSearchService = {
  /**
   * Search commits semantically with optional filters
   */
  async searchCommits(
    query: string,
    filters: CommitSearchFilters = {},
    matchCount: number = 10,
  ): Promise<GitCommitSearchResponse> {
    try {
      const params = new URLSearchParams({
        query,
        match_count: matchCount.toString(),
      });

      if (filters.repo_id) params.append("repo_id", filters.repo_id);
      if (filters.branch) params.append("branch", filters.branch);
      if (filters.since) params.append("since", filters.since);
      if (filters.until) params.append("until", filters.until);
      if (filters.author) params.append("author", filters.author);
      if (filters.breaking_only) params.append("breaking_only", "true");
      if (filters.security_only) params.append("security_only", "true");

      // Handle array parameters
      if (filters.intent) {
        filters.intent.forEach((intent) => params.append("intent", intent));
      }
      if (filters.risk) {
        filters.risk.forEach((risk) => params.append("risk", risk));
      }

      const response = await callAPIWithETag<GitCommitSearchResponse>(
        `/api/rag/git/search?${params.toString()}`,
      );
      return response;
    } catch (error) {
      console.error("Failed to search commits:", error);
      throw error;
    }
  },

  /**
   * Combined document + Git commit search
   */
  async searchWithGitContext(
    request: GitAwareSearchRequest,
  ): Promise<GitAwareSearchResponse> {
    try {
      const response = await callAPIWithETag<GitAwareSearchResponse>(
        "/api/rag/search/git-aware",
        {
          method: "POST",
          body: JSON.stringify(request),
        },
      );
      return response;
    } catch (error) {
      console.error("Failed to search with Git context:", error);
      throw error;
    }
  },

  /**
   * Get commit history for a specific file
   */
  async getFileHistory(request: FileHistoryRequest): Promise<FileHistoryResponse> {
    try {
      const response = await callAPIWithETag<FileHistoryResponse>(
        "/api/rag/git/file-history",
        {
          method: "POST",
          body: JSON.stringify(request),
        },
      );
      return response;
    } catch (error) {
      console.error("Failed to get file history:", error);
      throw error;
    }
  },

  /**
   * Get detailed commit context
   */
  async getCommitContext(
    commitSha: string,
    repoId: string,
  ): Promise<CommitContextResponse> {
    try {
      const params = new URLSearchParams({ repo_id: repoId });
      const response = await callAPIWithETag<CommitContextResponse>(
        `/api/rag/git/commit/${commitSha}?${params.toString()}`,
      );
      return response;
    } catch (error) {
      console.error("Failed to get commit context:", error);
      throw error;
    }
  },
};
