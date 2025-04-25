"""
Code quality metrics for evaluating generated code as recommended by:
'Benchmarks and Metrics for Evaluations of Code Generation: A Critical Review'
"""
from typing import Dict, Any, List, Optional
import ast
import tokenize
from io import StringIO
import math
from collections import Counter
import black
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze

class CodeQualityMetrics:
    """Evaluate code quality using multiple metrics."""
    
    @staticmethod
    def calculate_bleu(candidate: str, reference: str, max_n: int = 4) -> float:
        """
        Calculate BLEU score between candidate and reference code.
        Uses character-level n-grams as recommended by the paper for code evaluation.
        """
        def get_char_ngrams(text: str, n: int) -> List[str]:
            return [text[i:i+n] for i in range(len(text) - n + 1)]
        
        def count_ngrams(text: str, n: int) -> Counter:
            return Counter(get_char_ngrams(text, n))
        
        def modified_precision(cand: str, ref: str, n: int) -> float:
            cand_ngrams = count_ngrams(cand, n)
            ref_ngrams = count_ngrams(ref, n)
            
            if not cand_ngrams:
                return 0.0
                
            matches = sum(min(cand_ngrams[ngram], ref_ngrams[ngram]) 
                         for ngram in cand_ngrams)
            total = sum(cand_ngrams.values())
            
            return matches / total if total > 0 else 0.0
        
        # Calculate modified precisions for different n-gram sizes
        precisions = [modified_precision(candidate, reference, n) 
                     for n in range(1, max_n + 1)]
        
        # Calculate brevity penalty
        bp = math.exp(min(0, 1 - len(reference) / len(candidate))) if len(candidate) > 0 else 0
        
        # Calculate final BLEU score
        if all(p == 0 for p in precisions):
            return 0.0
        
        avg_precision = math.exp(sum(math.log(p) if p > 0 else float('-inf') 
                                   for p in precisions) / len(precisions))
        
        return bp * avg_precision
    
    @staticmethod
    def calculate_complexity_metrics(code: str) -> Dict[str, Any]:
        """
        Calculate code complexity metrics using radon.
        Returns cyclomatic complexity and maintainability index.
        """
        try:
            # Calculate cyclomatic complexity
            cc_results = cc_visit(code)
            avg_cc = sum(cc.complexity for cc in cc_results) / len(cc_results) if cc_results else 0
            
            # Calculate maintainability index
            mi_score = mi_visit(code, multi=True)
            
            # Get raw metrics (LOC, SLOC, comments, etc)
            raw_metrics = analyze(code)
            
            return {
                "cyclomatic_complexity": avg_cc,
                "maintainability_index": mi_score,
                "loc": raw_metrics.loc,
                "sloc": raw_metrics.sloc,
                "comments": raw_metrics.comments,
                "multi": raw_metrics.multi,
                "blank": raw_metrics.blank
            }
        except Exception as e:
            return {
                "error": f"Failed to calculate complexity metrics: {str(e)}"
            }
    
    @staticmethod
    def check_style_conformance(code: str) -> Dict[str, Any]:
        """
        Check if code conforms to style guidelines using black.
        Returns style conformance score and suggested fixes.
        """
        try:            # Format with black to get "ideal" formatting
            formatted = black.format_str(code, mode=black.FileMode())
            
            # Calculate similarity between original and formatted
            style_score = CodeQualityMetrics.calculate_bleu(code, formatted)
            
            return {
                "metrics": {
                    "style_score": style_score
                },
                "formatted_code": formatted,
                "requires_formatting": code != formatted
            }
        except Exception as e:
            return {
                "error": f"Failed to check style conformance: {str(e)}",
                "style_score": 0.0,
                "requires_formatting": True
            }
    @staticmethod
    def check_error_types(code: str) -> Dict[str, Any]:
        """
        Analyze code for potential errors and categorize them.
        As recommended by the paper for error analysis.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dictionary containing error information and metrics
        """
        errors: List[Dict[str, str]] = []
        
        # Check for syntax errors
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append({"type": "syntax", "details": str(e)})
            return {
                "errors": errors,
                "metrics": {"error_count": len(errors)}
            }
        
        try:
            # Tokenize to check for other issues
            tokens = list(tokenize.generate_tokens(StringIO(code).readline))
            
            # Check for common issues
            has_docstring = False
            has_type_hints = False
            indentation_consistent = True
            prev_indent = 0
            
            for token in tokens:
                if token.type == tokenize.STRING and token.start[1] == 0:
                    has_docstring = True
                elif token.type == tokenize.NAME and token.string in ('int', 'str', 'float', 'bool', 'List', 'Dict', 'Any', 'Optional'):
                    has_type_hints = True
                elif token.type == tokenize.INDENT:
                    if token.string != '    ' and token.string != '\t':
                        indentation_consistent = False
                  # Record identified issues
            if not has_docstring:
                errors.append({"type": "style", "details": "Missing docstring"})
            if not has_type_hints:
                errors.append({"type": "style", "details": "Missing type hints"})
            if not indentation_consistent:
                errors.append({"type": "style", "details": "Inconsistent indentation"})
                
        except Exception as e:
            errors.append({"type": "unknown", "details": str(e)})
        
        return {
            "errors": errors,
            "metrics": {"error_count": len(errors)}
        }
    @staticmethod
    def evaluate_code_quality(code: str, reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Comprehensive code quality evaluation combining all metrics.
        
        Args:
            code: The code to evaluate
            reference: Optional reference code to compare against
            
        Returns:
            Dictionary containing quality metrics
        """
        results: Dict[str, Any] = {
            "complexity": CodeQualityMetrics.calculate_complexity_metrics(code),
            "style": CodeQualityMetrics.check_style_conformance(code),
            "errors": CodeQualityMetrics.check_error_types(code),
            "metrics": {}  # Store numeric metrics separately
        }
        
        if reference is not None:
            results["metrics"]["bleu_score"] = CodeQualityMetrics.calculate_bleu(code, reference)
        
        # Calculate overall quality score (0-1)
        try:
            # Normalize complexity (lower is better)
            cc_score = 1.0 / (1.0 + results["complexity"]["cyclomatic_complexity"])
            
            # Style score is already 0-1
            style_score = results["style"]["style_score"]
            
            # Error penalty
            error_penalty = 1.0 / (1.0 + results["errors"]["error_count"])
            
            # Weighted average (adjust weights as needed)
            overall_score = (
                0.3 * cc_score +
                0.4 * style_score +
                0.3 * error_penalty
            )
            
            results["metrics"]["overall_score"] = overall_score
            
        except Exception as e:
            results["metrics"]["overall_score"] = 0.0
            results["error"] = str(e)
        
        return results
