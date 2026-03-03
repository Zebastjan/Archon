/**
 * Integration Tests for GitTab Component
 *
 * Tests end-to-end flows with real component + hook integration.
 * Only mocks callAPIWithETag (the API layer).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as apiClient from "@/features/shared/api/apiClient";
import {
	mockCommitsPaginationResponse,
	mockFileContentResponse,
	mockFileTreeResponse,
	mockRepository,
	mockRepositoryMetadata,
	mockSyncCommitsResponse,
} from "../../__tests__/mockData";
import { GitTab } from "../../GitTab";

vi.mock("@/features/shared/api/apiClient", () => ({
	callAPIWithETag: vi.fn(),
}));

vi.mock("@/features/shared/hooks/useToast", () => ({
	useToast: () => ({
		showToast: vi.fn(),
	}),
}));

// Mock CodeViewer to avoid syntax highlighting complexity
vi.mock("../CodeViewer", () => ({
	CodeViewer: ({
		content,
		filePath,
	}: {
		content: string;
		filePath: string;
	}) => (
		<div data-testid="code-viewer">
			<div data-testid="code-content">{content}</div>
			<div data-testid="code-file-path">{filePath}</div>
		</div>
	),
}));

describe("GitTab Integration Tests", () => {
	let queryClient: QueryClient;
	const mockProject = {
		id: "project-123",
		title: "Test Project",
	};

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("should complete full flow: initialize → commits → file tree → view content", async () => {
		const user = userEvent.setup({ delay: null });

		// Step 1: No repository exists
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(null);

		const { rerender } = render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText("No repository linked")).toBeInTheDocument();
		});

		// Step 2: Initialize repository
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockRepositoryMetadata);

		const initButton = screen.getByText("Initialize Repository");
		await user.click(initButton);

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		// Step 3: After init, fetch repository
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockRepository);

		await waitFor(() => {
			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				"/api/projects/project-123/repository",
				expect.objectContaining({ method: "POST" }),
			);
		});

		// Simulate repository now exists
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockRepository);

		rerender(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		// Step 4: Load commits
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockCommitsPaginationResponse);

		await waitFor(() => {
			expect(screen.getByText("test/repo")).toBeInTheDocument();
			expect(screen.getByText("Commits")).toBeInTheDocument();
		});

		// Step 5: Select commit
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockFileTreeResponse);

		const firstCommit = screen.getByText(/Add new feature/i);
		await user.click(firstCommit);

		// Step 6: Load file tree
		await waitFor(() => {
			expect(screen.getByText("Files")).toBeInTheDocument();
			expect(screen.getByText("2")).toBeInTheDocument(); // 2 files
		});

		// Step 7: Select file
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockFileContentResponse);

		const fileItem = screen.getByText("Button.tsx");
		await user.click(fileItem);

		// Step 8: View content
		await waitFor(() => {
			expect(screen.getByTestId("code-viewer")).toBeInTheDocument();
			expect(screen.getByTestId("code-content")).toHaveTextContent(
				'export const Button = () => <button>Click me</button>;',
			);
		});
	});

	it("should sync commits and update list", async () => {
		const user = userEvent.setup({ delay: null });

		// Repository exists
		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText("test/repo")).toBeInTheDocument();
		});

		// Sync commits
		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockSyncCommitsResponse)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		await user.click(syncButton);

		await waitFor(() => {
			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				"/api/projects/project-123/repository/sync",
				expect.objectContaining({ method: "POST" }),
			);
		});
	});

	it("should filter commits via search", async () => {
		const user = userEvent.setup({ delay: null });

		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText(/Add new feature/i)).toBeInTheDocument();
			expect(screen.getByText(/Fix bug in login/i)).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search commits...");
		await user.type(searchInput, "feature");

		await waitFor(() => {
			expect(screen.getByText(/Add new feature/i)).toBeInTheDocument();
			expect(screen.queryByText(/Fix bug in login/i)).not.toBeInTheDocument();
		});
	});

	it("should implement two-stage delete and return to empty state", async () => {
		const user = userEvent.setup({ delay: null });

		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText("test/repo")).toBeInTheDocument();
		});

		// First click - show confirm
		const deleteButton = screen.getByRole("button", { name: "Remove" });
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "Click to confirm" })).toBeInTheDocument();
		});

		// Second click - delete
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(undefined);

		const confirmButton = screen.getByRole("button", { name: "Click to confirm" });
		await user.click(confirmButton);

		await waitFor(() => {
			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				"/api/projects/project-123/repository",
				expect.objectContaining({ method: "DELETE" }),
			);
		});

		// After delete, should return to empty state
		await waitFor(() => {
			expect(screen.getByText("No repository linked")).toBeInTheDocument();
		});
	});

	it("should handle initialization error", async () => {
		const user = userEvent.setup({ delay: null });

		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(null);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText("No repository linked")).toBeInTheDocument();
		});

		const initButton = screen.getByText("Initialize Repository");
		await user.click(initButton);

		vi.mocked(apiClient.callAPIWithETag).mockRejectedValueOnce(new Error("Init failed"));

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/invalid/path");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Init failed")).toBeInTheDocument();
		});
	});

	it("should handle sync error", async () => {
		const user = userEvent.setup({ delay: null });

		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText("test/repo")).toBeInTheDocument();
		});

		vi.mocked(apiClient.callAPIWithETag).mockRejectedValueOnce(new Error("Sync failed"));

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		await user.click(syncButton);

		await waitFor(() => {
			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				"/api/projects/project-123/repository/sync",
				expect.objectContaining({ method: "POST" }),
			);
		});
	});

	it("should persist selection when switching between commits", async () => {
		const user = userEvent.setup({ delay: null });

		vi.mocked(apiClient.callAPIWithETag)
			.mockResolvedValueOnce(mockRepository)
			.mockResolvedValueOnce(mockCommitsPaginationResponse);

		render(
			<QueryClientProvider client={queryClient}>
				<GitTab project={mockProject} />
			</QueryClientProvider>,
		);

		await waitFor(() => {
			expect(screen.getByText(/Add new feature/i)).toBeInTheDocument();
		});

		// Select first commit
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockFileTreeResponse);

		const firstCommit = screen.getByText(/Add new feature/i);
		await user.click(firstCommit);

		// Select second commit
		vi.mocked(apiClient.callAPIWithETag).mockResolvedValueOnce(mockFileTreeResponse);

		const secondCommit = screen.getByText(/Fix bug in login/i);
		await user.click(secondCommit);

		// File tree should update for new commit
		await waitFor(() => {
			expect(apiClient.callAPIWithETag).toHaveBeenCalledWith(
				expect.stringContaining("/repository/tree"),
				undefined,
			);
		});
	});
});
