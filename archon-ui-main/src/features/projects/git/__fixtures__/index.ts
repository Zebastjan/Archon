/**
 * Frontend Test Fixtures for Git Integration
 *
 * These fixtures align with the backend test fixtures in:
 * python/tests/git_integration/fixtures/
 *
 * Each fixture represents a known git repository state that can be used
 * for both backend and frontend testing to ensure consistency.
 */

import type { Commit, GitFile, Repository } from "../types";

export interface GitTestFixture {
	name: string;
	repository: Partial<Repository>;
	commits: Commit[];
	files: GitFile[];
	defaultBranch: string;
}

/**
 * Simple Commits Fixture
 *
 * 3 commits, 1 branch, 3 files
 * - README.md
 * - config.json
 * - src/app.py
 *
 * Backend fixture: python/tests/git_integration/fixtures/simple-commits/
 */
export const simpleCommitsFixture: GitTestFixture = {
	name: "simple-commits",
	repository: {
		id: "fixture-simple-commits",
		repo_name: "simple-commits",
		default_branch: "main",
		current_head_sha: "1eac0cd85a172f2e03709f41dc47f5c4356b3bde",
	},
	commits: [
		{
			id: "commit-3",
			repo_id: "fixture-simple-commits",
			commit_sha: "1eac0cd85a172f2e03709f41dc47f5c4356b3bde",
			parent_shas: ["9c61b1ad15472197d0f0e0126596aa722aad1735"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Update README with features list",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-2",
			repo_id: "fixture-simple-commits",
			commit_sha: "9c61b1ad15472197d0f0e0126596aa722aad1735",
			parent_shas: ["9aebc994da52c9913be2898cb962e555b8397b0d"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Add application code and config",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-1",
			repo_id: "fixture-simple-commits",
			commit_sha: "9aebc994da52c9913be2898cb962e555b8397b0d",
			parent_shas: [],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Initial commit - add README",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
	],
	files: [
		{
			file_path: "README.md",
			file_name: "README.md",
			file_extension: "md",
			blob_sha: "226115db550e4ceebc4bc7d56c0fde60d13c248c",
			file_size: 143,
			language: "markdown",
			is_binary: false,
		},
		{
			file_path: "config.json",
			file_name: "config.json",
			file_extension: "json",
			blob_sha: "1b35511fd2b137defc0d3ba9fca14a81cd40d780",
			file_size: 51,
			language: "json",
			is_binary: false,
		},
		{
			file_path: "src/app.py",
			file_name: "app.py",
			file_extension: "py",
			blob_sha: "dea05ae20e80bec4a3bbe645cf4beb2343e0d4c9",
			file_size: 40,
			language: "python",
			is_binary: false,
		},
	],
	defaultBranch: "main",
};

/**
 * Multi-Branch Fixture
 *
 * 4 commits, 3 branches
 * - main: 3 commits (initial, feature-a, merge)
 * - feature-a: 2 commits
 * - feature-b: 2 commits
 *
 * Tests merge commits, branch operations
 *
 * Backend fixture: python/tests/git_integration/fixtures/multi-branch/
 */
export const multiBranchFixture: GitTestFixture = {
	name: "multi-branch",
	repository: {
		id: "fixture-multi-branch",
		repo_name: "multi-branch",
		default_branch: "main",
		current_head_sha: "4a2b3c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
	},
	commits: [
		{
			id: "commit-4",
			repo_id: "fixture-multi-branch",
			commit_sha: "4a2b3c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
			parent_shas: [
				"3b2a1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b",
				"2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b",
			],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Merge feature-a and feature-b into main",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-3a",
			repo_id: "fixture-multi-branch",
			commit_sha: "3b2a1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b",
			parent_shas: ["1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Add feature-a changes",
			branches: ["feature-a", "main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-3b",
			repo_id: "fixture-multi-branch",
			commit_sha: "2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b",
			parent_shas: ["1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Add feature-b changes",
			branches: ["feature-b", "main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-1",
			repo_id: "fixture-multi-branch",
			commit_sha: "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
			parent_shas: [],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Initial commit",
			branches: ["main", "feature-a", "feature-b"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
	],
	files: [
		{
			file_path: "README.md",
			file_name: "README.md",
			file_extension: "md",
			blob_sha: "abc123",
			file_size: 100,
			language: "markdown",
			is_binary: false,
		},
		{
			file_path: "feature-a.txt",
			file_name: "feature-a.txt",
			file_extension: "txt",
			blob_sha: "def456",
			file_size: 50,
			language: undefined,
			is_binary: false,
		},
		{
			file_path: "feature-b.txt",
			file_name: "feature-b.txt",
			file_extension: "txt",
			blob_sha: "ghi789",
			file_size: 50,
			language: undefined,
			is_binary: false,
		},
	],
	defaultBranch: "main",
};

/**
 * File Structure Fixture
 *
 * 3 commits, 13 files including binary files
 * Tests binary file detection (PNG, GIF correctly identified as binary)
 *
 * Backend fixture: python/tests/git_integration/fixtures/file-structure/
 */
export const fileStructureFixture: GitTestFixture = {
	name: "file-structure",
	repository: {
		id: "fixture-file-structure",
		repo_name: "file-structure",
		default_branch: "main",
		current_head_sha: "final-commit-sha",
	},
	commits: [
		{
			id: "commit-3",
			repo_id: "fixture-file-structure",
			commit_sha: "final-commit-sha",
			parent_shas: ["middle-commit-sha"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Add images directory with binary files",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-2",
			repo_id: "fixture-file-structure",
			commit_sha: "middle-commit-sha",
			parent_shas: ["initial-commit-sha"],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Add src directory with code files",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
		{
			id: "commit-1",
			repo_id: "fixture-file-structure",
			commit_sha: "initial-commit-sha",
			parent_shas: [],
			author_name: "Archon Test",
			author_email: "archon-tests@example.com",
			author_date: "2026-03-06T07:02:00Z",
			committer_name: "Archon Test",
			committer_email: "archon-tests@example.com",
			commit_date: "2026-03-06T07:02:00Z",
			message: "Initial commit - add README",
			branches: ["main"],
			tags: [],
			created_at: "2026-03-06T07:02:00Z",
		},
	],
	files: [
		{
			file_path: "README.md",
			file_name: "README.md",
			file_extension: "md",
			blob_sha: "sha-readme",
			file_size: 100,
			language: "markdown",
			is_binary: false,
		},
		{
			file_path: "package.json",
			file_name: "package.json",
			file_extension: "json",
			blob_sha: "sha-package",
			file_size: 200,
			language: "json",
			is_binary: false,
		},
		{
			file_path: "src/index.ts",
			file_name: "index.ts",
			file_extension: "ts",
			blob_sha: "sha-index",
			file_size: 150,
			language: "typescript",
			is_binary: false,
		},
		{
			file_path: "src/app.ts",
			file_name: "app.ts",
			file_extension: "ts",
			blob_sha: "sha-app",
			file_size: 300,
			language: "typescript",
			is_binary: false,
		},
		{
			file_path: "src/utils.ts",
			file_name: "utils.ts",
			file_extension: "ts",
			blob_sha: "sha-utils",
			file_size: 100,
			language: "typescript",
			is_binary: false,
		},
		{
			file_path: "src/components/Button.tsx",
			file_name: "Button.tsx",
			file_extension: "tsx",
			blob_sha: "sha-button",
			file_size: 250,
			language: "typescript",
			is_binary: false,
		},
		{
			file_path: "src/components/Input.tsx",
			file_name: "Input.tsx",
			file_extension: "tsx",
			blob_sha: "sha-input",
			file_size: 200,
			language: "typescript",
			is_binary: false,
		},
		{
			file_path: "styles/main.css",
			file_name: "main.css",
			file_extension: "css",
			blob_sha: "sha-css",
			file_size: 500,
			language: "css",
			is_binary: false,
		},
		{
			file_path: "images/logo.png",
			file_name: "logo.png",
			file_extension: "png",
			blob_sha: "sha-png",
			file_size: 10240,
			language: undefined,
			is_binary: true,
		},
		{
			file_path: "images/icon.png",
			file_name: "icon.png",
			file_extension: "png",
			blob_sha: "sha-icon-png",
			file_size: 5120,
			language: undefined,
			is_binary: true,
		},
		{
			file_path: "images/animated.gif",
			file_name: "animated.gif",
			file_extension: "gif",
			blob_sha: "sha-gif",
			file_size: 20480,
			language: undefined,
			is_binary: true,
		},
		{
			file_path: "docs/guide.md",
			file_name: "guide.md",
			file_extension: "md",
			blob_sha: "sha-guide",
			file_size: 800,
			language: "markdown",
			is_binary: false,
		},
		{
			file_path: "docs/api.md",
			file_name: "api.md",
			file_extension: "md",
			blob_sha: "sha-api",
			file_size: 1200,
			language: "markdown",
			is_binary: false,
		},
	],
	defaultBranch: "main",
};

/**
 * All available test fixtures
 */
export const gitTestFixtures = {
	simpleCommits: simpleCommitsFixture,
	multiBranch: multiBranchFixture,
	fileStructure: fileStructureFixture,
} as const;

/**
 * Get a fixture by name
 */
export function getFixture(name: keyof typeof gitTestFixtures): GitTestFixture {
	return gitTestFixtures[name];
}

/**
 * Get all fixture names
 */
export function getFixtureNames(): string[] {
	return Object.keys(gitTestFixtures);
}
