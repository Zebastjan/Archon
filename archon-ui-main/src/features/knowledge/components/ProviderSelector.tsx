/**
 * Provider Selection Component
 * Selector for web crawl provider (Tavily, Crawl4AI, or Auto)
 */

import { motion } from "framer-motion";
import { Info, Zap, Bot, Sparkles } from "lucide-react";
import { cn, glassCard } from "../../ui/primitives/styles";
import { SimpleTooltip, Tooltip, TooltipContent, TooltipTrigger } from "../../ui/primitives/tooltip";

interface ProviderSelectorProps {
  value: string | null;
  onValueChange: (value: string | null) => void;
  disabled?: boolean;
}

const PROVIDERS = [
  {
    value: null,
    label: "Auto",
    icon: Sparkles,
    description: "Automatic selection",
    details: "Uses default provider from settings • Fallback enabled",
    color: "purple" as const,
  },
  {
    value: "tavily",
    label: "Tavily",
    icon: Zap,
    description: "Modern sites",
    details: "Best for: JS-heavy sites, clean content • Costs credits",
    color: "cyan" as const,
  },
  {
    value: "crawl4ai",
    label: "Crawl4AI",
    icon: Bot,
    description: "Traditional crawling",
    details: "Best for: Static sites, deep crawls • Free, unlimited",
    color: "blue" as const,
  },
];

export const ProviderSelector: React.FC<ProviderSelectorProps> = ({ value, onValueChange, disabled = false }) => {
  const tooltipContent = (
    <div className="space-y-2 max-w-xs">
      <div className="font-semibold mb-2 text-sm">Crawl Providers:</div>
      {PROVIDERS.map((provider) => (
        <div key={provider.value ?? "auto"} className="space-y-0.5">
          <div className="text-xs font-medium">
            {provider.label}: {provider.description}
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 pl-2">{provider.details}</div>
        </div>
      ))}
      <div className="mt-2 pt-2 border-t border-gray-600 dark:border-gray-500 text-xs">
        💡 Auto mode uses Tavily if configured, falls back to Crawl4AI
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="text-sm font-medium text-gray-900 dark:text-white/90" id="crawl-provider-label">
            Crawl Provider
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-gray-400 hover:text-cyan-500 transition-colors cursor-help"
                aria-label="Show crawl provider details"
              >
                <Info className="w-4 h-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">{tooltipContent}</TooltipContent>
          </Tooltip>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">Choose the crawling engine</div>
      </div>
      <div className="grid grid-cols-3 gap-3" role="radiogroup" aria-labelledby="crawl-provider-label">
        {PROVIDERS.map((provider) => {
          const isSelected = value === provider.value;
          const Icon = provider.icon;
          const colorClass =
            provider.color === "purple"
              ? "text-purple-700 dark:text-purple-400"
              : provider.color === "cyan"
                ? "text-cyan-700 dark:text-cyan-400"
                : "text-blue-700 dark:text-blue-400";

          const borderClass =
            provider.color === "purple"
              ? glassCard.edgeColors.purple.border
              : provider.color === "cyan"
                ? glassCard.edgeColors.cyan.border
                : glassCard.edgeColors.blue.border;

          const tintClass =
            provider.color === "purple"
              ? glassCard.tints.purple.light
              : provider.color === "cyan"
                ? glassCard.tints.cyan.light
                : glassCard.tints.blue.light;

          const edgeLitClass =
            provider.color === "purple"
              ? {
                  line: glassCard.edgeLit.color.purple.line,
                  glow: glassCard.edgeLit.color.purple.glow,
                  gradient: glassCard.edgeLit.color.purple.gradient.vertical,
                }
              : provider.color === "cyan"
                ? {
                    line: glassCard.edgeLit.color.cyan.line,
                    glow: glassCard.edgeLit.color.cyan.glow,
                    gradient: glassCard.edgeLit.color.cyan.gradient.vertical,
                  }
                : {
                    line: glassCard.edgeLit.color.blue.line,
                    glow: glassCard.edgeLit.color.blue.glow,
                    gradient: glassCard.edgeLit.color.blue.gradient.vertical,
                  };

          return (
            <motion.div
              key={provider.value ?? "auto"}
              whileHover={!disabled ? { scale: 1.05 } : {}}
              whileTap={!disabled ? { scale: 0.95 } : {}}
            >
              <SimpleTooltip content={provider.details}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  aria-label={`${provider.label}: ${provider.description}`}
                  tabIndex={isSelected ? 0 : -1}
                  onClick={() => !disabled && onValueChange(provider.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      if (!disabled) onValueChange(provider.value);
                    }
                  }}
                  disabled={disabled}
                  className={cn(
                    "relative w-full h-20 rounded-xl transition-all duration-200",
                    "flex flex-col items-center justify-center gap-1",
                    glassCard.base,
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2",
                    isSelected ? borderClass : "border border-gray-300/50 dark:border-gray-700/50",
                    isSelected ? tintClass : glassCard.transparency.light,
                    !disabled && !isSelected && "hover:border-cyan-400/50",
                    disabled && "opacity-50 cursor-not-allowed",
                  )}
                >
                  {/* Top edge-lit effect for selected state */}
                  {isSelected && (
                    <>
                      <div
                        className={cn(
                          "absolute inset-x-0 top-0 h-[2px] pointer-events-none z-10",
                          glassCard.edgeLit.position.top,
                          edgeLitClass.line,
                          edgeLitClass.glow,
                        )}
                      />
                      <div
                        className={cn(
                          "absolute inset-x-0 top-0 h-16 bg-gradient-to-b to-transparent blur-lg pointer-events-none z-10",
                          edgeLitClass.gradient,
                        )}
                      />
                    </>
                  )}

                  {/* Provider icon */}
                  <Icon className={cn("w-6 h-6", isSelected ? colorClass : "text-gray-500 dark:text-gray-400")} />

                  {/* Provider label */}
                  <div
                    className={cn(
                      "text-sm font-semibold",
                      isSelected ? colorClass : "text-gray-700 dark:text-gray-300",
                    )}
                  >
                    {provider.label}
                  </div>

                  {/* Provider description */}
                  <div
                    className={cn(
                      "text-xs text-center leading-tight px-1",
                      isSelected ? colorClass.replace("700", "600").replace("400", "300") : "text-gray-500 dark:text-gray-400",
                    )}
                  >
                    {provider.description}
                  </div>
                </button>
              </SimpleTooltip>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
