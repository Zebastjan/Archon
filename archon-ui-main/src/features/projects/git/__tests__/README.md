# Git Integration Test Suite

## Overview

Comprehensive test suite for the Git integration feature, covering all layers from API services to UI components.

## Test Structure

```
src/features/projects/git/
├── __tests__/
│   ├── README.md (this file)
│   └── mockData.ts                     # Shared test fixtures and factory functions
├── services/
│   └── __tests__/
│       └── repositoryService.test.ts   # API layer tests (7 methods)
├── hooks/
│   └── __tests__/
│       └── useRepositoryQueries.test.tsx  # Query/mutation hook tests
└── components/
    └── __tests__/
        ├── GitTab.test.tsx                    # Main component (P0)
        ├── GitTab.integration.test.tsx        # End-to-end integration tests
        ├── InitializeRepositoryModal.test.tsx # Init modal (P0)
        ├── RepositoryHeader.test.tsx          # Header with sync/delete (P0)
        ├── CommitList.test.tsx                # Commit list with search (P1)
        ├── CommitCard.test.tsx                # Individual commit card (P1)
        ├── FileTreeViewer.test.tsx            # File tree viewer (P1)
        └── FileTreeItem.test.tsx              # Individual file item (P1)
```

## Test Coverage

### Service Layer (`repositoryService.test.ts`)
- ✅ initializeRepository (with/without branch_name, error propagation)
- ✅ getRepository (returns Repository or null, error handling)
- ✅ deleteRepository (DELETE request, 404 handling)
- ✅ getCommits (query param construction, empty results)
- ✅ syncCommits (POST with optional body, error propagation)
- ✅ getFileTree (query params with commit_sha/path_prefix)
- ✅ getFileContent (proper encoding, error handling)

**Pattern**: Mocks `callAPIWithETag` from `@/features/shared/api/apiClient`

### Hook Layer (`useRepositoryQueries.test.tsx`)
- ✅ repositoryKeys (query key factory)
- ✅ useProjectRepository (fetch, DISABLED_QUERY_KEY, normal stale time)
- ✅ useRepositoryCommits (pagination, branch filtering, DISABLED_QUERY_KEY)
- ✅ useFileTree (static stale time for immutable data)
- ✅ useFileContent (static stale time, DISABLED_QUERY_KEY)
- ✅ useInitializeRepository (service call, invalidation, toasts)
- ✅ useDeleteRepository (set data to null, invalidate commits, toasts)
- ✅ useSyncCommits (invalidate commits + repository, toasts)

**Pattern**: Mocks `repositoryService`, uses `renderHook` with QueryClientProvider

### Component Layer - P0 (Critical Flows)

#### GitTab.test.tsx
- ✅ Loading state while fetching repository
- ✅ Empty state with "Initialize Repository" button
- ✅ Modal opens/closes on button click
- ✅ Two-panel layout when repository exists
- ✅ selectedBranch/selectedCommitSha state updates
- ✅ Props passed correctly to child components
- ✅ Modal success triggers branch update

#### InitializeRepositoryModal.test.tsx
- ✅ Form validation (empty repo path shows error)
- ✅ Input trimming (whitespace removed)
- ✅ Submit calls mutation with correct payload
- ✅ branch_name is undefined when empty
- ✅ Success calls onSuccess callback
- ✅ Error displays in modal
- ✅ Submit button shows loading state
- ✅ Form submission via Enter key

#### RepositoryHeader.test.tsx
- ✅ Repository name and URL display
- ✅ Current branch display
- ✅ Sync button calls mutation with selectedBranch
- ✅ Sync button disabled + spinning icon while pending
- ✅ Two-stage delete: first click → "Click to confirm"
- ✅ Two-stage delete: second click → calls mutation
- ✅ Confirm state resets after 3 seconds
- ✅ Both buttons disabled during mutations

### Component Layer - P1 (User Interactions)

#### CommitList.test.tsx
- ✅ Commit count display
- ✅ CommitCard rendered for each commit
- ✅ Search filters by message (case insensitive)
- ✅ Search filters by SHA
- ✅ Search filters by author name
- ✅ Empty state when no commits
- ✅ "No commits found" when search returns empty
- ✅ onSelectCommit called when card clicked
- ✅ isSelected passed correctly to CommitCard

#### CommitCard.test.tsx
- ✅ Short SHA display (7 chars, monospace)
- ✅ Commit message truncation (max 2 lines)
- ✅ Author name with User icon
- ✅ Date formatting ("Mon DD, YYYY")
- ✅ First branch badge display
- ✅ Selected styles (cyan border/background)
- ✅ onClick triggered on click
- ✅ Keyboard accessibility (Enter/Space)

#### FileTreeViewer.test.tsx
- ✅ File count display
- ✅ FileTreeItem rendered for each file
- ✅ Non-binary file selection updates state
- ✅ Binary file selection blocked
- ✅ CodeViewer displayed when file selected
- ✅ Empty state when no file selected
- ✅ Loading states for tree and content

#### FileTreeItem.test.tsx
- ✅ FileCode icon for files with language
- ✅ File icon (gray) for binary files
- ✅ Binary files disabled (no onClick)
- ✅ Tooltip shows "cannot preview" for binary files
- ✅ Language badge display
- ✅ Selected styles (cyan background)
- ✅ Hover styles for non-binary files
- ✅ File name truncation

### Integration Layer (`GitTab.integration.test.tsx`)

End-to-end flows mocking only `callAPIWithETag`:

- ✅ Initialize repository → commits display → select commit → view file tree → select file → view content
- ✅ Sync commits → list updates
- ✅ Search commits → results filter
- ✅ Two-stage delete → repository removed → UI returns to empty state
- ✅ Error handling during initialization
- ✅ Error handling during sync
- ✅ Persist selection when switching between commits

## Mock Strategy

Layer-by-layer approach:

1. **Service tests**: Mock `callAPIWithETag`
2. **Hook tests**: Mock `repositoryService`
3. **Component tests**: Mock hooks from `useRepositoryQueries`
4. **Integration tests**: Mock `callAPIWithETag` only

Always mock:
```typescript
vi.mock("@/features/ui/hooks/useToast", () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));
```

## Running Tests

```bash
# All Git integration tests
npm run test -- src/features/projects/git

# Specific test file
npm run test -- src/features/projects/git/services/__tests__/repositoryService.test.ts

# Watch mode
npm run test

# Coverage report
npm run test:coverage:run -- src/features/projects/git
```

## Shared Mock Data (`mockData.ts`)

Centralized fixtures:
- `mockRepository`, `mockCommit`, `mockGitFile`, `mockBinaryFile`
- `mockCommitsPaginationResponse`, `mockFileTreeResponse`, `mockFileContentResponse`
- `mockRepositoryMetadata`, `mockSyncCommitsResponse`

Factory functions:
- `createMockCommit(overrides)` - Create commit variations
- `createMockFile(overrides)` - Create file variations
- `createMockMutation()` - Mock TanStack Query mutation return value
- `createMockQuery()` - Mock TanStack Query query return value

## Coverage Goals

- **Service layer**: 100% coverage
- **Hook layer**: 95%+ coverage
- **Component layer**: 85%+ coverage
- **Integration layer**: 70%+ coverage

## Key Patterns

### Testing Query Hooks
```typescript
const { useProjectRepository } = await import("../../hooks/useRepositoryQueries");
vi.mocked(useProjectRepository).mockReturnValue(createMockQuery({ data: mockRepository }));
```

### Testing Mutation Hooks
```typescript
const mockMutate = vi.fn();
vi.mocked(useInitializeRepository).mockReturnValue(
  createMockMutation({ mutate: mockMutate })
);
```

### Testing Form Submission
```typescript
await user.type(input, "value");
await user.click(submitButton);
await waitFor(() => expect(mockMutate).toHaveBeenCalledWith({ ... }));
```

### Testing Two-Stage Delete
```typescript
await user.click(deleteButton); // First click
expect(screen.getByText("Click to confirm")).toBeInTheDocument();
await user.click(confirmButton); // Second click
expect(mockMutate).toHaveBeenCalled();
```

## Notes

- All tests use Vitest + React Testing Library
- User interactions use `@testing-library/user-event` for realistic behavior
- Query client configured with `retry: false` for faster tests
- Timers mocked for two-stage delete testing
- Integration tests cover critical user journeys
