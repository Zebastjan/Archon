/**
 * Tests for InitializeRepositoryModal Component
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMockMutation, mockRepositoryMetadata } from "../../__tests__/mockData";
import { InitializeRepositoryModal } from "../InitializeRepositoryModal";

vi.mock("../../hooks/useRepositoryQueries", () => ({
	useInitializeRepository: vi.fn(),
}));

describe("InitializeRepositoryModal", () => {
	const mockOnClose = vi.fn();
	const mockOnSuccess = vi.fn();
	const mockProjectId = "project-123";

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("should render modal with form fields", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useInitializeRepository).mockReturnValue(createMockMutation());

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		expect(screen.getByText("Initialize Repository")).toBeInTheDocument();
		expect(screen.getByLabelText("Repository Path")).toBeInTheDocument();
		expect(screen.getByLabelText("Branch Name (Optional)")).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Initialize" })).toBeInTheDocument();
	});

	it("should show error when repo path is empty on submit", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useInitializeRepository).mockReturnValue(createMockMutation());

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Repository path is required")).toBeInTheDocument();
		});
	});

	it("should trim input values before submission", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockResolvedValue(mockRepositoryMetadata);
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const repoPathInput = screen.getByLabelText("Repository Path");
		const branchNameInput = screen.getByLabelText("Branch Name (Optional)");

		await user.type(repoPathInput, "  /path/to/repo  ");
		await user.type(branchNameInput, "  main  ");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(mockMutateAsync).toHaveBeenCalledWith({
				repo_path: "/path/to/repo",
				branch_name: "main",
			});
		});
	});

	it("should set branch_name to undefined when empty", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockResolvedValue(mockRepositoryMetadata);
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(mockMutateAsync).toHaveBeenCalledWith({
				repo_path: "/path/to/repo",
				branch_name: undefined,
			});
		});
	});

	it("should call onSuccess on successful initialization", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockResolvedValue(mockRepositoryMetadata);
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(mockOnSuccess).toHaveBeenCalledWith(mockRepositoryMetadata);
		});
	});

	it("should display error on initialization failure", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockRejectedValue(new Error("Initialization failed"));
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo");

		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Initialization failed")).toBeInTheDocument();
		});
	});

	it("should show loading state while initializing", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");

		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				isPending: true,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const submitButton = screen.getByRole("button", { name: "Initializing..." });
		expect(submitButton).toBeDisabled();
	});

	it("should call onClose when close button clicked", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		vi.mocked(useInitializeRepository).mockReturnValue(createMockMutation());

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const closeButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(closeButton);

		expect(mockOnClose).toHaveBeenCalled();
	});

	it("should submit form via Enter key", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockResolvedValue(mockRepositoryMetadata);
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo{Enter}");

		await waitFor(() => {
			expect(mockMutateAsync).toHaveBeenCalled();
		});
	});

	it("should clear error when resubmitting after error", async () => {
		const { useInitializeRepository } = await import("../../hooks/useRepositoryQueries");
		const user = userEvent.setup();

		const mockMutateAsync = vi.fn().mockResolvedValue(mockRepositoryMetadata);
		vi.mocked(useInitializeRepository).mockReturnValue(
			createMockMutation({
				mutateAsync: mockMutateAsync,
			}),
		);

		render(
			<InitializeRepositoryModal projectId={mockProjectId} onClose={mockOnClose} onSuccess={mockOnSuccess} />,
		);

		// First submit with empty path
		const submitButton = screen.getByRole("button", { name: "Initialize" });
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Repository path is required")).toBeInTheDocument();
		});

		// Now fill in path and submit again
		const repoPathInput = screen.getByLabelText("Repository Path");
		await user.type(repoPathInput, "/path/to/repo");
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.queryByText("Repository path is required")).not.toBeInTheDocument();
		});
	});
});
