/**
 * Tests for CommitList Component
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockCommit, createMockQuery, mockCommitsPaginationResponse } from "../../__tests__/mockData";
import { CommitList } from "../CommitList";

vi.mock("../../hooks/useRepositoryQueries", () => ({
	useRepositoryCommits: vi.fn(),
}));

vi.mock("../CommitCard", () => ({
	CommitCard: ({
		commit,
		isSelected,
		onClick,
	}: {
		commit: { id: string; message: string; commit_sha: string };
		isSelected: boolean;
		onClick: () => void;
	}) => (
		<div data-testid={`commit-card-${commit.id}`} data-selected={isSelected} onClick={onClick}>
			{commit.message}
		</div>
	),
}));

describe("CommitList", () => {
	const mockOnSelectCommit = vi.fn();
	const mockProjectId = "project-123";
	const mockBranch = "main";

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render commit count", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		expect(screen.getByText("Commits")).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("should render CommitCard for each commit", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		expect(screen.getByTestId("commit-card-commit-789")).toBeInTheDocument();
		expect(screen.getByTestId("commit-card-commit-790")).toBeInTheDocument();
	});

	it("should filter commits by message (case insensitive)", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search commits...");
		await user.type(searchInput, "FEATURE");

		expect(screen.getByTestId("commit-card-commit-789")).toBeInTheDocument();
		expect(screen.queryByTestId("commit-card-commit-790")).not.toBeInTheDocument();
	});

	it("should filter commits by SHA", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search commits...");
		await user.type(searchInput, "def456");

		expect(screen.queryByTestId("commit-card-commit-789")).not.toBeInTheDocument();
		expect(screen.getByTestId("commit-card-commit-790")).toBeInTheDocument();
	});

	it("should filter commits by author name", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search commits...");
		await user.type(searchInput, "Jane");

		expect(screen.queryByTestId("commit-card-commit-789")).not.toBeInTheDocument();
		expect(screen.getByTestId("commit-card-commit-790")).toBeInTheDocument();
	});

	it("should show empty state when no commits", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: {
					commits: [],
					pagination: {
						total: 0,
						limit: 50,
						offset: 0,
						has_more: false,
					},
				},
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		expect(screen.getByText("No commits available")).toBeInTheDocument();
	});

	it("should show 'No commits found' when search returns empty", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const searchInput = screen.getByPlaceholderText("Search commits...");
		await user.type(searchInput, "nonexistent");

		expect(screen.getByText("No commits found")).toBeInTheDocument();
	});

	it("should call onSelectCommit when card clicked", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const commitCard = screen.getByTestId("commit-card-commit-789");
		await user.click(commitCard);

		expect(mockOnSelectCommit).toHaveBeenCalledWith("abc123def456");
	});

	it("should pass isSelected correctly to CommitCard", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				data: mockCommitsPaginationResponse,
				isSuccess: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha="abc123def456"
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		const selectedCard = screen.getByTestId("commit-card-commit-789");
		const unselectedCard = screen.getByTestId("commit-card-commit-790");

		expect(selectedCard).toHaveAttribute("data-selected", "true");
		expect(unselectedCard).toHaveAttribute("data-selected", "false");
	});

	it("should show loading state", async () => {
		const { useRepositoryCommits } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useRepositoryCommits).mockReturnValue(
			createMockQuery({
				isLoading: true,
				isPending: true,
			}),
		);

		render(
			<CommitList
				projectId={mockProjectId}
				branch={mockBranch}
				selectedCommitSha={undefined}
				onSelectCommit={mockOnSelectCommit}
			/>,
		);

		expect(screen.getByText("Loading commits...")).toBeInTheDocument();
	});
});
