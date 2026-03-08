/**
 * Tests for Repository Query Hooks
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
import { repositoryKeys } from "../useRepositoryQueries";

vi.mock("../../services/repositoryService", () => ({
	repositoryService: {
		getRepository: vi.fn(),
		getCommits: vi.fn(),
		getFileTree: vi.fn(),
		getFileContent: vi.fn(),
		initializeRepository: vi.fn(),
		deleteRepository: vi.fn(),
		syncCommits: vi.fn(),
	},
}));

vi.mock("@/features/shared/hooks/useToast", () => ({
	useToast: () => ({
		showToast: vi.fn(),
	}),
}));

vi.mock("@/features/shared/config/queryPatterns", () => ({
	DISABLED_QUERY_KEY: ["disabled"] as const,
	STALE_TIMES: {
		instant: 0,
		realtime: 3_000,
		frequent: 5_000,
		normal: 30_000,
		rare: 300_000,
		static: Number.POSITIVE_INFINITY,
	},
}));

describe("repositoryKeys", () => {
	it("should generate correct query keys", () => {
		expect(repositoryKeys.all).toEqual(["repository"]);
		expect(repositoryKeys.byProject("project-123")).toEqual(["projects", "project-123", "repository"]);
		expect(repositoryKeys.commits("project-123")).toEqual([
			"projects",
			"project-123",
			"repository",
			"commits",
			undefined,
		]);
		expect(repositoryKeys.commits("project-123", "main")).toEqual([
			"projects",
			"project-123",
			"repository",
			"commits",
			"main",
		]);
		expect(repositoryKeys.tree("project-123", "abc123")).toEqual([
			"projects",
			"project-123",
			"repository",
			"tree",
			"abc123",
			undefined,
		]);
		expect(repositoryKeys.tree("project-123", "abc123", "src/")).toEqual([
			"projects",
			"project-123",
			"repository",
			"tree",
			"abc123",
			"src/",
		]);
		expect(repositoryKeys.file("project-123", "abc123", "file.ts")).toEqual([
			"projects",
			"project-123",
			"repository",
			"file",
			"abc123",
			"file.ts",
		]);
	});
});

describe("useProjectRepository", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should fetch repository successfully", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useProjectRepository } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getRepository).mockResolvedValue(mockRepository);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useProjectRepository("project-123"), { wrapper });

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getRepository).toHaveBeenCalledWith("project-123");
		expect(result.current.data).toEqual(mockRepository);
	});

	it("should use DISABLED_QUERY_KEY when projectId is undefined", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useProjectRepository } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useProjectRepository(undefined), { wrapper });

		expect(result.current.isPending).toBe(true);
		expect(repositoryService.getRepository).not.toHaveBeenCalled();
	});

	it("should use normal stale time", async () => {
		const { useProjectRepository } = await import("../useRepositoryQueries");
		const { STALE_TIMES } = await import("@/features/shared/config/queryPatterns");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useProjectRepository("project-123"), { wrapper });

		expect(result.current.dataUpdatedAt).toBeLessThanOrEqual(Date.now());
	});
});

describe("useRepositoryCommits", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should fetch commits without options", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useRepositoryCommits } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getCommits).mockResolvedValue(mockCommitsPaginationResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useRepositoryCommits("project-123"), { wrapper });

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getCommits).toHaveBeenCalledWith("project-123", undefined);
		expect(result.current.data).toEqual(mockCommitsPaginationResponse);
	});

	it("should fetch commits with branch filter", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useRepositoryCommits } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getCommits).mockResolvedValue(mockCommitsPaginationResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(
			() =>
				useRepositoryCommits("project-123", {
					branch_name: "main",
					limit: 20,
					offset: 10,
				}),
			{ wrapper },
		);

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getCommits).toHaveBeenCalledWith("project-123", {
			branch_name: "main",
			limit: 20,
			offset: 10,
		});
		expect(result.current.data).toEqual(mockCommitsPaginationResponse);
	});

	it("should use DISABLED_QUERY_KEY when projectId is undefined", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useRepositoryCommits } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useRepositoryCommits(undefined), { wrapper });

		expect(result.current.isPending).toBe(true);
		expect(repositoryService.getCommits).not.toHaveBeenCalled();
	});
});

describe("useFileTree", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should fetch file tree successfully", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useFileTree } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getFileTree).mockResolvedValue(mockFileTreeResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileTree("project-123", "abc123"), { wrapper });

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getFileTree).toHaveBeenCalledWith("project-123", "abc123", undefined);
		expect(result.current.data).toEqual(mockFileTreeResponse);
	});

	it("should fetch file tree with path prefix", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useFileTree } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getFileTree).mockResolvedValue(mockFileTreeResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileTree("project-123", "abc123", "src/"), { wrapper });

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getFileTree).toHaveBeenCalledWith("project-123", "abc123", "src/");
	});

	it("should use DISABLED_QUERY_KEY when params missing", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useFileTree } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileTree("project-123", undefined), { wrapper });

		expect(result.current.isPending).toBe(true);
		expect(repositoryService.getFileTree).not.toHaveBeenCalled();
	});

	it("should use static stale time for immutable data", async () => {
		const { useFileTree } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileTree("project-123", "abc123"), { wrapper });

		expect(result.current.dataUpdatedAt).toBeLessThanOrEqual(Date.now());
	});
});

describe("useFileContent", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should fetch file content successfully", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useFileContent } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.getFileContent).mockResolvedValue(mockFileContentResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileContent("project-123", "abc123", "file.ts"), { wrapper });

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.getFileContent).toHaveBeenCalledWith("project-123", "abc123", "file.ts");
		expect(result.current.data).toEqual(mockFileContentResponse);
	});

	it("should use DISABLED_QUERY_KEY when params missing", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useFileContent } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileContent("project-123", "abc123", undefined), { wrapper });

		expect(result.current.isPending).toBe(true);
		expect(repositoryService.getFileContent).not.toHaveBeenCalled();
	});

	it("should use static stale time for immutable data", async () => {
		const { useFileContent } = await import("../useRepositoryQueries");

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useFileContent("project-123", "abc123", "file.ts"), { wrapper });

		expect(result.current.dataUpdatedAt).toBeLessThanOrEqual(Date.now());
	});
});

describe("useInitializeRepository", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should initialize repository and invalidate queries", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useInitializeRepository } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.initializeRepository).mockResolvedValue(mockRepositoryMetadata);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useInitializeRepository("project-123"), { wrapper });

		result.current.mutate(mockInitializeRequest);

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.initializeRepository).toHaveBeenCalledWith("project-123", mockInitializeRequest);
		expect(showToast).toHaveBeenCalledWith('Repository "test/repo" initialized successfully!', "success");
	});

	it("should show error toast on failure", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useInitializeRepository } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.initializeRepository).mockRejectedValue(new Error("Init failed"));

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useInitializeRepository("project-123"), { wrapper });

		result.current.mutate(mockInitializeRequest);

		await waitFor(() => expect(result.current.isError).toBe(true));

		expect(showToast).toHaveBeenCalledWith("Failed to initialize repository: Init failed", "error");
	});
});

describe("useDeleteRepository", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should delete repository and update cache", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useDeleteRepository } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.deleteRepository).mockResolvedValue();

		// Set initial data in cache
		queryClient.setQueryData(repositoryKeys.byProject("project-123"), mockRepository);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useDeleteRepository("project-123"), { wrapper });

		result.current.mutate();

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.deleteRepository).toHaveBeenCalledWith("project-123");
		expect(queryClient.getQueryData(repositoryKeys.byProject("project-123"))).toBeNull();
		expect(showToast).toHaveBeenCalledWith("Repository removed successfully!", "success");
	});

	it("should show error toast on failure", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useDeleteRepository } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.deleteRepository).mockRejectedValue(new Error("Delete failed"));

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useDeleteRepository("project-123"), { wrapper });

		result.current.mutate();

		await waitFor(() => expect(result.current.isError).toBe(true));

		expect(showToast).toHaveBeenCalledWith("Failed to delete repository: Delete failed", "error");
	});
});

describe("useSyncCommits", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
		vi.clearAllMocks();
	});

	it("should sync commits and invalidate queries", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useSyncCommits } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.syncCommits).mockResolvedValue(mockSyncCommitsResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useSyncCommits("project-123"), { wrapper });

		result.current.mutate(mockSyncCommitsRequest);

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.syncCommits).toHaveBeenCalledWith("project-123", mockSyncCommitsRequest);
		expect(showToast).toHaveBeenCalledWith('Synced 10 commits from "main"!', "success");
	});

	it("should sync commits without request body", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useSyncCommits } = await import("../useRepositoryQueries");

		vi.mocked(repositoryService.syncCommits).mockResolvedValue(mockSyncCommitsResponse);

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useSyncCommits("project-123"), { wrapper });

		result.current.mutate(undefined);

		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		expect(repositoryService.syncCommits).toHaveBeenCalledWith("project-123", undefined);
	});

	it("should show error toast on failure", async () => {
		const { repositoryService } = await import("../../services/repositoryService");
		const { useSyncCommits } = await import("../useRepositoryQueries");
		const { useToast } = await import("@/features/shared/hooks/useToast");

		const showToast = vi.fn();
		vi.mocked(useToast).mockReturnValue({ showToast });
		vi.mocked(repositoryService.syncCommits).mockRejectedValue(new Error("Sync failed"));

		const wrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);

		const { result } = renderHook(() => useSyncCommits("project-123"), { wrapper });

		result.current.mutate(mockSyncCommitsRequest);

		await waitFor(() => expect(result.current.isError).toBe(true));

		expect(showToast).toHaveBeenCalledWith("Failed to sync commits: Sync failed", "error");
	});
});
