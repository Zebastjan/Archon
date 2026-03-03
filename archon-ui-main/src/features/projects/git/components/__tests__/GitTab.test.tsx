/**
 * Tests for GitTab Component
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockQuery, mockRepository, mockRepositoryMetadata } from "../../__tests__/mockData";
import { GitTab } from "../../GitTab";

// Mock all hooks
vi.mock("../../hooks/useRepositoryQueries", () => ({
	useProjectRepository: vi.fn(),
	useRepositoryCommits: vi.fn(),
	useFileTree: vi.fn(),
	useFileContent: vi.fn(),
	useInitializeRepository: vi.fn(),
	useDeleteRepository: vi.fn(),
	useSyncCommits: vi.fn(),
}));

// Mock child components
vi.mock("../InitializeRepositoryModal", () => ({
	InitializeRepositoryModal: ({
		onClose,
		onSuccess,
	}: {
		onClose: () => void;
		onSuccess: (data: unknown) => void;
	}) => (
		<div data-testid="init-modal">
			<button onClick={onClose} type="button">
				Close
			</button>
			<button onClick={() => onSuccess(mockRepositoryMetadata)} type="button">
				Success
			</button>
		</div>
	),
}));

vi.mock("../CommitList", () => ({
	CommitList: ({
		projectId,
		branch,
		selectedCommitSha,
		onSelectCommit,
	}: {
		projectId: string;
		branch: string;
		selectedCommitSha?: string;
		onSelectCommit: (sha: string) => void;
	}) => (
		<div data-testid="commit-list">
			<div data-testid="commit-list-project-id">{projectId}</div>
			<div data-testid="commit-list-branch">{branch}</div>
			<div data-testid="commit-list-selected">{selectedCommitSha || "none"}</div>
			<button onClick={() => onSelectCommit("test-sha")} type="button">
				Select Commit
			</button>
		</div>
	),
}));

vi.mock("../FileTreeViewer", () => ({
	FileTreeViewer: ({ projectId, commitSha }: { projectId: string; commitSha: string }) => (
		<div data-testid="file-tree-viewer">
			<div data-testid="file-tree-project-id">{projectId}</div>
			<div data-testid="file-tree-commit-sha">{commitSha}</div>
		</div>
	),
}));

vi.mock("../RepositoryHeader", () => ({
	RepositoryHeader: ({
		projectId,
		selectedBranch,
		onBranchChange,
	}: {
		projectId: string;
		selectedBranch: string;
		onBranchChange: (branch: string) => void;
	}) => (
		<div data-testid="repository-header">
			<div data-testid="header-project-id">{projectId}</div>
			<div data-testid="header-branch">{selectedBranch}</div>
			<button onClick={() => onBranchChange("develop")} type="button">
				Change Branch
			</button>
		</div>
	),
}));

describe("GitTab", () => {
	const mockProject = {
		id: "project-123",
		title: "Test Project",
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render loading state", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				isLoading: true,
				isPending: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByText("Loading repository...")).toBeInTheDocument();
	});

	it("should render empty state with initialize button", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: null,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByText("No repository linked")).toBeInTheDocument();
		expect(screen.getByText(/Link an existing Git repository/i)).toBeInTheDocument();
		expect(screen.getByRole("button", { name: /Initialize Repository/i })).toBeInTheDocument();
	});

	it("should open modal when initialize button clicked", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: null,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		const initButton = screen.getByRole("button", { name: /Initialize Repository/i });
		await user.click(initButton);

		expect(screen.getByTestId("init-modal")).toBeInTheDocument();
	});

	it("should close modal when close button clicked", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: null,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		const initButton = screen.getByRole("button", { name: /Initialize Repository/i });
		await user.click(initButton);

		const closeButton = screen.getByText("Close");
		await user.click(closeButton);

		await waitFor(() => {
			expect(screen.queryByTestId("init-modal")).not.toBeInTheDocument();
		});
	});

	it("should update selected branch on modal success", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: null,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		const initButton = screen.getByRole("button", { name: /Initialize Repository/i });
		await user.click(initButton);

		const successButton = screen.getByText("Success");
		await user.click(successButton);

		await waitFor(() => {
			expect(screen.queryByTestId("init-modal")).not.toBeInTheDocument();
		});
	});

	it("should render two-panel layout when repository exists", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("repository-header")).toBeInTheDocument();
		expect(screen.getByTestId("commit-list")).toBeInTheDocument();
		expect(screen.getByTestId("file-tree-viewer")).toBeInTheDocument();
	});

	it("should pass correct props to child components", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("header-project-id")).toHaveTextContent("project-123");
		expect(screen.getByTestId("header-branch")).toHaveTextContent("main");
		expect(screen.getByTestId("commit-list-project-id")).toHaveTextContent("project-123");
		expect(screen.getByTestId("commit-list-branch")).toHaveTextContent("main");
		expect(screen.getByTestId("file-tree-project-id")).toHaveTextContent("project-123");
		expect(screen.getByTestId("file-tree-commit-sha")).toHaveTextContent("abc123def456");
	});

	it("should update selected commit when commit is selected", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("commit-list-selected")).toHaveTextContent("none");

		const selectButton = screen.getByText("Select Commit");
		await user.click(selectButton);

		await waitFor(() => {
			expect(screen.getByTestId("commit-list-selected")).toHaveTextContent("test-sha");
		});
	});

	it("should update selected branch when branch is changed", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("header-branch")).toHaveTextContent("main");
		expect(screen.getByTestId("commit-list-branch")).toHaveTextContent("main");

		const changeBranchButton = screen.getByText("Change Branch");
		await user.click(changeBranchButton);

		await waitFor(() => {
			expect(screen.getByTestId("header-branch")).toHaveTextContent("develop");
			expect(screen.getByTestId("commit-list-branch")).toHaveTextContent("develop");
		});
	});

	it("should use default branch when selectedBranch is undefined", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("header-branch")).toHaveTextContent("main");
		expect(screen.getByTestId("commit-list-branch")).toHaveTextContent("main");
	});

	it("should use current_head_sha when no commit selected", async () => {
		const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useProjectRepository).mockReturnValue(
			createMockQuery({
				data: mockRepository,
				isSuccess: true,
			}),
		);

		render(<GitTab project={mockProject} />);

		expect(screen.getByTestId("file-tree-commit-sha")).toHaveTextContent("abc123def456");
	});
});
