/**
 * Tests for CommitCard Component
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockCommit } from "../../__tests__/mockData";
import { CommitCard } from "../CommitCard";

describe("CommitCard", () => {
	const mockOnClick = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should display short SHA (7 characters)", () => {
		const commit = createMockCommit();

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("abc123d")).toBeInTheDocument();
	});

	it("should display SHA in monospace font", () => {
		const commit = createMockCommit();

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const shaElement = screen.getByText("abc123d");
		expect(shaElement.tagName).toBe("CODE");
		expect(shaElement).toHaveClass("font-mono");
	});

	it("should display commit message", () => {
		const commit = createMockCommit({
			message: "Add new feature to improve user experience",
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("Add new feature to improve user experience")).toBeInTheDocument();
	});

	it("should truncate long commit messages (line-clamp-2)", () => {
		const commit = createMockCommit({
			message: "Very long commit message that should be truncated after two lines of text",
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const messageElement = screen.getByText(
			"Very long commit message that should be truncated after two lines of text",
		);
		expect(messageElement).toHaveClass("line-clamp-2");
	});

	it("should display author name with User icon", () => {
		const commit = createMockCommit({
			author_name: "John Doe",
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("John Doe")).toBeInTheDocument();
	});

	it("should display formatted date (Mon DD, YYYY)", () => {
		const commit = createMockCommit({
			commit_date: "2025-01-15T09:00:00Z",
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("Jan 15, 2025")).toBeInTheDocument();
	});

	it("should display first branch badge when branches exist", () => {
		const commit = createMockCommit({
			branches: ["main", "feature/test"],
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		expect(screen.getByText("main")).toBeInTheDocument();
		expect(screen.queryByText("feature/test")).not.toBeInTheDocument();
	});

	it("should not display branch badge when no branches", () => {
		const commit = createMockCommit({
			branches: [],
		});

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const branchBadges = screen.queryByText("main");
		expect(branchBadges).not.toBeInTheDocument();
	});

	it("should apply selected styles when isSelected is true", () => {
		const commit = createMockCommit();

		const { container } = render(<CommitCard commit={commit} isSelected={true} onClick={mockOnClick} />);

		const button = container.querySelector("button");
		expect(button).toHaveClass("border-cyan-500/50");
		expect(button).toHaveClass("bg-cyan-500/10");
	});

	it("should apply hover styles when not selected", () => {
		const commit = createMockCommit();

		const { container } = render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const button = container.querySelector("button");
		expect(button).toHaveClass("hover:border-cyan-500/30");
		expect(button).toHaveClass("hover:bg-white/10");
	});

	it("should trigger onClick when clicked", async () => {
		const commit = createMockCommit();
		const user = userEvent.setup();

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		await user.click(button);

		expect(mockOnClick).toHaveBeenCalledTimes(1);
	});

	it("should be keyboard accessible (Enter key)", async () => {
		const commit = createMockCommit();
		const user = userEvent.setup();

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		button.focus();
		await user.keyboard("{Enter}");

		expect(mockOnClick).toHaveBeenCalledTimes(1);
	});

	it("should be keyboard accessible (Space key)", async () => {
		const commit = createMockCommit();
		const user = userEvent.setup();

		render(<CommitCard commit={commit} isSelected={false} onClick={mockOnClick} />);

		const button = screen.getByRole("button");
		button.focus();
		await user.keyboard(" ");

		expect(mockOnClick).toHaveBeenCalledTimes(1);
	});
});
