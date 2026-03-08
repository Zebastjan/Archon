/**
 * Semantic Search Hook
 * React hook for Git commit semantic search
 */

import { useState, useCallback } from "react";
import {
  semanticSearchService,
  type CommitSearchFilters,
  type CommitSearchResult,
  type GitCommitSearchResponse,
} from "../services/semanticSearchService";

export const useSemanticSearch = () => {
  const [results, setResults] = useState<CommitSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<string>("");

  const search = useCallback(
    async (query: string, filters: CommitSearchFilters = {}, matchCount: number = 20) => {
      if (!query.trim()) {
        setResults([]);
        setLastQuery("");
        return;
      }

      setIsLoading(true);
      setError(null);
      setLastQuery(query);

      try {
        const response: GitCommitSearchResponse = await semanticSearchService.searchCommits(
          query,
          filters,
          matchCount,
        );
        setResults(response.results);
      } catch (err) {
        console.error("Semantic search failed:", err);
        setError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setResults([]);
    setIsLoading(false);
    setError(null);
    setLastQuery("");
  }, []);

  return {
    results,
    isLoading,
    error,
    lastQuery,
    search,
    reset,
  };
};
