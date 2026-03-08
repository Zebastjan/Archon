/**
 * Git Repository Types
 *
 * Type definitions for git repository integration
 */

export interface Repository {
  id: string;
  source_id: string;
  repo_url: string;
  repo_name: string;
  owner?: string;
  default_branch: string;
  current_head_sha: string;
  last_crawled_at?: string;
  crawl_status: "pending" | "crawling" | "completed" | "failed";
  crawl_error?: Record<string, unknown>;
  config?: RepositoryConfig;
  metadata?: {
    is_test_fixture?: boolean;
    fixture_name?: string;
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
}

export interface CommitClassification {
  intent: "feature" | "bugfix" | "refactor" | "security-fix" | "performance" | "docs" | "test" | "chore";
  risk_level: "high" | "medium" | "low";
  api_breaking: boolean;
  security_relevant: boolean;
  performance_impact: "high" | "medium" | "low" | "none";
  test_coverage: "full" | "partial" | "none";
  confidence: number;
  reasoning: string;
  classification_model?: string;
  classification_timestamp?: string;
}

export interface Commit {
  id: string;
  repo_id: string;
  commit_sha: string;
  parent_shas: string[];
  author_name: string;
  author_email?: string;
  author_date: string;
  committer_name: string;
  committer_email?: string;
  commit_date: string;
  message: string;
  branches: string[];
  tags: string[];
  metadata?: CommitClassification;
  created_at: string;
}

export interface GitFile {
  file_path: string;
  file_name: string;
  file_extension: string;
  blob_sha: string;
  file_size: number;
  language?: string;
  is_binary: boolean;
}

export interface RepositoryConfig {
  branch_filters?: string[];
  file_patterns?: string[];
  max_file_size?: number;
}

export interface InitializeRepositoryRequest {
  repo_path: string;
  branch_name?: string;
  config?: RepositoryConfig;
}

export interface SyncCommitsRequest {
  branch_name?: string;
  max_commits?: number;
}

export interface CommitsPaginationResponse {
  commits: Commit[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
}

export interface FileTreeResponse {
  files: GitFile[];
  file_count: number;
  commit_sha: string;
}

export interface FileContentResponse {
  content: string;
  file_path: string;
  file_size: number;
  blob_sha: string;
  language?: string;
  commit_sha: string;
}

export interface RepositoryMetadata {
  repo_id: string;
  repo_name: string;
  default_branch: string;
  current_head_sha: string;
}
