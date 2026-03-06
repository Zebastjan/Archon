/**
 * Shared Mock Data for Git Integration Tests
 *
 * Centralized test fixtures and factory functions used across all Git integration tests.
 */

import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import type {
	Commit,
	CommitsPaginationResponse,
	FileContentResponse,
	FileTreeResponse,
	GitFile,
	InitializeRepositoryRequest,
	Repository,
	RepositoryMetadata,
	SyncCommitsRequest,
} from "../types";

/**
 * Mock Repository
 */
export const mockRepository: Repository = {
	id: "repo-123",
	source_id: "source-456",
	repo_url: "https://github.com/test/repo",
	repo_name: "test/repo",
	owner: "test",
	default_branch: "main",
	current_head_sha: "abc123def456",
	last_crawled_at: "2025-01-15T10:00:00Z",
	crawl_status: "completed",
	crawl_error: undefined,
	config: {
		branch_filters: ["main", "develop"],
		file_patterns: ["*.ts", "*.tsx"],
		max_file_size: 1024000,
	},
	created_at: "2025-01-10T08:00:00Z",
	updated_at: "2025-01-15T10:00:00Z",
};

/**
 * Mock Commit
 */
export const mockCommit: Commit = {
	id: "commit-789",
	repo_id: "repo-123",
	commit_sha: "abc123def456",
	parent_shas: ["parent1sha", "parent2sha"],
	author_name: "John Doe",
	author_email: "john@example.com",
	author_date: "2025-01-15T09:00:00Z",
	committer_name: "John Doe",
	committer_email: "john@example.com",
	commit_date: "2025-01-15T09:00:00Z",
	message: "Add new feature to improve user experience",
	branches: ["main", "feature/new-feature"],
	tags: ["v1.0.0"],
	created_at: "2025-01-15T09:00:00Z",
};

/**
 * Mock GitFile (non-binary TypeScript file)
 */
export const mockGitFile: GitFile = {
	file_path: "src/components/Button.tsx",
	file_name: "Button.tsx",
	file_extension: "tsx",
	blob_sha: "blob123",
	file_size: 2048,
	language: "typescript",
	is_binary: false,
};

/**
 * Mock Binary File
 */
export const mockBinaryFile: GitFile = {
	file_path: "assets/logo.png",
	file_name: "logo.png",
	file_extension: "png",
	blob_sha: "blobpng456",
	file_size: 102400,
	language: undefined,
	is_binary: true,
};

/**
 * Mock Commits Pagination Response
 */
export const mockCommitsPaginationResponse: CommitsPaginationResponse = {
	commits: [
		mockCommit,
		{
			...mockCommit,
			id: "commit-790",
			commit_sha: "def456ghi789",
			message: "Fix bug in login flow",
			author_name: "Jane Smith",
			author_email: "jane@example.com",
			branches: ["main"],
			tags: [],
		},
	],
	pagination: {
		total: 2,
		limit: 50,
		offset: 0,
		has_more: false,
	},
};

/**
 * Mock File Tree Response
 */
export const mockFileTreeResponse: FileTreeResponse = {
	files: [mockGitFile, mockBinaryFile],
	file_count: 2,
	commit_sha: "abc123def456",
};

/**
 * Mock File Content Response
 */
export const mockFileContentResponse: FileContentResponse = {
	content: 'export const Button = () => <button>Click me</button>;',
	file_path: "src/components/Button.tsx",
	file_size: 2048,
	blob_sha: "blob123",
	language: "typescript",
	commit_sha: "abc123def456",
};

/**
 * Mock Repository Metadata
 */
export const mockRepositoryMetadata: RepositoryMetadata = {
	repo_id: "repo-123",
	repo_name: "test/repo",
	default_branch: "main",
	current_head_sha: "abc123def456",
};

/**
 * Factory: Create Mock Commit with overrides
 */
export function createMockCommit(overrides?: Partial<Commit>): Commit {
	return {
		...mockCommit,
		...overrides,
	};
}

/**
 * Factory: Create Mock GitFile with overrides
 */
export function createMockFile(overrides?: Partial<GitFile>): GitFile {
	return {
		...mockGitFile,
		...overrides,
	};
}

/**
 * Factory: Create Mock Mutation return value
 *
 * Used for mocking TanStack Query mutation hooks like useInitializeRepository
 */
export function createMockMutation<TData = unknown, TVariables = unknown>(
	overrides?: Partial<UseMutationResult<TData, Error, TVariables>>,
): UseMutationResult<TData, Error, TVariables> {
	return {
		mutate: vi.fn(),
		mutateAsync: vi.fn(),
		reset: vi.fn(),
		isPending: false,
		isIdle: true,
		isSuccess: false,
		isError: false,
		data: undefined,
		error: null,
		variables: undefined,
		context: undefined,
		status: "idle",
		failureCount: 0,
		failureReason: null,
		submittedAt: 0,
		isPaused: false,
		...overrides,
	} as UseMutationResult<TData, Error, TVariables>;
}

/**
 * Factory: Create Mock Query return value
 *
 * Used for mocking TanStack Query query hooks like useProjectRepository
 */
export function createMockQuery<TData = unknown>(
	overrides?: Partial<UseQueryResult<TData, Error>>,
): UseQueryResult<TData, Error> {
	return {
		data: undefined,
		error: null,
		isLoading: false,
		isSuccess: false,
		isError: false,
		isFetching: false,
		isRefetching: false,
		isPending: false,
		isLoadingError: false,
		isRefetchError: false,
		isStale: false,
		status: "pending",
		fetchStatus: "idle",
		dataUpdatedAt: 0,
		errorUpdatedAt: 0,
		failureCount: 0,
		failureReason: null,
		errorUpdateCount: 0,
		isFetched: false,
		isFetchedAfterMount: false,
		isPlaceholderData: false,
		isPaused: false,
		refetch: vi.fn(),
		...overrides,
	} as UseQueryResult<TData, Error>;
}

/**
 * Mock Initialize Repository Request
 */
export const mockInitializeRequest: InitializeRepositoryRequest = {
	repo_path: "/path/to/repo",
	branch_name: "main",
	config: {
		branch_filters: ["main"],
		file_patterns: ["*.ts"],
	},
};

/**
 * Mock Sync Commits Request
 */
export const mockSyncCommitsRequest: SyncCommitsRequest = {
	branch_name: "main",
	max_commits: 100,
};

/**
 * Mock Sync Commits Response
 */
export const mockSyncCommitsResponse = {
	commit_count: 10,
	branch: "main",
};
