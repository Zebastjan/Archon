/**
 * Git Integration Test Project Card
 * 
 * A special project card that appears when Git Test Fixtures are enabled.
 * Allows users to initialize and cleanup test repositories.
 */

import { GitBranch, Loader2, Play, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";
import { useToast } from "../../../features/shared/hooks/useToast";
import { SelectableCard } from "../../ui/primitives";
import { cn } from "../../ui/primitives/styles";
import { repositoryService } from "../git/services";

interface GitTestProjectCardProps {
  onInitialize?: () => void;
}

const FIXTURES = [
  { 
    name: "simple-commits", 
    displayName: "Simple Commits",
    description: "3 commits, 1 branch, 3 files"
  },
  { 
    name: "multi-branch", 
    displayName: "Multi Branch",
    description: "4 commits, 3 branches, merge commit"
  },
  { 
    name: "file-structure", 
    displayName: "File Structure",
    description: "13 files including binary files"
  },
];

export const GitTestProjectCard: React.FC<GitTestProjectCardProps> = ({
  onInitialize
}) => {
  const { showToast } = useToast();
  const [loadingFixture, setLoadingFixture] = useState<string | null>(null);
  const [initializedFixtures, setInitializedFixtures] = useState<Set<string>>(new Set());
  const [isCleaning, setIsCleaning] = useState(false);

  // Load initialized fixtures from backend on mount
  useEffect(() => {
    const loadInitializedFixtures = async () => {
      try {
        const testProjectId = "git-integration-test-project";
        const response = await repositoryService.getInitializedFixtures(testProjectId);

        // Extract fixture names from the response
        const fixtureNames = response.fixtures.map(f => f.name);
        setInitializedFixtures(new Set(fixtureNames));
      } catch (error) {
        // Silently fail - fixtures list will just be empty
        console.error("Failed to load initialized fixtures:", error);
      }
    };

    loadInitializedFixtures();
  }, []);

  const handleInitializeFixture = async (fixtureName: string) => {
    try {
      setLoadingFixture(fixtureName);
      
      // Note: This uses a special test project ID
      // In a real implementation, you'd create/get the test project first
      const testProjectId = "git-integration-test-project";
      
      await repositoryService.initializeTestFixture(testProjectId, fixtureName);
      
      setInitializedFixtures(prev => new Set(prev).add(fixtureName));
      showToast(
        `Test fixture '${fixtureName}' initialized successfully`,
        "success"
      );
      
      onInitialize?.();
    } catch (error) {
      console.error("Failed to initialize test fixture:", error);
      showToast(
        `Failed to initialize test fixture: ${error instanceof Error ? error.message : "Unknown error"}`,
        "error"
      );
    } finally {
      setLoadingFixture(null);
    }
  };

  const handleCleanup = async () => {
    if (!confirm("Are you sure you want to cleanup all test fixtures? This will delete all test repositories and their data.")) {
      return;
    }
    
    try {
      setIsCleaning(true);
      
      const testProjectId = "git-integration-test-project";
      await repositoryService.cleanupTestFixtures(testProjectId);
      
      setInitializedFixtures(new Set());
      showToast("Test fixtures cleaned up successfully", "success");
    } catch (error) {
      console.error("Failed to cleanup test fixtures:", error);
      showToast(
        `Failed to cleanup test fixtures: ${error instanceof Error ? error.message : "Unknown error"}`,
        "error"
      );
    } finally {
      setIsCleaning(false);
    }
  };

  return (
    <SelectableCard
      isSelected={false}
      isPinned={false}
      showAuroraGlow={false}
      size="default"
      blur="md"
      onSelect={() => {}} // Dummy handler to prevent SelectableCard from intercepting clicks
      className={cn(
        "p-4 bg-gradient-to-br from-purple-500/10 via-purple-400/5 to-purple-500/10",
        "border-purple-400/30 dark:border-purple-400/20"
      )}
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-purple-500/20 to-purple-600/20">
              <GitBranch className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-800 dark:text-white">
                Git Integration Test Project
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Test repository fixtures
              </p>
            </div>
          </div>
        </div>

        {/* Test Fixture Buttons */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
            Initialize Test Fixtures:
          </p>
          <div className="grid grid-cols-1 gap-2">
            {FIXTURES.map((fixture) => (
              <button
                key={fixture.name}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleInitializeFixture(fixture.name);
                }}
                disabled={loadingFixture === fixture.name || initializedFixtures.has(fixture.name)}
                className={cn(
                  "flex items-center justify-between px-3 py-2 rounded-lg text-left",
                  "border transition-all duration-200",
                  initializedFixtures.has(fixture.name)
                    ? "bg-green-500/10 border-green-400/30 cursor-default"
                    : "bg-purple-500/5 border-purple-400/20 hover:bg-purple-500/10 hover:border-purple-400/40",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                <div className="flex items-center gap-2">
                  {loadingFixture === fixture.name ? (
                    <Loader2 className="h-4 w-4 text-purple-500 animate-spin" />
                  ) : initializedFixtures.has(fixture.name) ? (
                    <span className="h-4 w-4 text-green-500">✓</span>
                  ) : (
                    <Play className="h-4 w-4 text-purple-500" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
                      {fixture.displayName}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {fixture.description}
                    </p>
                  </div>
                </div>
                {initializedFixtures.has(fixture.name) && (
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                    Active
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Cleanup Button */}
        <div className="pt-2 border-t border-gray-200/50 dark:border-gray-700/50">
          <button
            type="button"
            onClick={handleCleanup}
            disabled={isCleaning || initializedFixtures.size === 0}
            className={cn(
              "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg",
              "text-sm font-medium transition-all duration-200",
              "bg-red-500/10 text-red-600 dark:text-red-400",
              "border border-red-400/20 hover:bg-red-500/20 hover:border-red-400/40",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {isCleaning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Cleaning up...
              </>
            ) : (
              <>
                <Trash2 className="h-4 w-4" />
                Cleanup All Test Repositories
              </>
            )}
          </button>
          <p className="mt-1 text-xs text-center text-gray-500 dark:text-gray-400">
            This will delete all test data and files
          </p>
        </div>
      </div>
    </SelectableCard>
  );
};
