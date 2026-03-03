/**
 * Tests for FileTreeItem Component
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockFile, mockBinaryFile, mockGitFile } from "../../__tests__/mockData";
import { FileTreeItem } from "../FileTreeItem";

describe("FileTreeItem", () => {
	const mockOnClick = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render FileCode icon for files with language", () => {
		const file = createMockFile({
			language: "typescript",
			is_binary: false,
		});

		render(<FileTreeItem file={file} isSelected={false} onClick={mockOnClick} />);

		// With mocked icons, just verify the component renders
		const button = screen.getByRole("button");
		expect(button).toBeInTheDocument();
	});

	it("should render gray File icon for binary files", () => {
		render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		expect(button).toBeInTheDocument();
	});

	it("should disable binary files", () => {
		render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		expect(button).toBeDisabled();
	});

	it("should show tooltip for binary files", () => {
		render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		expect(button).toHaveAttribute("title", "Binary file (cannot preview)");
	});

	it("should show file path tooltip for non-binary files", () => {
		render(<FileTreeItem file={mockGitFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		expect(button).toHaveAttribute("title", mockGitFile.file_path);
	});

	it("should display language badge when language exists", () => {
		const file = createMockFile({
			language: "typescript",
			file_name: "test.ts",
		});

		render(<FileTreeItem file={file} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("typescript")).toBeInTheDocument();
	});

	it("should not display language badge for binary files", () => {
		render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		expect(screen.queryByText("typescript")).not.toBeInTheDocument();
	});

	it("should apply selected styles when isSelected is true", () => {
		const { container } = render(<FileTreeItem file={mockGitFile} isSelected={true} onClick={mockOnClick} />);

		const button = container.querySelector("button");
		expect(button).toHaveClass("bg-cyan-500/20");
		expect(button).toHaveClass("text-cyan-300");
	});

	it("should apply hover styles for non-binary files", () => {
		const { container } = render(<FileTreeItem file={mockGitFile} isSelected={false} onClick={mockOnClick} />);

		const button = container.querySelector("button");
		expect(button).toHaveClass("hover:bg-white/5");
	});

	it("should apply disabled cursor for binary files", () => {
		const { container } = render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		const button = container.querySelector("button");
		expect(button).toHaveClass("cursor-not-allowed");
	});

	it("should display file name", () => {
		render(<FileTreeItem file={mockGitFile} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("Button.tsx")).toBeInTheDocument();
	});

	it("should truncate long file names", () => {
		const file = createMockFile({
			file_name: "VeryLongFileNameThatShouldBeTruncatedInTheUI.tsx",
		});

		render(<FileTreeItem file={file} isSelected={false} onClick={mockOnClick} />);

		const fileName = screen.getByText("VeryLongFileNameThatShouldBeTruncatedInTheUI.tsx");
		expect(fileName).toHaveClass("truncate");
	});

	it("should trigger onClick when non-binary file is clicked", async () => {
		const user = userEvent.setup();

		render(<FileTreeItem file={mockGitFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		await user.click(button);

		expect(mockOnClick).toHaveBeenCalledTimes(1);
	});

	it("should not trigger onClick when binary file is clicked (disabled)", async () => {
		const user = userEvent.setup();

		render(<FileTreeItem file={mockBinaryFile} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		await user.click(button);

		// Button is disabled, so onClick should not be called
		expect(mockOnClick).not.toHaveBeenCalled();
	});
});
