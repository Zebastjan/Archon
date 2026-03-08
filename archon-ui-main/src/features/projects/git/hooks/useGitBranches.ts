import { useQuery } from '@tanstack/react-query';

interface BranchesResponse {
  branches: string[];
  default_branch: string;
}

export const useGitBranches = (projectId: string) => {
  return useQuery<BranchesResponse>({
    queryKey: ['git', 'branches', projectId],
    queryFn: async () => {
      const response = await fetch(`/api/projects/${projectId}/repository/branches`);
      if (!response.ok) {
        throw new Error('Failed to fetch branches');
      }
      return response.json();
    },
    // Cache for 5 minutes since branches don't change frequently
    staleTime: 5 * 60 * 1000,
  });
};
