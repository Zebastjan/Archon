/**
 * Git Test Fixtures Section
 *
 * UI for viewing and verifying git test fixtures.
 * This allows manual verification that backend and frontend tests align.
 */

import { useEffect, useState } from "react";
import { GitBranch, GitCommit, File, Binary, RefreshCw, Check, X } from "lucide-react";
import { repositoryService, type GitTestFixtureInfo } from "../../features/projects/git/services";

export function GitTestFixturesSection() {
  const [fixtures, setFixtures] = useState<GitTestFixtureInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFixture, setSelectedFixture] = useState<string | null>(null);

  const loadFixtures = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await repositoryService.listGitTestFixtures();
      setFixtures(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fixtures");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFixtures();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <RefreshCw className="w-5 h-5 animate-spin text-blue-500 mr-2" />
        <span className="text-sm text-gray-500">Loading fixtures...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        <button
          onClick={loadFixtures}
          className="mt-2 text-sm text-blue-500 hover:text-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Git test fixtures for backend/frontend test alignment verification.
        </p>
        <button
          onClick={loadFixtures}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {fixtures.length === 0 ? (
        <p className="text-sm text-gray-500">No fixtures found.</p>
      ) : (
        <div className="space-y-3">
          {fixtures.map((fixture) => (
            <div
              key={fixture.name}
              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                selectedFixture === fixture.name
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                  : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
              }`}
              onClick={() =>
                setSelectedFixture(
                  selectedFixture === fixture.name ? null : fixture.name,
                )
              }
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {fixture.name}
                  </span>
                  {fixture.has_binary_files ? (
                    <span className="flex items-center text-xs text-amber-600 dark:text-amber-400">
                      <Binary className="w-3 h-3 mr-1" />
                      Binary
                    </span>
                  ) : (
                    <span className="flex items-center text-xs text-green-600 dark:text-green-400">
                      <Check className="w-3 h-3 mr-1" />
                      Text only
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400">
                <span className="flex items-center">
                  <GitCommit className="w-3 h-3 mr-1" />
                  {fixture.commit_count} commits
                </span>
                <span className="flex items-center">
                  <GitBranch className="w-3 h-3 mr-1" />
                  {fixture.branch_count} branches
                </span>
                <span className="flex items-center">
                  <File className="w-3 h-3 mr-1" />
                  {fixture.file_count} files
                </span>
              </div>

              {selectedFixture === fixture.name && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    <p className="font-medium mb-1">Path:</p>
                    <code className="block bg-gray-100 dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto">
                      {fixture.path}
                    </code>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          These fixtures are used by both backend and frontend tests to ensure
          consistent behavior across the stack.
        </p>
      </div>
    </div>
  );
}
