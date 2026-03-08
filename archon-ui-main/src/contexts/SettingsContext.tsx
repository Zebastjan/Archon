import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { credentialsService } from '../services/credentialsService';
import { repositoryService } from '../features/projects/git/services';

interface SettingsContextType {
  projectsEnabled: boolean;
  setProjectsEnabled: (enabled: boolean) => Promise<void>;
  styleGuideEnabled: boolean;
  setStyleGuideEnabled: (enabled: boolean) => Promise<void>;
  agentWorkOrdersEnabled: boolean;
  setAgentWorkOrdersEnabled: (enabled: boolean) => Promise<void>;
  gitTestFixturesEnabled: boolean;
  setGitTestFixturesEnabled: (enabled: boolean) => Promise<void>;
  loading: boolean;
  refreshSettings: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

interface SettingsProviderProps {
  children: ReactNode;
}

export const SettingsProvider: React.FC<SettingsProviderProps> = ({ children }) => {
  const [projectsEnabled, setProjectsEnabledState] = useState(true);
  const [styleGuideEnabled, setStyleGuideEnabledState] = useState(false);
  const [agentWorkOrdersEnabled, setAgentWorkOrdersEnabledState] = useState(false);
  const [gitTestFixturesEnabled, setGitTestFixturesEnabledState] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadSettings = async () => {
    try {
      setLoading(true);

      // Load Projects, Style Guide, Agent Work Orders, and Git Test Fixtures settings
      const [projectsResponse, styleGuideResponse, agentWorkOrdersResponse, gitTestResponse] = await Promise.all([
        credentialsService.getCredential('PROJECTS_ENABLED').catch(() => ({ value: undefined })),
        credentialsService.getCredential('STYLE_GUIDE_ENABLED').catch(() => ({ value: undefined })),
        credentialsService.getCredential('AGENT_WORK_ORDERS_ENABLED').catch(() => ({ value: undefined })),
        credentialsService.getCredential('GIT_TEST_FIXTURES_ENABLED').catch(() => ({ value: undefined }))
      ]);

      if (projectsResponse.value !== undefined) {
        setProjectsEnabledState(projectsResponse.value === 'true');
      } else {
        setProjectsEnabledState(true); // Default to true
      }

      if (styleGuideResponse.value !== undefined) {
        setStyleGuideEnabledState(styleGuideResponse.value === 'true');
      } else {
        setStyleGuideEnabledState(false); // Default to false
      }

      if (agentWorkOrdersResponse.value !== undefined) {
        setAgentWorkOrdersEnabledState(agentWorkOrdersResponse.value === 'true');
      } else {
        setAgentWorkOrdersEnabledState(false); // Default to false
      }

      if (gitTestResponse.value !== undefined) {
        setGitTestFixturesEnabledState(gitTestResponse.value === 'true');
      } else {
        setGitTestFixturesEnabledState(false); // Default to false
      }

    } catch (error) {
      console.error('Failed to load settings:', error);
      setProjectsEnabledState(true);
      setStyleGuideEnabledState(false);
      setAgentWorkOrdersEnabledState(false);
      setGitTestFixturesEnabledState(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const setProjectsEnabled = async (enabled: boolean) => {
    try {
      // Update local state immediately
      setProjectsEnabledState(enabled);

      // Save to backend
      await credentialsService.createCredential({
        key: 'PROJECTS_ENABLED',
        value: enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable or disable Projects and Tasks functionality'
      });
    } catch (error) {
      console.error('Failed to update projects setting:', error);
      // Revert on error
      setProjectsEnabledState(!enabled);
      throw error;
    }
  };

  const setStyleGuideEnabled = async (enabled: boolean) => {
    try {
      // Update local state immediately
      setStyleGuideEnabledState(enabled);

      // Save to backend
      await credentialsService.createCredential({
        key: 'STYLE_GUIDE_ENABLED',
        value: enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Show UI style guide and components in navigation'
      });
    } catch (error) {
      console.error('Failed to update style guide setting:', error);
      // Revert on error
      setStyleGuideEnabledState(!enabled);
      throw error;
    }
  };

  const setAgentWorkOrdersEnabled = async (enabled: boolean) => {
    try {
      // Update local state immediately
      setAgentWorkOrdersEnabledState(enabled);

      // Save to backend
      await credentialsService.createCredential({
        key: 'AGENT_WORK_ORDERS_ENABLED',
        value: enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable Agent Work Orders feature for automated development workflows'
      });
    } catch (error) {
      console.error('Failed to update agent work orders setting:', error);
      // Revert on error
      setAgentWorkOrdersEnabledState(!enabled);
      throw error;
    }
  };

  const setGitTestFixturesEnabled = async (enabled: boolean) => {
    try {
      // Update local state immediately
      setGitTestFixturesEnabledState(enabled);

      // Save to backend
      await credentialsService.createCredential({
        key: 'GIT_TEST_FIXTURES_ENABLED',
        value: enabled.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable Git Test Fixtures for testing Git integration'
      });

      // If disabling, trigger cleanup
      if (!enabled) {
        try {
          await repositoryService.cleanupTestFixtures('git-integration-test-project');
          console.log('Git Test Fixtures disabled - cleanup completed');
        } catch (cleanupError) {
          console.error('Failed to cleanup test fixtures:', cleanupError);
          // Don't throw - we still want to disable the setting even if cleanup fails
        }
      }
    } catch (error) {
      console.error('Failed to update git test fixtures setting:', error);
      // Revert on error
      setGitTestFixturesEnabledState(!enabled);
      throw error;
    }
  };

  const refreshSettings = async () => {
    await loadSettings();
  };

  const value: SettingsContextType = {
    projectsEnabled,
    setProjectsEnabled,
    styleGuideEnabled,
    setStyleGuideEnabled,
    agentWorkOrdersEnabled,
    setAgentWorkOrdersEnabled,
    gitTestFixturesEnabled,
    setGitTestFixturesEnabled,
    loading,
    refreshSettings
  };

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
}; 