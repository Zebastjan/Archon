/**
 * Tests for Repository Service
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "@/features/shared/api/apiClient";
import { repositoryService } from "../repositoryService";
import {
	mockCommitsPaginationResponse,
	mockFileContentResponse,
	mockFileTreeResponse,
	mockInitializeRequest,
	mockRepository,
	mockRepositoryMetadata,
	mockSyncCommitsRequest,
	mockSyncCommitsResponse,
} from "../../__tests__/mockData";

vi.mock("@/features/shared/api/apiClient", () => ({
	callAPIWithETag: vi.fn(),
}));

describe("repositoryService", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	const projectId = "project-123";

	describe("initializeRepository", () => {
		it("should initialize repository with branch_name", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockRepositoryMetadata);

			const result = await repositoryService.initializeRepository(projectId, mockInitializeRequest);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository`, {
				method: "POST",
				body: JSON.stringify(mockInitializeRequest),
			});
			expect(result).toEqual(mockRepositoryMetadata);
		});

		it("should initialize repository without branch_name", async () => {
			const requestWithoutBranch = {
				repo_path: "/path/to/repo",
			};

			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockRepositoryMetadata);

			const result = await repositoryService.initializeRepository(projectId, requestWithoutBranch);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository`, {
				method: "POST",
				body: JSON.stringify(requestWithoutBranch),
			});
			expect(result).toEqual(mockRepositoryMetadata);
		});

		it("should throw error on initialization failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("Initialization failed"));

			await expect(repositoryService.initializeRepository(projectId, mockInitializeRequest)).rejects.toThrow(
				"Initialization failed",
			);
		});
	});

	describe("getRepository", () => {
		it("should get repository successfully", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockRepository);

			const result = await repositoryService.getRepository(projectId);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository`);
			expect(result).toEqual(mockRepository);
		});

		it("should return null when repository does not exist", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(null);

			const result = await repositoryService.getRepository(projectId);

			expect(result).toBeNull();
		});

		it("should throw error on get failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("Get failed"));

			await expect(repositoryService.getRepository(projectId)).rejects.toThrow("Get failed");
		});
	});

	describe("deleteRepository", () => {
		it("should delete repository successfully", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(undefined);

			await repositoryService.deleteRepository(projectId);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository`, {
				method: "DELETE",
			});
		});

		it("should handle 404 error gracefully", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("Not found"));

			await expect(repositoryService.deleteRepository(projectId)).rejects.toThrow("Not found");
		});
	});

	describe("getCommits", () => {
		it("should get commits without options", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockCommitsPaginationResponse);

			const result = await repositoryService.getCommits(projectId);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository/commits`);
			expect(result).toEqual(mockCommitsPaginationResponse);
		});

		it("should get commits with all options", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockCommitsPaginationResponse);

			const result = await repositoryService.getCommits(projectId, {
				branch_name: "main",
				limit: 20,
				offset: 10,
			});

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/commits?branch_name=main&limit=20&offset=10`,
			);
			expect(result).toEqual(mockCommitsPaginationResponse);
		});

		it("should get commits with only branch_name", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockCommitsPaginationResponse);

			const result = await repositoryService.getCommits(projectId, {
				branch_name: "develop",
			});

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/commits?branch_name=develop`,
			);
			expect(result).toEqual(mockCommitsPaginationResponse);
		});

		it("should return empty commits array when no commits exist", async () => {
			const emptyResponse = {
				commits: [],
				pagination: {
					total: 0,
					limit: 50,
					offset: 0,
					has_more: false,
				},
			};

			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(emptyResponse);

			const result = await repositoryService.getCommits(projectId);

			expect(result).toEqual(emptyResponse);
		});

		it("should throw error on get commits failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("Fetch failed"));

			await expect(repositoryService.getCommits(projectId)).rejects.toThrow("Fetch failed");
		});
	});

	describe("syncCommits", () => {
		it("should sync commits with request body", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockSyncCommitsResponse);

			const result = await repositoryService.syncCommits(projectId, mockSyncCommitsRequest);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository/sync`, {
				method: "POST",
				body: JSON.stringify(mockSyncCommitsRequest),
			});
			expect(result).toEqual(mockSyncCommitsResponse);
		});

		it("should sync commits without request body", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockSyncCommitsResponse);

			const result = await repositoryService.syncCommits(projectId);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(`/api/projects/${projectId}/repository/sync`, {
				method: "POST",
				body: undefined,
			});
			expect(result).toEqual(mockSyncCommitsResponse);
		});

		it("should throw error on sync failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("Sync failed"));

			await expect(repositoryService.syncCommits(projectId, mockSyncCommitsRequest)).rejects.toThrow("Sync failed");
		});
	});

	describe("getFileTree", () => {
		it("should get file tree with commitSha only", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockFileTreeResponse);

			const commitSha = "abc123def456";
			const result = await repositoryService.getFileTree(projectId, commitSha);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/tree?commit_sha=${commitSha}`,
			);
			expect(result).toEqual(mockFileTreeResponse);
		});

		it("should get file tree with commitSha and pathPrefix", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockFileTreeResponse);

			const commitSha = "abc123def456";
			const pathPrefix = "src/components";
			const result = await repositoryService.getFileTree(projectId, commitSha, pathPrefix);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/tree?commit_sha=${commitSha}&path_prefix=${encodeURIComponent(pathPrefix)}`,
			);
			expect(result).toEqual(mockFileTreeResponse);
		});

		it("should throw error on get file tree failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("File tree failed"));

			await expect(repositoryService.getFileTree(projectId, "abc123")).rejects.toThrow("File tree failed");
		});
	});

	describe("getFileContent", () => {
		it("should get file content with proper encoding", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockFileContentResponse);

			const commitSha = "abc123def456";
			const filePath = "src/components/Button.tsx";
			const result = await repositoryService.getFileContent(projectId, commitSha, filePath);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/file?commit_sha=${commitSha}&file_path=${encodeURIComponent(filePath)}`,
			);
			expect(result).toEqual(mockFileContentResponse);
		});

		it("should encode special characters in file path", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockResolvedValue(mockFileContentResponse);

			const commitSha = "abc123def456";
			const filePath = "src/utils/special file (with spaces).ts";
			await repositoryService.getFileContent(projectId, commitSha, filePath);

			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				`/api/projects/${projectId}/repository/file?commit_sha=${commitSha}&file_path=${encodeURIComponent(filePath)}`,
			);
		});

		it("should throw error on get file content failure", async () => {
			vi.mocked(apiClient.callAPIWithETag).mockRejectedValue(new Error("File content failed"));

			await expect(repositoryService.getFileContent(projectId, "abc123", "file.ts")).rejects.toThrow(
				"File content failed",
			);
		});
	});
});
