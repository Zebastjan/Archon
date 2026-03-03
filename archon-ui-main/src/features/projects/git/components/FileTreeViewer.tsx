/**
 * File Tree Viewer Component
 * Displays file tree and code content
 */

import { FileCode, Folder, FolderOpen } from "lucide-react";
import { useState } from "react";
import { useFileContent, useFileTree } from "../hooks";
import { CodeViewer } from "./CodeViewer";
import { FileTreeItem } from "./FileTreeItem";

interface FileTreeViewerProps {
  projectId: string;
  commitSha: string;
}

export const FileTreeViewer = ({ projectId, commitSha }: FileTreeViewerProps) => {
  const [selectedFilePath, setSelectedFilePath] = useState<string | undefined>();
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());

  // Fetch file tree
  const { data: fileTree, isLoading } = useFileTree(projectId, commitSha);

  // Fetch selected file content
  const { data: fileContent, isLoading: isLoadingContent } = useFileContent(
    projectId,
    commitSha,
    selectedFilePath,
  );

  const files = fileTree?.files || [];

  // Build folder structure
  const buildTree = () => {
    const tree: Record<string, unknown[]> = { "/": [] };

    files.forEach((file) => {
      const parts = file.file_path.split("/");
      let currentPath = "";

      parts.forEach((part, index) => {
        const parentPath = currentPath || "/";
        currentPath = currentPath ? `${currentPath}/${part}` : part;

        if (index === parts.length - 1) {
          // It's a file
          if (!tree[parentPath]) tree[parentPath] = [];
          tree[parentPath].push({ type: "file", ...file });
        } else {
          // It's a folder
          if (!tree[parentPath]) tree[parentPath] = [];
          if (!tree[parentPath].some((item: any) => item.type === "folder" && item.name === part)) {
            tree[parentPath].push({ type: "folder", name: part, path: currentPath });
          }
          if (!tree[currentPath]) tree[currentPath] = [];
        }
      });
    });

    return tree;
  };

  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedFolders(newExpanded);
  };

  return (
    <div className="flex h-full gap-4">
      {/* File tree panel */}
      <div className="w-1/3 min-w-[250px] overflow-hidden rounded-lg border border-white/10 bg-zinc-900/50 backdrop-blur-xl">
        <div className="border-b border-white/10 p-4">
          <div className="flex items-center gap-2">
            <Folder className="h-5 w-5 text-cyan-400" />
            <h3 className="font-medium text-white">Files</h3>
            <span className="ml-auto text-sm text-zinc-400">{files.length}</span>
          </div>
        </div>

        <div className="overflow-y-auto p-2">
          {isLoading && (
            <div className="flex h-32 items-center justify-center">
              <div className="text-sm text-zinc-400">Loading files...</div>
            </div>
          )}

          {!isLoading && files.length === 0 && (
            <div className="flex h-32 items-center justify-center">
              <div className="text-sm text-zinc-400">No files found</div>
            </div>
          )}

          {!isLoading && files.length > 0 && (
            <div className="space-y-1">
              {files.map((file) => (
                <FileTreeItem
                  key={file.file_path}
                  file={file}
                  isSelected={file.file_path === selectedFilePath}
                  onClick={() => !file.is_binary && setSelectedFilePath(file.file_path)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Code viewer panel */}
      <div className="flex-1 overflow-hidden">
        {selectedFilePath && fileContent ? (
          <CodeViewer
            content={fileContent.content}
            filePath={fileContent.file_path}
            language={fileContent.language}
            isLoading={isLoadingContent}
          />
        ) : (
          <div className="flex h-full items-center justify-center rounded-lg border border-white/10 bg-zinc-900/50 backdrop-blur-xl">
            <div className="text-center">
              <FileCode className="mx-auto mb-3 h-12 w-12 text-zinc-600" />
              <p className="text-sm text-zinc-400">Select a file to view its content</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
