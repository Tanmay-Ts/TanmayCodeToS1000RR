# agents/analyzer_agent.py - Test result analysis and validation
import logging
import json
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
import sys, os

# Add project root and agents folder to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
# If this file is in project root (e.g. main.py), project_root is correct.
# If this file is inside agents/, go up one level:
if os.path.basename(project_root) == "agents":
    project_root = os.path.dirname(project_root)

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Also ensure agents package is on path
agents_path = os.path.join(project_root, "agents")
if agents_path not in sys.path:
    sys.path.insert(0, agents_path)


class AnalyzerAgent:
    """Analyze test results with repeat and cross-validation."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Analysis thresholds
        self.thresholds = {
            "max_execution_time": 30.0,
            "min_success_rate": 0.8,
            "max_error_rate": 0.2,
            "performance_budget_ms": 3000
        }

    async def analyze_results(self, test_results: List[Dict[str, Any]], test_run_id: str) -> Dict[str, Any]:
        """Perform comprehensive analysis of test results."""
        
        self.logger.info(f"Analyzing {len(test_results)} test results")
        
        # Basic statistics
        stats = self._calculate_basic_stats(test_results)
        
        # Detailed analysis
        analysis = {
            "test_run_id": test_run_id,
            "summary": stats,
            "detailed_analysis": {
                "performance_analysis": self._analyze_performance(test_results),
                "error_analysis": self._analyze_errors(test_results),
                "artifact_analysis": self._analyze_artifacts(test_results),
                "reliability_analysis": self._analyze_reliability(test_results)
            },
            "validation_results": await self._perform_cross_validation(test_results),
            "recommendations": self._generate_recommendations(test_results, stats),
            "triage_notes": self._generate_triage_notes(test_results),
            "metadata": {
                "analyzed_by": "AnalyzerAgent",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }
        }
        
        # Save analysis report
        report_path = Path("reports") / f"{test_run_id}_analysis.json"
        with open(report_path, "w") as f:
            json.dump(analysis, f, indent=2)
        
        self.logger.info(f"Analysis completed and saved to {report_path}")
        return analysis

    def _calculate_basic_stats(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate basic test statistics."""
        
        total_tests = len(test_results)
        if total_tests == 0:
            return {"total_tests": 0, "success_rate": 0, "error": "No test results to analyze"}
        
        passed_tests = sum(1 for result in test_results if result.get("status") == "passed")
        failed_tests = sum(1 for result in test_results if result.get("status") == "failed")
        error_tests = sum(1 for result in test_results if result.get("status") == "error")
        
        execution_times = [
            float(result.get("execution_time", 0)) 
            for result in test_results 
            if result.get("execution_time")
        ]
        
        return {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "errors": error_tests,
            "success_rate": passed_tests / total_tests,
            "failure_rate": failed_tests / total_tests,
            "error_rate": error_tests / total_tests,
            "execution_times": {
                "min": min(execution_times) if execution_times else 0,
                "max": max(execution_times) if execution_times else 0,
                "average": sum(execution_times) / len(execution_times) if execution_times else 0,
                "total": sum(execution_times) if execution_times else 0
            }
        }

    def _analyze_performance(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance metrics from test results."""
        
        performance_data = []
        slow_tests = []
        
        for result in test_results:
            execution_time = float(result.get("execution_time", 0))
            test_id = result.get("test_id", "unknown")
            
            performance_data.append({
                "test_id": test_id,
                "execution_time": execution_time,
                "status": result.get("status", "unknown")
            })
            
            if execution_time > self.thresholds["max_execution_time"]:
                slow_tests.append({
                    "test_id": test_id,
                    "execution_time": execution_time,
                    "threshold_exceeded": execution_time - self.thresholds["max_execution_time"]
                })
        
        # Performance metrics analysis
        performance_metrics = []
        for result in test_results:
            for step in result.get("steps_executed", []):
                if "performance_metrics" in step:
                    performance_metrics.extend(step["performance_metrics"])
        
        return {
            "performance_summary": {
                "total_tests_analyzed": len(performance_data),
                "slow_tests_count": len(slow_tests),
                "performance_threshold": self.thresholds["max_execution_time"]
            },
            "slow_tests": slow_tests,
            "performance_metrics": performance_metrics,
            "recommendations": [
                "Optimize slow test cases" if slow_tests else "Performance within acceptable limits",
                "Consider parallel execution for faster results" if len(test_results) > 5 else None
            ]
        }

    def _analyze_errors(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze errors and failures from test results."""
        
        error_summary = {}
        failure_patterns = []
        
        for result in test_results:
            test_id = result.get("test_id", "unknown")
            status = result.get("status", "unknown")
            
            # Collect errors
            errors = result.get("errors", [])
            for error in errors:
                error_type = error.get("type", "unknown")
                error_summary[error_type] = error_summary.get(error_type, 0) + 1
                
                failure_patterns.append({
                    "test_id": test_id,
                    "error_type": error_type,
                    "error_message": error.get("message", ""),
                    "timestamp": error.get("timestamp", "")
                })
            
            # Check for test failure
            if status == "failed":
                failure_reason = result.get("failure_reason", "Unknown failure")
                failure_patterns.append({
                    "test_id": test_id,
                    "error_type": "test_failure",
                    "error_message": failure_reason,
                    "timestamp": result.get("end_time", "")
                })
        
        return {
            "error_summary": error_summary,
            "failure_patterns": failure_patterns,
            "common_errors": self._identify_common_errors(failure_patterns),
            "error_rate_analysis": {
                "within_threshold": len(failure_patterns) / len(test_results) <= self.thresholds["max_error_rate"],
                "current_rate": len(failure_patterns) / len(test_results) if test_results else 0,
                "threshold": self.thresholds["max_error_rate"]
            }
        }

    def _analyze_artifacts(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze captured artifacts."""
        
        artifact_summary = {
            "screenshots": 0,
            "dom_snapshots": 0,
            "console_logs": 0,
            "network_logs": 0,
            "videos": 0
        }
        
        artifact_quality = []
        
        for result in test_results:
            test_id = result.get("test_id", "unknown")
            
            # Count artifacts
            artifacts = result.get("artifacts", [])
            screenshots = result.get("screenshots", [])
            console_logs = result.get("console_logs", [])
            
            artifact_summary["screenshots"] += len(screenshots)
            artifact_summary["console_logs"] += len(console_logs)
            
            # Assess artifact quality
            quality_score = self._assess_artifact_quality(result)
            artifact_quality.append({
                "test_id": test_id,
                "quality_score": quality_score,
                "artifact_count": len(artifacts) + len(screenshots)
            })
        
        return {
            "artifact_summary": artifact_summary,
            "artifact_quality": artifact_quality,
            "coverage_analysis": {
                "tests_with_screenshots": sum(1 for r in test_results if r.get("screenshots")),
                "tests_with_console_logs": sum(1 for r in test_results if r.get("console_logs")),
                "overall_coverage": sum(1 for r in test_results if r.get("artifacts") or r.get("screenshots")) / len(test_results) if test_results else 0
            }
        }

    def _analyze_reliability(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze test reliability and repeatability."""
        
        # Group tests by type/category for reliability analysis
        test_categories = {}
        for result in test_results:
            category = result.get("category", "unknown")
            if category not in test_categories:
                test_categories[category] = []
            test_categories[category].append(result)
        
        reliability_scores = {}
        for category, results in test_categories.items():
            passed = sum(1 for r in results if r.get("status") == "passed")
            total = len(results)
            reliability_scores[category] = passed / total if total > 0 else 0
        
        return {
            "category_reliability": reliability_scores,
            "overall_reliability": sum(reliability_scores.values()) / len(reliability_scores) if reliability_scores else 0,
            "flaky_tests": self._identify_flaky_tests(test_results),
            "repeatability_assessment": {
                "consistent_results": sum(1 for score in reliability_scores.values() if score >= 0.9),
                "inconsistent_results": sum(1 for score in reliability_scores.values() if score < 0.7)
            }
        }

    async def _perform_cross_validation(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform cross-validation checks on test results."""
        
        validation_checks = []
        
        # Check 1: Execution time consistency
        execution_times = [float(r.get("execution_time", 0)) for r in test_results]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
        outliers = [
            {"test_id": r.get("test_id"), "time": float(r.get("execution_time", 0))}
            for r in test_results 
            if abs(float(r.get("execution_time", 0)) - avg_time) > 2 * avg_time
        ]
        
        validation_checks.append({
            "check_name": "execution_time_consistency",
            "status": "pass" if len(outliers) <= len(test_results) * 0.1 else "fail",
            "details": f"Found {len(outliers)} execution time outliers",
            "outliers": outliers
        })
        
        # Check 2: Error pattern validation
        error_patterns = {}
        for result in test_results:
            for error in result.get("errors", []):
                pattern = error.get("type", "unknown")
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1
        
        validation_checks.append({
            "check_name": "error_pattern_validation",
            "status": "pass" if len(error_patterns) <= 3 else "warning",
            "details": f"Found {len(error_patterns)} distinct error patterns",
            "error_patterns": error_patterns
        })
        
        # Check 3: Artifact completeness
        incomplete_artifacts = [
            r.get("test_id") 
            for r in test_results 
            if not r.get("screenshots") and not r.get("artifacts")
        ]
        
        validation_checks.append({
            "check_name": "artifact_completeness",
            "status": "pass" if len(incomplete_artifacts) == 0 else "warning",
            "details": f"Found {len(incomplete_artifacts)} tests with incomplete artifacts",
            "incomplete_tests": incomplete_artifacts
        })
        
        return {
            "validation_checks": validation_checks,
            "overall_validation_status": "pass" if all(c["status"] == "pass" for c in validation_checks) else "warning",
            "cross_validation_score": sum(1 for c in validation_checks if c["status"] == "pass") / len(validation_checks)
        }

    def _generate_recommendations(self, test_results: List[Dict[str, Any]], stats: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        
        recommendations = []
        
        # Success rate recommendations
        if stats["success_rate"] < self.thresholds["min_success_rate"]:
            recommendations.append(f"Success rate ({stats['success_rate']:.1%}) is below threshold. Review failing tests.")
        
        # Performance recommendations
        avg_time = stats["execution_times"]["average"]
        if avg_time > self.thresholds["max_execution_time"]:
            recommendations.append(f"Average execution time ({avg_time:.1f}s) exceeds threshold. Optimize slow tests.")
        
        # Error rate recommendations
        if stats["error_rate"] > self.thresholds["max_error_rate"]:
            recommendations.append(f"Error rate ({stats['error_rate']:.1%}) is too high. Investigate common failure patterns.")
        
        # General recommendations
        if stats["total_tests"] < 10:
            recommendations.append("Consider expanding test coverage with more test cases.")
        
        if len(recommendations) == 0:
            recommendations.append("All metrics within acceptable thresholds. Test suite performing well.")
        
        return recommendations

    def _generate_triage_notes(self, test_results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Generate triage notes for failed tests."""
        
        triage_notes = {
            "high_priority": [],
            "medium_priority": [],
            "low_priority": []
        }
        
        for result in test_results:
            test_id = result.get("test_id", "unknown")
            status = result.get("status", "unknown")
            
            if status == "failed":
                # Classify by failure type
                errors = result.get("errors", [])
                has_page_errors = any(e.get("type") == "page_error" for e in errors)
                
                if has_page_errors:
                    triage_notes["high_priority"].append(f"{test_id}: Page errors detected - investigate immediately")
                elif result.get("execution_time", 0) > self.thresholds["max_execution_time"]:
                    triage_notes["medium_priority"].append(f"{test_id}: Performance issues - timeout or slow execution")
                else:
                    triage_notes["low_priority"].append(f"{test_id}: General test failure - review test logic")
            
            elif status == "error":
                triage_notes["high_priority"].append(f"{test_id}: Test execution error - fix test infrastructure")
        
        return triage_notes

    def _assess_artifact_quality(self, test_result: Dict[str, Any]) -> float:
        """Assess the quality of captured artifacts for a test."""
        
        score = 0.0
        max_score = 5.0
        
        # Check for screenshots
        if test_result.get("screenshots"):
            score += 1.0
        
        # Check for console logs
        if test_result.get("console_logs"):
            score += 1.0
        
        # Check for DOM snapshots (implied by artifacts)
        if test_result.get("artifacts"):
            score += 1.0
        
        # Check for step-level artifacts
        steps_with_artifacts = sum(1 for step in test_result.get("steps_executed", []) if step.get("artifacts"))
        if steps_with_artifacts > 0:
            score += 1.0
        
        # Check for performance metrics
        has_performance = any(
            "performance_metrics" in step 
            for step in test_result.get("steps_executed", [])
        )
        if has_performance:
            score += 1.0
        
        return score / max_score

    def _identify_common_errors(self, failure_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify common error patterns."""
        
        error_counts = {}
        for pattern in failure_patterns:
            error_type = pattern.get("error_type", "unknown")
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # Return errors that appear in multiple tests
        common_errors = [
            {"error_type": error_type, "count": count, "frequency": count / len(failure_patterns)}
            for error_type, count in error_counts.items()
            if count > 1
        ]
        
        return sorted(common_errors, key=lambda x: x["count"], reverse=True)

    def _identify_flaky_tests(self, test_results: List[Dict[str, Any]]) -> List[str]:
        """Identify potentially flaky tests (placeholder - would need historical data)."""
        
        # In a real system, this would compare against historical results
        # For now, identify tests with unusual patterns
        flaky_tests = []
        
        for result in test_results:
            test_id = result.get("test_id", "unknown")
            
            # Tests with intermittent errors might be flaky
            errors = result.get("errors", [])
            if len(errors) > 0 and result.get("status") == "passed":
                flaky_tests.append(test_id)
        
        return flaky_tests

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_type": "AnalyzerAgent",
            "version": "1.0.0",
            "capabilities": ["result_analysis", "cross_validation", "performance_analysis"],
            "analysis_thresholds": self.thresholds
        }