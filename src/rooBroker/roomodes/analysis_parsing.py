from typing import Optional, List


def extract_strategy_from_analysis(analysis: str, context: str = "coding") -> Optional[str]:
    """Extract a concise strategy from prompt improvement analysis."""
    if not analysis or len(analysis) < 20:
        return None
    cleaned = analysis.replace("Analysis failed:", "").strip()
    phrases = [
        "be more specific", "provide context", "include examples",
        "break down", "step by step", "clarify", "specify",
        "detailed", "clear instructions", "format"
    ]
    for phrase in phrases:
        if phrase in cleaned.lower():
            sentences = cleaned.split('.')
            for sentence in sentences:
                if phrase in sentence.lower() and len(sentence) > 15:
                    return sentence.strip().capitalize()
    if len(cleaned) > 150:
        return cleaned[:150].strip() + "..."
    return cleaned.capitalize()


def extract_core_insight(analysis: str) -> str:
    """Extract the core insight from an analysis, limited to 100 chars."""
    if not analysis or len(analysis) < 10:
        return ""
    cleaned = analysis.replace("Analysis failed:", "").strip()
    if '.' in cleaned:
        first_sentence = cleaned.split('.')[0].strip()
        if len(first_sentence) > 10:
            return first_sentence
    if len(cleaned) > 100:
        return cleaned[:100] + "..."
    return cleaned


def extract_coding_insights(analysis: str, task_type: str) -> Optional[List[str]]:
    """Extract coding-specific insights from prompt analysis."""
    if not analysis or len(analysis) < 20 or 'HTTPConnectionPool' in analysis:
        return None
        
    # Clean up the analysis text
    cleaned = analysis.replace("Analysis failed:", "").strip()
    
    # Task-specific extraction patterns
    if task_type == 'complex':
        # For complex tasks, look for refactoring, optimization, and algorithm insights
        coding_patterns = [
            "refactor", "optimize", "algorithm", "pattern", 
            "efficiency", "complex", "structure", "design"
        ]
    elif task_type == 'moderate':
        # For moderate tasks, look for function design and implementation insights
        coding_patterns = [
            "function", "implementation", "parameter", "return",
            "class", "method", "interface", "API"
        ]
    else:  # simple tasks
        # For simple tasks, look for basic syntax and clarity insights
        coding_patterns = [
            "syntax", "clarity", "basic", "simple", "explain",
            "variable", "statement", "expression"
        ]
    
    # Find relevant insights
    insights: List[str] = []
    sentences = cleaned.split('.')
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 15:
            for pattern in coding_patterns:
                if pattern in sentence.lower():
                    # Clean and format
                    insight = sentence.capitalize()
                    if len(insight) > 120:
                        insight = insight[:120] + "..."
                    insights.append(insight)
                    break  # One match per sentence is enough
    
    return insights if insights else None
