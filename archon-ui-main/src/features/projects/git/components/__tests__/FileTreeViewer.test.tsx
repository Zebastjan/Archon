/**
 * Tests for FileTreeViewer Component
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	createMockFile,
	createMockQuery,
	mockBinaryFile,
	mockFileContentResponse,
	mockFileTreeResponse,
	mockGitFile,
} from "../../__tests__/mockData";
import { FileTreeViewer } from "../FileTreeViewer";

vi.mock("../../hooks/useRepositoryQueries", () => ({
	useFileTree: vi.fn(),
	useFileContent: vi.fn(),
}));

vi.mock("../FileTreeItem", () => ({
	FileTreeItem: ({
		file,
		isSelected,
		onClick,
	}: {
		file: { file_path: string; file_name: string; is_binary: boolean };
		isSelected: boolean;
		onClick: () => void;
	}) => (
		<div
			data-testid={`file-item-${file.file_path}`}
			data-selected={isSelected}
			data-binary={file.is_binary}
			onClick={onClick}
		>
			{file.file_name}
		</div>
	),
}));

vi.mock("../CodeViewer", () => ({
	CodeViewer: ({
		content,
		filePath,
		language,
	}: {
		content: string;
		filePath: string;
		language?: string;
	}) => (
		<div data-testid="code-viewer">
			<div data-testid="code-content">{content}</div>
			<div data-testid="code-file-path">{filePath}</div>
			<div data-testid="code-language">{language}</div>
		</div>
	),
}));

describe("FileTreeViewer", () => {
	const mockProjectId = "project-123";
	const mockCommitSha = "abc123def456";

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render file count", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		expect(screen.getByText("Files")).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("should render FileTreeItem for each file", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		expect(screen.getByTestId(`file-item-${mockGitFile.file_path}`)).toBeInTheDocument();
		expect(screen.getByTestId(`file-item-${mockBinaryFile.file_path}`)).toBeInTheDocument();
	});

	it("should select non-binary file when clicked", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(
			createMockQuery({
				data: mockFileContentResponse,
				isSuccess: true,
			}),
		);

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		const fileItem = screen.getByTestId(`file-item-${mockGitFile.file_path}`);
		await user.click(fileItem);

		expect(fileItem).toHaveAttribute("data-selected", "true");
	});

	it("should not select binary file when clicked", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		const binaryFileItem = screen.getByTestId(`file-item-${mockBinaryFile.file_path}`);
		await user.click(binaryFileItem);

		expect(binaryFileItem).toHaveAttribute("data-selected", "false");
	});

	it("should display CodeViewer when file selected", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(
			createMockQuery({
				data: mockFileContentResponse,
				isSuccess: true,
			}),
		);

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		const fileItem = screen.getByTestId(`file-item-${mockGitFile.file_path}`);
		await user.click(fileItem);

		expect(screen.getByTestId("code-viewer")).toBeInTheDocument();
		expect(screen.getByTestId("code-content")).toHaveTextContent(
			'export const Button = () => <button>Click me</button>;',
		);
	});

	it("should show empty state when no file selected", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		expect(screen.getByText("Select a file to view its content")).toBeInTheDocument();
	});

	it("should show loading state for tree", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				isLoading: true,
				isPending: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		expect(screen.getByText("Loading files...")).toBeInTheDocument();
	});

	it("should show empty state when no files", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: { files: [], file_count: 0, commit_sha: mockCommitSha },
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(createMockQuery());

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		expect(screen.getByText("No files found")).toBeInTheDocument();
	});

	it("should pass loading state to CodeViewer", async () => {
		const { useFileTree, useFileContent } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useFileTree).mockReturnValue(
			createMockQuery({
				data: mockFileTreeResponse,
				isSuccess: true,
			}),
		);
		vi.mocked(useFileContent).mockReturnValue(
			createMockQuery({
				data: mockFileContentResponse,
				isLoading: true,
			}),
		);

		render(<FileTreeViewer projectId={mockProjectId} commitSha={mockCommitSha} />);

		const fileItem = screen.getByTestId(`file-item-${mockGitFile.file_path}`);
		await user.click(fileItem);

		// CodeViewer should be rendered with isLoading=true
		expect(screen.getByTestId("code-viewer")).toBeInTheDocument();
	});
});
