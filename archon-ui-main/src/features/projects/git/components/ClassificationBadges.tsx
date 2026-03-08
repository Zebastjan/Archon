/**
 * Classification Badges Component
 * Displays AI-generated commit classification metadata
 */

import { AlertTriangle, Shield, Zap, TestTube, Code2, Wrench } from "lucide-react";
import type { CommitClassification } from "../types";

interface ClassificationBadgesProps {
  classification: CommitClassification;
  compact?: boolean;
}

/**
 * Get color classes for intent badge
 */
const getIntentColor = (intent: CommitClassification["intent"]) => {
  switch (intent) {
    case "feature":
      return "bg-blue-500/20 text-blue-300 border-blue-500/30";
    case "bugfix":
      return "bg-red-500/20 text-red-300 border-red-500/30";
    case "security-fix":
      return "bg-orange-500/20 text-orange-300 border-orange-500/30";
    case "performance":
      return "bg-purple-500/20 text-purple-300 border-purple-500/30";
    case "refactor":
      return "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    case "test":
      return "bg-green-500/20 text-green-300 border-green-500/30";
    case "docs":
      return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
    case "chore":
      return "bg-gray-500/20 text-gray-300 border-gray-500/30";
    default:
      return "bg-zinc-500/20 text-zinc-300 border-zinc-500/30";
  }
};

/**
 * Get color classes for risk level
 */
const getRiskColor = (risk: CommitClassification["risk_level"]) => {
  switch (risk) {
    case "high":
      return "bg-red-500/20 text-red-300 border-red-500/30";
    case "medium":
      return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
    case "low":
      return "bg-green-500/20 text-green-300 border-green-500/30";
    default:
      return "bg-zinc-500/20 text-zinc-300 border-zinc-500/30";
  }
};

/**
 * Get icon for intent
 */
const getIntentIcon = (intent: CommitClassification["intent"]) => {
  const className = "h-3 w-3";
  switch (intent) {
    case "feature":
      return <Zap className={className} />;
    case "bugfix":
      return <Wrench className={className} />;
    case "security-fix":
      return <Shield className={className} />;
    case "performance":
      return <Zap className={className} />;
    case "test":
      return <TestTube className={className} />;
    case "refactor":
      return <Code2 className={className} />;
    default:
      return null;
  }
};

export const ClassificationBadges = ({ classification, compact = false }: ClassificationBadgesProps) => {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* Intent Badge */}
      <div
        className={`flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${getIntentColor(classification.intent)}`}
        title={`Intent: ${classification.intent}`}
      >
        {getIntentIcon(classification.intent)}
        <span>{classification.intent}</span>
      </div>

      {/* Risk Level Badge */}
      <div
        className={`flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${getRiskColor(classification.risk_level)}`}
        title={`Risk: ${classification.risk_level}`}
      >
        <AlertTriangle className="h-3 w-3" />
        <span>{classification.risk_level}</span>
      </div>

      {!compact && (
        <>
          {/* Breaking Changes Badge */}
          {classification.api_breaking && (
            <div
              className="flex items-center gap-1 rounded border border-red-500/50 bg-red-500/20 px-1.5 py-0.5 text-xs font-medium text-red-300"
              title="Contains API breaking changes"
            >
              <AlertTriangle className="h-3 w-3" />
              <span>BREAKING</span>
            </div>
          )}

          {/* Security Badge */}
          {classification.security_relevant && (
            <div
              className="flex items-center gap-1 rounded border border-orange-500/50 bg-orange-500/20 px-1.5 py-0.5 text-xs font-medium text-orange-300"
              title="Has security implications"
            >
              <Shield className="h-3 w-3" />
              <span>SECURITY</span>
            </div>
          )}

          {/* Performance Impact Badge */}
          {classification.performance_impact !== "none" && (
            <div
              className="flex items-center gap-1 rounded border border-purple-500/50 bg-purple-500/20 px-1.5 py-0.5 text-xs font-medium text-purple-300"
              title={`Performance impact: ${classification.performance_impact}`}
            >
              <Zap className="h-3 w-3" />
              <span>PERF: {classification.performance_impact.toUpperCase()}</span>
            </div>
          )}

          {/* Test Coverage Badge */}
          {classification.test_coverage !== "none" && (
            <div
              className={`flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${
                classification.test_coverage === "full"
                  ? "border-green-500/50 bg-green-500/20 text-green-300"
                  : "border-yellow-500/50 bg-yellow-500/20 text-yellow-300"
              }`}
              title={`Test coverage: ${classification.test_coverage}`}
            >
              <TestTube className="h-3 w-3" />
              <span>{classification.test_coverage.toUpperCase()}</span>
            </div>
          )}
        </>
      )}

      {/* Confidence Indicator (if low) */}
      {classification.confidence < 0.7 && (
        <div
          className="rounded border border-zinc-500/50 bg-zinc-500/20 px-1.5 py-0.5 text-xs font-medium text-zinc-400"
          title={`Confidence: ${(classification.confidence * 100).toFixed(0)}%`}
        >
          {(classification.confidence * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
};

/**
 * Compact version for list views
 */
export const CompactClassificationBadge = ({ classification }: { classification: CommitClassification }) => {
  return <ClassificationBadges classification={classification} compact />;
};
