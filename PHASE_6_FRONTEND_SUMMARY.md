# Phase 6: Frontend Updates - Summary

## Overview

Phase 6 adds UI support for the Tavily provider integration, allowing users to select their preferred crawling provider and view which provider was used for each knowledge source.

## Changes Made

### 1. Type Updates

**File:** `archon-ui-main/src/features/knowledge/types/knowledge.ts`

**CrawlRequest Interface:**
```typescript
export interface CrawlRequest {
  url: string;
  knowledge_type?: "technical" | "business";
  tags?: string[];
  update_frequency?: number;
  max_depth?: number;
  extract_code_examples?: boolean;
  crawl_provider?: "tavily" | "crawl4ai" | null; // NEW: Optional provider override
}
```

**KnowledgeItemMetadata Interface:**
```typescript
export interface KnowledgeItemMetadata {
  // ... existing fields ...
  crawl_provider?: string; // NEW: Crawl provider used (tavily, crawl4ai)
  provider_metadata?: {    // NEW: Provider-specific metadata
    pages_crawled?: number;
    total_credits_used?: number;
    fallback_used?: boolean;
    fallback_reason?: string;
  };
}
```

### 2. Provider Selector Component

**File:** `archon-ui-main/src/features/knowledge/components/ProviderSelector.tsx` (NEW)

**Features:**
- Three-option selector: Auto (default), Tavily, Crawl4AI
- Visual design matching existing LevelSelector component
- Color-coded icons:
  - Auto: Purple sparkle icon
  - Tavily: Cyan lightning bolt icon
  - Crawl4AI: Blue bot icon
- Tooltips with provider descriptions:
  - Auto: "Uses default provider from settings • Fallback enabled"
  - Tavily: "Best for: JS-heavy sites, clean content • Costs credits"
  - Crawl4AI: "Best for: Static sites, deep crawls • Free, unlimited"
- Keyboard navigation support
- Disabled state handling

**Component Pattern:**
- Follows same glassmorphism style as other selectors
- Edge-lit effect on selected option
- Hover and click animations
- Responsive grid layout (3 columns)

### 3. Add Knowledge Dialog Updates

**File:** `archon-ui-main/src/features/knowledge/components/AddKnowledgeDialog.tsx`

**Changes:**
1. **New Import:**
   ```typescript
   import { ProviderSelector } from "./ProviderSelector";
   ```

2. **New State:**
   ```typescript
   const [crawlProvider, setCrawlProvider] = useState<"tavily" | "crawl4ai" | null>(null);
   ```

3. **Form Integration:**
   - Added ProviderSelector between LevelSelector and TagInput
   - Included in resetForm() to reset to Auto
   - Included in CrawlRequest when submitting:
     ```typescript
     crawl_provider: crawlProvider, // null = Auto
     ```

### 4. Knowledge Card Updates

**File:** `archon-ui-main/src/features/knowledge/components/KnowledgeCard.tsx`

**Changes:**
1. **New Icons:**
   ```typescript
   import { ..., Zap, Bot } from "lucide-react";
   ```

2. **Provider Data Extraction:**
   ```typescript
   const crawlProvider = item.metadata?.crawl_provider;
   const providerMetadata = item.metadata?.provider_metadata;
   const creditsUsed = providerMetadata?.total_credits_used;
   const fallbackUsed = providerMetadata?.fallback_used;
   ```

3. **Provider Badge Display:**
   - Added after code examples stat pill in footer
   - Conditional rendering (only shows if provider is set)
   - Visual elements:
     - Tavily: Cyan lightning bolt icon + "Tavily" text
     - Crawl4AI: Blue bot icon + "Crawl4AI" text
     - Fallback indicator: Orange "!" if fallback was used
   - Tooltip shows:
     - Provider name
     - Credits used (for Tavily)
     - Fallback status if applicable

**Provider Badge Design:**
```tsx
<div className="flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50">
  {/* Icon */}
  {/* Provider name */}
  {/* Fallback indicator */}
</div>
```

## User Experience Flow

### Adding Knowledge with Provider Selection

1. **Open Add Knowledge Dialog**
2. **Fill in URL** (required)
3. **Select Knowledge Type** (Technical/Business)
4. **Select Crawl Depth** (1-5 levels)
5. **Select Provider** (NEW):
   - Auto: Uses default from settings
   - Tavily: Modern crawler for JS-heavy sites
   - Crawl4AI: Traditional crawler, free
6. **Add Tags** (optional)
7. **Submit** - Provider choice is sent to backend

### Viewing Provider Information

**On Knowledge Cards:**
- Provider badge shows in footer next to document/code stats
- Tavily badge shows credits consumed
- Fallback indicator (!) appears if provider fell back
- Hover tooltip provides additional details

**Example Tooltips:**
- Tavily success: "Crawled with Tavily (45 credits)"
- Tavily fallback: "Crawled with Crawl4AI • Fallback used"
- Crawl4AI: "Crawled with Crawl4AI"

## Visual Design

### Provider Selector

**Auto Option:**
- Color: Purple
- Icon: Sparkles
- Description: "Automatic selection"

**Tavily Option:**
- Color: Cyan
- Icon: Lightning bolt (Zap)
- Description: "Modern sites"

**Crawl4AI Option:**
- Color: Blue
- Icon: Robot (Bot)
- Description: "Traditional crawling"

### Provider Badge

**Styling:**
- Glassmorphism design matching card style
- Gray background with subtle border
- Icon colored based on provider (cyan/blue)
- Small, compact size to fit in footer
- Hover tooltip for detailed info

## Accessibility

- **Keyboard Navigation**: All selectors support Enter/Space key activation
- **ARIA Labels**: Provider selector has proper role="radio" and aria-checked
- **Tooltips**: All elements have descriptive tooltips
- **Focus Indicators**: Visible focus rings on keyboard navigation

## Backward Compatibility

- **Optional Field**: `crawl_provider` is optional in API requests
- **Null Handling**: Missing provider data doesn't break UI
- **Conditional Rendering**: Provider badge only shows when data exists
- **Default Behavior**: Auto (null) uses backend's default provider

## Files Modified

1. `archon-ui-main/src/features/knowledge/types/knowledge.ts` - Type definitions
2. `archon-ui-main/src/features/knowledge/components/AddKnowledgeDialog.tsx` - Form integration
3. `archon-ui-main/src/features/knowledge/components/KnowledgeCard.tsx` - Provider display

## Files Created

1. `archon-ui-main/src/features/knowledge/components/ProviderSelector.tsx` - New component

## Testing Recommendations

### Manual Testing

1. **Provider Selector:**
   ```
   - Open Add Knowledge dialog
   - Verify all three provider options display correctly
   - Test keyboard navigation (Tab, Enter, Space)
   - Verify tooltips appear on hover
   - Test selection state visuals (edge-lit effect)
   ```

2. **Form Submission:**
   ```
   - Select Auto provider → Submit → Verify request sent without provider
   - Select Tavily → Submit → Verify request includes crawl_provider: "tavily"
   - Select Crawl4AI → Submit → Verify request includes crawl_provider: "crawl4ai"
   ```

3. **Provider Badge Display:**
   ```
   - Crawl with Tavily → Verify cyan Zap icon + "Tavily" + credits
   - Crawl with Crawl4AI → Verify blue Bot icon + "Crawl4AI"
   - Trigger fallback → Verify orange "!" indicator
   - Hover badge → Verify tooltip shows details
   ```

4. **Dark Mode:**
   ```
   - Test provider selector in dark mode
   - Test provider badge in dark mode
   - Verify contrast and readability
   ```

### Edge Cases

- Missing provider data → Badge doesn't render
- Missing credits → Shows provider without credit count
- Fallback scenario → Shows fallback indicator
- Old sources (no provider) → No badge shown

## Next Steps

**Phase 7 Remaining Tasks:**

1. **Settings UI for Tavily API Key:**
   - Add encrypted input field in Settings page
   - Add default provider dropdown (Tavily/Crawl4AI)
   - Save to backend settings

2. **Integration Testing:**
   - Test full flow: Select provider → Crawl → View results
   - Test fallback scenarios
   - Test with real Tavily API key

3. **Production Hardening:**
   - Error handling for provider selection
   - Loading states during crawl
   - Better fallback messaging

## Success Criteria

- ✅ Users can select crawl provider in UI
- ✅ Provider selection is sent to backend
- ✅ Provider info displayed on knowledge cards
- ✅ Credits usage shown for Tavily
- ✅ Fallback indicator visible when used
- ✅ Backward compatible with existing data
- ✅ Matches existing UI design patterns

**Phase 6: Frontend Updates = COMPLETE** ✅

## Screenshots (Conceptual)

**Provider Selector in Dialog:**
```
┌─────────────────────────────────────────┐
│  Crawl Provider               ⓘ        │
│  ┌───────┐  ┌───────┐  ┌───────┐     │
│  │  ✨   │  │  ⚡   │  │  🤖   │     │
│  │ Auto  │  │Tavily │  │Crawl4AI│     │
│  │ [lit] │  │       │  │       │     │
│  └───────┘  └───────┘  └───────┘     │
└─────────────────────────────────────────┘
```

**Provider Badge on Card:**
```
Footer: [📄 15]  [💻 8]  [⚡ Tavily !]
                          ^^^^^^^^^
                        Provider badge
```
