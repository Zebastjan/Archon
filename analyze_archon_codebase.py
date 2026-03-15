#!/usr/bin/env python3
"""
Archon Codebase Analysis Report Generator

Uses Tree-sitter extraction to analyze the Archon codebase structure,
identifying patterns, quality metrics, and architectural insights.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# Add Python src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "python" / "src"))

from server.services.languages import get_language_for_file
from server.services.languages.language_support import CodeEntity, CodeRelationship


class CodebaseAnalyzer:
    """Analyzes codebase structure using Tree-sitter extraction."""
    
    def __init__(self, root_path: Path):
        self.root = root_path
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        self.files_analyzed = 0
        self.errors: list[str] = []
        
    def analyze(self) -> dict[str, Any]:
        """Run full analysis of the codebase."""
        print("🔍 Analyzing Archon codebase...")
        print(f"   Root: {self.root}")
        
        # Discover and analyze all source files
        self._discover_and_parse_files()
        
        # Generate report sections
        report = {
            "overview": self._generate_overview(),
            "language_distribution": self._analyze_languages(),
            "entity_breakdown": self._analyze_entity_types(),
            "complexity_metrics": self._analyze_complexity(),
            "documentation_coverage": self._analyze_documentation(),
            "module_structure": self._analyze_modules(),
            "relationship_graph": self._analyze_relationships(),
            "quality_indicators": self._analyze_quality(),
            "architecture_insights": self._analyze_architecture(),
        }
        
        return report
    
    def _discover_and_parse_files(self):
        """Find and parse all source files."""
        print("\n📁 Discovering source files...")
        
        # Patterns to analyze
        patterns = [
            "python/src/**/*.py",
            "archon-ui-main/src/**/*.{ts,tsx}",
        ]
        
        files_found = []
        for pattern in patterns:
            if "python" in pattern:
                files_found.extend(self.root.glob(pattern))
            elif "archon-ui-main" in pattern:
                ui_root = self.root / "archon-ui-main"
                if ui_root.exists():
                    files_found.extend(ui_root.glob("src/**/*.{ts,tsx}"))
        
        # Filter to supported languages
        for file_path in files_found:
            if file_path.is_file() and not self._should_skip(file_path):
                lang_support = get_language_for_file(str(file_path))
                if lang_support:
                    self._parse_file(file_path, lang_support)
        
        print(f"   Analyzed {self.files_analyzed} files")
        print(f"   Found {len(self.entities)} entities")
        print(f"   Found {len(self.relationships)} relationships")
        if self.errors:
            print(f"   Errors: {len(self.errors)}")
    
    def _should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            "/tests/", "/test_", "__pycache__", ".pyc", "/fixtures/",
            "/node_modules/", "/dist/", "/build/", ".min.js", ".d.ts"
        ]
        path_str = str(file_path)
        return any(pattern in path_str for pattern in skip_patterns)
    
    def _parse_file(self, file_path: Path, lang_support):
        """Parse a single file and extract entities."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if not content.strip():
                return
            
            entities, relationships = lang_support.extract_entities_and_relationships(
                content, str(file_path.relative_to(self.root))
            )
            
            self.entities.extend(entities)
            self.relationships.extend(relationships)
            self.files_analyzed += 1
            
        except Exception as e:
            self.errors.append(f"{file_path}: {e}")
    
    def _generate_overview(self) -> dict[str, Any]:
        """Generate high-level overview metrics."""
        return {
            "files_analyzed": self.files_analyzed,
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "errors_encountered": len(self.errors),
        }
    
    def _analyze_languages(self) -> dict[str, Any]:
        """Analyze language distribution."""
        lang_counts = Counter(e.metadata.get('language', 'unknown') for e in self.entities)
        
        return {
            "by_language": dict(lang_counts.most_common()),
            "primary_language": lang_counts.most_common(1)[0][0] if lang_counts else None,
            "language_diversity": len(lang_counts),
        }
    
    def _analyze_entity_types(self) -> dict[str, Any]:
        """Analyze breakdown by entity type."""
        type_counts = Counter(e.entity_type for e in self.entities)
        
        # Calculate averages
        functions = [e for e in self.entities if e.entity_type == 'function']
        classes = [e for e in self.entities if e.entity_type == 'class']
        methods = [e for e in self.entities if e.entity_type == 'method']
        
        avg_func_lines = sum(e.line_end - e.line_start for e in functions) / len(functions) if functions else 0
        avg_class_methods = len(methods) / len(classes) if classes else 0
        
        return {
            "by_type": dict(type_counts.most_common()),
            "total_functions": len(functions),
            "total_classes": len(classes),
            "total_methods": len(methods),
            "avg_function_length_lines": round(avg_func_lines, 2),
            "avg_methods_per_class": round(avg_class_methods, 2),
        }
    
    def _analyze_complexity(self) -> dict[str, Any]:
        """Analyze code complexity metrics."""
        # Size distribution
        sizes = [e.line_end - e.line_start for e in self.entities]
        
        if not sizes:
            return {}
        
        # Identify large entities (potential god classes/functions)
        large_threshold = 50  # lines
        large_entities = [
            {
                "name": e.name,
                "type": e.entity_type,
                "lines": e.line_end - e.line_start,
                "file": e.metadata.get('file_path', 'unknown')
            }
            for e in self.entities
            if e.line_end - e.line_start > large_threshold
        ]
        large_entities.sort(key=lambda x: x["lines"], reverse=True)
        
        return {
            "size_distribution": {
                "min_lines": min(sizes),
                "max_lines": max(sizes),
                "avg_lines": round(sum(sizes) / len(sizes), 2),
                "median_lines": sorted(sizes)[len(sizes) // 2],
            },
            "large_entities_count": len(large_entities),
            "largest_entities": large_entities[:10],  # Top 10
        }
    
    def _analyze_documentation(self) -> dict[str, Any]:
        """Analyze documentation coverage."""
        total = len(self.entities)
        with_docstrings = sum(1 for e in self.entities if e.docstring)
        without_docstrings = total - with_docstrings
        
        coverage_pct = (with_docstrings / total * 100) if total > 0 else 0
        
        # By entity type
        by_type = defaultdict(lambda: {"total": 0, "with_docs": 0})
        for e in self.entities:
            by_type[e.entity_type]["total"] += 1
            if e.docstring:
                by_type[e.entity_type]["with_docs"] += 1
        
        type_coverage = {
            t: {
                "total": data["total"],
                "with_docs": data["with_docs"],
                "coverage_pct": round(data["with_docs"] / data["total"] * 100, 1)
            }
            for t, data in by_type.items()
        }
        
        return {
            "overall_coverage_pct": round(coverage_pct, 1),
            "entities_with_docstrings": with_docstrings,
            "entities_without_docstrings": without_docstrings,
            "by_entity_type": type_coverage,
            "well_documented_entities": [
                {"name": e.name, "type": e.entity_type, "file": e.metadata.get('file_path')}
                for e in self.entities
                if e.docstring and len(e.docstring) > 50
            ][:10],
        }
    
    def _analyze_modules(self) -> dict[str, Any]:
        """Analyze module/file structure."""
        # Group by file
        by_file = defaultdict(list)
        for e in self.entities:
            file_path = e.metadata.get('file_path', 'unknown')
            by_file[file_path].append(e)
        
        # File complexity metrics
        file_metrics = []
        for file_path, entities in by_file.items():
            file_metrics.append({
                "file": file_path,
                "entity_count": len(entities),
                "functions": len([e for e in entities if e.entity_type == 'function']),
                "classes": len([e for e in entities if e.entity_type == 'class']),
                "methods": len([e for e in entities if e.entity_type == 'method']),
            })
        
        # Sort by complexity
        file_metrics.sort(key=lambda x: x["entity_count"], reverse=True)
        
        # Identify module patterns
        module_groups = defaultdict(int)
        for file_path in by_file.keys():
            parts = file_path.split('/')
            if len(parts) > 1:
                module_groups[parts[0]] += 1
        
        return {
            "total_files_with_entities": len(by_file),
            "avg_entities_per_file": round(len(self.entities) / len(by_file), 2) if by_file else 0,
            "most_complex_files": file_metrics[:10],
            "module_distribution": dict(module_groups.most_common()) if hasattr(module_groups, 'most_common') else dict(module_groups),
        }
    
    def _analyze_relationships(self) -> dict[str, Any]:
        """Analyze entity relationships."""
        if not self.relationships:
            return {"total_relationships": 0}
        
        by_type = Counter(r.relationship_type for r in self.relationships)
        
        # Find highly connected entities
        entity_connections = defaultdict(lambda: {"incoming": 0, "outgoing": 0})
        for r in self.relationships:
            entity_connections[r.source_name]["outgoing"] += 1
            entity_connections[r.target_name]["incoming"] += 1
        
        # Top connected entities
        top_connected = sorted(
            [
                {
                    "name": name,
                    "total_connections": data["incoming"] + data["outgoing"],
                    "incoming": data["incoming"],
                    "outgoing": data["outgoing"],
                }
                for name, data in entity_connections.items()
            ],
            key=lambda x: x["total_connections"],
            reverse=True
        )[:10]
        
        return {
            "total_relationships": len(self.relationships),
            "by_type": dict(by_type.most_common()),
            "most_connected_entities": top_connected,
        }
    
    def _analyze_quality(self) -> dict[str, Any]:
        """Analyze code quality indicators."""
        findings = []
        
        # Very long functions
        very_long = [e for e in self.entities if e.line_end - e.line_start > 100]
        if very_long:
            findings.append({
                "type": "very_long_entities",
                "severity": "warning",
                "count": len(very_long),
                "description": f"Found {len(very_long)} entities longer than 100 lines",
                "examples": [e.name for e in very_long[:3]]
            })
        
        # Undocumented public APIs (classes and functions)
        public_undocumented = [
            e for e in self.entities
            if e.entity_type in ('class', 'function') 
            and not e.docstring
            and not e.name.startswith('_')
        ]
        if public_undocumented:
            findings.append({
                "type": "undocumented_public_api",
                "severity": "info",
                "count": len(public_undocumented),
                "description": f"{len(public_undocumented)} public classes/functions lack docstrings",
            })
        
        # Deeply nested (indicated by long methods in classes)
        large_classes = [
            e for e in self.entities
            if e.entity_type == 'class' and e.line_end - e.line_start > 200
        ]
        if large_classes:
            findings.append({
                "type": "large_classes",
                "severity": "warning",
                "count": len(large_classes),
                "description": f"Found {len(large_classes)} classes larger than 200 lines",
            })
        
        return {
            "score": self._calculate_quality_score(),
            "findings": findings,
        }
    
    def _calculate_quality_score(self) -> int:
        """Calculate an overall quality score (0-100)."""
        if not self.entities:
            return 0
        
        score = 100
        
        # Deduct for missing documentation
        doc_coverage = sum(1 for e in self.entities if e.docstring) / len(self.entities)
        score -= int((1 - doc_coverage) * 20)  # Up to 20 points off
        
        # Deduct for very long entities
        long_pct = len([e for e in self.entities if e.line_end - e.line_start > 50]) / len(self.entities)
        score -= int(long_pct * 15)  # Up to 15 points off
        
        # Deduct for high complexity
        if len(self.entities) > 1000:
            score -= 5  # Large codebase complexity penalty
        
        return max(0, min(100, score))
    
    def _analyze_architecture(self) -> dict[str, Any]:
        """Analyze architectural patterns."""
        insights = []
        
        # Layer detection based on file paths
        layers = defaultdict(list)
        for e in self.entities:
            file_path = e.metadata.get('file_path', '')
            if 'services/' in file_path:
                layers['services'].append(e)
            elif 'api/' in file_path or 'routes/' in file_path:
                layers['api'].append(e)
            elif 'database/' in file_path or 'db_' in file_path:
                layers['database'].append(e)
            elif 'mcp_' in file_path or 'mcp/' in file_path:
                layers['mcp'].append(e)
            elif 'git' in file_path.lower():
                layers['git'].append(e)
        
        # Service layer analysis
        if layers['services']:
            service_classes = [e for e in layers['services'] if e.entity_type == 'class']
            insights.append({
                "pattern": "service_layer",
                "description": f"Detected service layer pattern with {len(service_classes)} service classes",
                "examples": [e.name for e in service_classes[:5]]
            })
        
        # MCP architecture
        if layers['mcp']:
            mcp_tools = [e for e in layers['mcp'] if 'tool' in e.name.lower()]
            insights.append({
                "pattern": "mcp_architecture",
                "description": f"MCP server architecture with {len(mcp_tools)} tool-related entities",
                "examples": list(set(e.name for e in mcp_tools))[:5]
            })
        
        # API surface
        api_funcs = [e for e in self.entities if e.entity_type == 'function' and 'api' in e.metadata.get('file_path', '').lower()]
        if api_funcs:
            insights.append({
                "pattern": "api_surface",
                "description": f"API layer with {len(api_funcs)} functions",
            })
        
        return {
            "detected_layers": {k: len(v) for k, v in layers.items()},
            "architectural_patterns": insights,
        }


def print_report(report: dict[str, Any]):
    """Print formatted report to console."""
    print("\n" + "=" * 80)
    print("ARCHON CODEBASE ANALYSIS REPORT")
    print("=" * 80)
    
    # Overview
    print("\n📊 OVERVIEW")
    print("-" * 40)
    overview = report["overview"]
    print(f"  Files analyzed:     {overview['files_analyzed']:,}")
    print(f"  Total entities:     {overview['total_entities']:,}")
    print(f"  Relationships:      {overview['total_relationships']:,}")
    print(f"  Errors:             {overview['errors_encountered']}")
    
    # Languages
    print("\n🌐 LANGUAGE DISTRIBUTION")
    print("-" * 40)
    for lang, count in report["language_distribution"]["by_language"].items():
        pct = count / report["overview"]["total_entities"] * 100
        bar = "█" * int(pct / 5)
        print(f"  {lang:12} {count:5,} ({pct:5.1f}%) {bar}")
    
    # Entity breakdown
    print("\n📦 ENTITY BREAKDOWN")
    print("-" * 40)
    breakdown = report["entity_breakdown"]
    for etype, count in breakdown["by_type"].items():
        print(f"  {etype:15} {count:5,}")
    print(f"\n  Avg function length: {breakdown['avg_function_length_lines']} lines")
    print(f"  Avg methods/class:   {breakdown['avg_methods_per_class']}")
    
    # Complexity
    print("\n📏 COMPLEXITY METRICS")
    print("-" * 40)
    complexity = report["complexity_metrics"]
    dist = complexity["size_distribution"]
    print(f"  Size range: {dist['min_lines']} - {dist['max_lines']} lines")
    print(f"  Average:    {dist['avg_lines']:.1f} lines")
    print(f"  Median:     {dist['median_lines']} lines")
    print(f"\n  Large entities (>50 lines): {complexity['large_entities_count']}")
    if complexity["largest_entities"]:
        print("\n  Largest entities:")
        for e in complexity["largest_entities"][:5]:
            print(f"    - {e['name']} ({e['type']}): {e['lines']} lines")
    
    # Documentation
    print("\n📝 DOCUMENTATION COVERAGE")
    print("-" * 40)
    docs = report["documentation_coverage"]
    print(f"  Overall coverage: {docs['overall_coverage_pct']}%")
    print(f"  With docstrings:  {docs['entities_with_docstrings']:,}")
    print(f"  Without:          {docs['entities_without_docstrings']:,}")
    print("\n  By type:")
    for etype, data in docs["by_entity_type"].items():
        print(f"    {etype:12} {data['coverage_pct']:5.1f}% ({data['with_docs']}/{data['total']})")
    
    # Quality
    print("\n✨ QUALITY INDICATORS")
    print("-" * 40)
    quality = report["quality_indicators"]
    print(f"  Quality score: {quality['score']}/100")
    if quality["findings"]:
        print("\n  Findings:")
        for finding in quality["findings"]:
            icon = "⚠️" if finding["severity"] == "warning" else "ℹ️"
            print(f"    {icon} {finding['description']}")
    else:
        print("  ✅ No major quality issues detected")
    
    # Architecture
    print("\n🏗️ ARCHITECTURE INSIGHTS")
    print("-" * 40)
    arch = report["architecture_insights"]
    print("  Detected layers:")
    for layer, count in arch["detected_layers"].items():
        print(f"    - {layer}: {count} entities")
    
    if arch["architectural_patterns"]:
        print("\n  Patterns:")
        for pattern in arch["architectural_patterns"]:
            print(f"    ✅ {pattern['description']}")
            if 'examples' in pattern:
                print(f"       Examples: {', '.join(pattern['examples'][:3])}")
    
    # Relationships
    if report["relationship_graph"]["total_relationships"] > 0:
        print("\n🔗 RELATIONSHIP GRAPH")
        print("-" * 40)
        rel = report["relationship_graph"]
        print(f"  Total relationships: {rel['total_relationships']}")
        print("\n  By type:")
        for rtype, count in rel["by_type"].items():
            print(f"    {rtype}: {count}")
    
    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


def main():
    """Main entry point."""
    root_path = Path("/home/zebastjan/dev/archon")
    
    analyzer = CodebaseAnalyzer(root_path)
    report = analyzer.analyze()
    
    print_report(report)
    
    # Save JSON report
    report_path = root_path / "codebase_analysis_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Full JSON report saved to: {report_path}")


if __name__ == "__main__":
    main()
