/**
 * Tests for RepositoryHeader Component
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockMutation, mockRepository } from "../../__tests__/mockData";
import { RepositoryHeader } from "../RepositoryHeader";

vi.mock("../../hooks/useRepositoryQueries", () => ({
	useSyncCommits: vi.fn(),
	useDeleteRepository: vi.fn(),
}));

describe("RepositoryHeader", () => {
	const mockOnBranchChange = vi.fn();
	const mockProjectId = "project-123";

	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("should render repository information", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		expect(screen.getByText("test/repo")).toBeInTheDocument();
		expect(screen.getByText("https://github.com/test/repo")).toBeInTheDocument();
	});

	it("should display selected branch", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="develop"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		expect(screen.getByText("develop")).toBeInTheDocument();
	});

	it("should call sync mutation with selected branch", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup({ delay: null });

		const mockMutate = vi.fn();
		vi.mocked(useSyncCommits).mockReturnValue(
			createMockMutation({
				mutate: mockMutate,
			}),
		);
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		await user.click(syncButton);

		expect(mockMutate).toHaveBeenCalledWith({ branch_name: "main" });
	});

	it("should disable sync button while syncing", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		expect(syncButton).toBeDisabled();
	});

	it("should show spinning icon while syncing", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		const icon = syncButton.querySelector("svg");
		expect(icon).toHaveClass("animate-spin");
	});

	it("should implement two-stage delete - first click shows confirm", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup({ delay: null });

		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const deleteButton = screen.getByRole("button", { name: "Remove" });
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "Click to confirm" })).toBeInTheDocument();
		});
	});

	it("should implement two-stage delete - second click calls mutation", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup({ delay: null });

		const mockMutate = vi.fn();
		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(
			createMockMutation({
				mutate: mockMutate,
			}),
		);

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const deleteButton = screen.getByRole("button", { name: "Remove" });
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "Click to confirm" })).toBeInTheDocument();
		});

		const confirmButton = screen.getByRole("button", { name: "Click to confirm" });
		await user.click(confirmButton);

		expect(mockMutate).toHaveBeenCalled();
	});

	it("should reset confirm state after 3 seconds", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup({ delay: null });

		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(createMockMutation());

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const deleteButton = screen.getByRole("button", { name: "Remove" });
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "Click to confirm" })).toBeInTheDocument();
		});

		// Advance timers by 3 seconds
		vi.advanceTimersByTime(3000);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
		});
	});

	it("should disable delete button while deleting", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(createMockMutation());
		vi.mocked(useDeleteRepository).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const deleteButton = screen.getByRole("button", { name: "Remove" });
		expect(deleteButton).toBeDisabled();
	});

	it("should disable both buttons during mutations", async () => {
		const { useSyncCommits, useDeleteRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useSyncCommits).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);
		vi.mocked(useDeleteRepository).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);

		render(
			<RepositoryHeader
				projectId={mockProjectId}
				repository={mockRepository}
				selectedBranch="main"
				onBranchChange={mockOnBranchChange}
			/>,
		);

		const syncButton = screen.getByRole("button", { name: /Sync/i });
		const deleteButton = screen.getByRole("button", { name: "Remove" });

		expect(syncButton).toBeDisabled();
		expect(deleteButton).toBeDisabled();
	});
});
