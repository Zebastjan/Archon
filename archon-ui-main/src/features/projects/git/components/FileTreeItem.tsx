/**
 * File Tree Item Component
 * Individual file/folder item in the tree
 */

import { File, FileCode, FileText } from "lucide-react";
import type { GitFile } from "../types";

interface FileTreeItemProps {
  file: GitFile;
  isSelected: boolean;
  onClick: () => void;
}

export const FileTreeItem = ({ file, isSelected, onClick }: FileTreeItemProps) => {
  const getFileIcon = () => {
    if (file.is_binary) return <File className="h-4 w-4 text-zinc-500" />;
    if (file.language) return <FileCode className="h-4 w-4 text-cyan-400" />;
    return <FileText className="h-4 w-4 text-zinc-400" />;
  };

  return (
    <button
      onClick={onClick}
      disabled={file.is_binary}
      className={`w-full rounded px-3 py-2 text-left text-sm transition-all ${
        isSelected
          ? "bg-cyan-500/20 text-cyan-300"
          : file.is_binary
            ? "cursor-not-allowed text-zinc-600"
            : "text-zinc-300 hover:bg-white/5"
      }`}
      type="button"
      title={file.is_binary ? "Binary file (cannot preview)" : file.file_path}
    >
      <div className="flex items-center gap-2">
        {getFileIcon()}
        <span className="truncate">{file.file_name}</span>
        {file.language && (
          <span className="ml-auto text-xs text-zinc-500">{file.language}</span>
        )}
      </div>
    </button>
  );
};
