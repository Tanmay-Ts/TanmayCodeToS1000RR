# agents/orchestrator.py - Multi-agent coordination
import logging
import asyncio
from typing import Dict, List, Any, Callable
from datetime import datetime
from pathlib import Path
import sys, os
import sys, os

# Compute project root (one level up if inside agents/ or orchestrator/)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
if os.path.basename(current_dir) in ("agents", "orchestrator"):
    project_root = os.path.dirname(current_dir)

# Add project root and agents folder to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
agents_path = os.path.join(project_root, "agents")
if os.path.isdir(agents_path) and agents_path not in sys.path:
    sys.path.insert(0, agents_path)



project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from agents.planner_agent import PlannerAgent
from agents.ranker_agent import RankerAgent
from agents.executor_agent import ExecutorAgent
from agents.analyzer_agent import AnalyzerAgent

class GameTestOrchestrator:
    """Orchestrate multi-agent game testing workflow."""
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize agents
        self.planner = PlannerAgent(config.get("planner", {}))
        self.ranker = RankerAgent(config.get("ranker", {}))
        self.executor = ExecutorAgent(config.get("executor", {}))
        self.analyzer = AnalyzerAgent(config.get("analyzer", {}))
        
        self.logger.info("GameTestOrchestrator initialized with all agents")

    async def execute_full_workflow(self, progress_callback: Callable = None) -> Dict[str, Any]:
        """Execute the complete multi-agent testing workflow."""
        
        test_run_id = self.config.get("test_run_id", f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        self.logger.info(f"Starting full workflow for test run: {test_run_id}")
        
        workflow_report = {
            "test_run_id": test_run_id,
            "workflow_start": datetime.now().isoformat(),
            "config": self.config,
            "phases": {},
            "final_verdict": None,
            "artifacts_location": f"artifacts/{test_run_id}",
            "reports_generated": []
        }
        
        try:
            # Phase 1: Test Case Generation
            if progress_callback:
                await progress_callback("Planning", 10, "Generating test cases with LangChain")
            
            planning_phase = await self._execute_planning_phase()
            workflow_report["phases"]["planning"] = planning_phase
            
            # Phase 2: Test Case Ranking
            if progress_callback:
                await progress_callback("Ranking", 30, "Ranking and selecting top test cases")
            
            ranking_phase = await self._execute_ranking_phase(planning_phase["test_cases"])
            workflow_report["phases"]["ranking"] = ranking_phase
            
            # Phase 3: Test Execution
            if progress_callback:
                await progress_callback("Execution", 50, "Executing selected test cases")
            
            execution_phase = await self._execute_execution_phase(
                ranking_phase["selected_test_cases"], test_run_id
            )
            workflow_report["phases"]["execution"] = execution_phase
            
            # Phase 4: Result Analysis
            if progress_callback:
                await progress_callback("Analysis", 80, "Analyzing results and performing validation")
            
            analysis_phase = await self._execute_analysis_phase(
                execution_phase["test_results"], test_run_id
            )
            workflow_report["phases"]["analysis"] = analysis_phase
            
            # Phase 5: Final Report Generation
            if progress_callback:
                await progress_callback("Reporting", 95, "Generating final report")
            
            final_report = self._generate_final_report(workflow_report)
            workflow_report["final_report"] = final_report
            workflow_report["final_verdict"] = final_report["overall_verdict"]
            
            workflow_report["workflow_end"] = datetime.now().isoformat()
            workflow_report["status"] = "completed"
            
            if progress_callback:
                await progress_callback("Complete", 100, "Workflow completed successfully")
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            workflow_report["status"] = "failed"
            workflow_report["error"] = str(e)
            workflow_report["workflow_end"] = datetime.now().isoformat()
            
            if progress_callback:
                await progress_callback("Failed", 0, f"Workflow failed: {str(e)}")
        
        return workflow_report

    async def _execute_planning_phase(self) -> Dict[str, Any]:
        """Execute test case planning phase."""
        
        self.logger.info("Executing planning phase")
        phase_start = datetime.now()
        
        requirements = {
            "game_url": self.config.get("game_url", "https://play.ezygamers.com/"),
            "num_candidates": self.config.get("num_candidates", 20),
            "test_types": self.config.get("test_types", ["basic_gameplay", "edge_cases"])
        }
        
        try:
            test_cases = await self.planner.generate_test_cases(requirements)
            
            phase_result = {
                "status": "success",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "test_cases": test_cases,
                "test_cases_generated": len(test_cases),
                "requirements": requirements,
                "planner_info": self.planner.get_agent_info()
            }
            
            self.logger.info(f"Planning phase completed: {len(test_cases)} test cases generated")
            
        except Exception as e:
            self.logger.error(f"Planning phase failed: {e}")
            phase_result = {
                "status": "failed",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "error": str(e),
                "test_cases": [],
                "test_cases_generated": 0
            }
        
        return phase_result

    async def _execute_ranking_phase(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute test case ranking phase."""
        
        self.logger.info("Executing ranking phase")
        phase_start = datetime.now()
        
        num_select = self.config.get("num_execute", 10)
        
        try:
            ranking_result = await self.ranker.rank_test_cases(test_cases, num_select)
            
            phase_result = {
                "status": "success",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "selected_test_cases": ranking_result["selected_test_cases"],
                "rejected_test_cases": ranking_result["rejected_test_cases"],
                "ranking_details": ranking_result,
                "ranker_info": self.ranker.get_agent_info()
            }
            
            self.logger.info(f"Ranking phase completed: {len(ranking_result['selected_test_cases'])} cases selected")
            
        except Exception as e:
            self.logger.error(f"Ranking phase failed: {e}")
            phase_result = {
                "status": "failed",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "error": str(e),
                "selected_test_cases": test_cases[:num_select],  # Fallback selection
                "rejected_test_cases": []
            }
        
        return phase_result

    async def _execute_execution_phase(self, test_cases: List[Dict[str, Any]], test_run_id: str) -> Dict[str, Any]:
        """Execute test execution phase."""
        
        self.logger.info("Executing test execution phase")
        phase_start = datetime.now()
        
        try:
            test_results = await self.executor.execute_test_cases(test_cases, test_run_id)
            
            # Calculate execution statistics
            passed_count = sum(1 for result in test_results if result.get("status") == "passed")
            failed_count = sum(1 for result in test_results if result.get("status") == "failed")
            error_count = sum(1 for result in test_results if result.get("status") == "error")
            
            phase_result = {
                "status": "success",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "test_results": test_results,
                "execution_statistics": {
                    "total_executed": len(test_results),
                    "passed": passed_count,
                    "failed": failed_count,
                    "errors": error_count,
                    "success_rate": passed_count / len(test_results) if test_results else 0
                },
                "executor_info": self.executor.get_agent_info()
            }
            
            self.logger.info(f"Execution phase completed: {len(test_results)} tests executed")
            
        except Exception as e:
            self.logger.error(f"Execution phase failed: {e}")
            phase_result = {
                "status": "failed",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "error": str(e),
                "test_results": [],
                "execution_statistics": {"total_executed": 0, "passed": 0, "failed": 0, "errors": 0}
            }
        
        return phase_result

    async def _execute_analysis_phase(self, test_results: List[Dict[str, Any]], test_run_id: str) -> Dict[str, Any]:
        """Execute result analysis phase."""
        
        self.logger.info("Executing analysis phase")
        phase_start = datetime.now()
        
        try:
            analysis_result = await self.analyzer.analyze_results(test_results, test_run_id)
            
            phase_result = {
                "status": "success",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "analysis_result": analysis_result,
                "analyzer_info": self.analyzer.get_agent_info()
            }
            
            self.logger.info("Analysis phase completed")
            
        except Exception as e:
            self.logger.error(f"Analysis phase failed: {e}")
            phase_result = {
                "status": "failed",
                "phase_duration": (datetime.now() - phase_start).total_seconds(),
                "error": str(e),
                "analysis_result": {}
            }
        
        return phase_result

    def _generate_final_report(self, workflow_report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive final report."""
        
        # Extract key metrics from all phases
        planning_phase = workflow_report["phases"].get("planning", {})
        ranking_phase = workflow_report["phases"].get("ranking", {})
        execution_phase = workflow_report["phases"].get("execution", {})
        analysis_phase = workflow_report["phases"].get("analysis", {})
        
        # Calculate overall success
        total_tests = execution_phase.get("execution_statistics", {}).get("total_executed", 0)
        passed_tests = execution_phase.get("execution_statistics", {}).get("passed", 0)
        overall_success_rate = passed_tests / total_tests if total_tests > 0 else 0
        
        # Determine overall verdict
        if overall_success_rate >= 0.9:
            verdict = "EXCELLENT"
            verdict_reason = "Very high success rate with minimal issues"
        elif overall_success_rate >= 0.8:
            verdict = "GOOD"
            verdict_reason = "Good success rate with some minor issues"
        elif overall_success_rate >= 0.6:
            verdict = "FAIR"
            verdict_reason = "Moderate success rate with several issues"
        else:
            verdict = "POOR"
            verdict_reason = "Low success rate indicating significant problems"
        
        # Collect recommendations from all phases
        all_recommendations = []
        if "analysis_result" in analysis_phase:
            all_recommendations.extend(analysis_phase["analysis_result"].get("recommendations", []))
        
        final_report = {
            "overall_verdict": verdict,
            "verdict_reason": verdict_reason,
            "executive_summary": {
                "test_cases_generated": planning_phase.get("test_cases_generated", 0),
                "test_cases_executed": total_tests,
                "overall_success_rate": overall_success_rate,
                "total_workflow_time": sum([
                    planning_phase.get("phase_duration", 0),
                    ranking_phase.get("phase_duration", 0),
                    execution_phase.get("phase_duration", 0),
                    analysis_phase.get("phase_duration", 0)
                ])
            },
            "key_findings": self._extract_key_findings(workflow_report),
            "recommendations": all_recommendations,
            "reproducibility_stats": {
                "workflow_reproducible": all(
                    phase.get("status") == "success" 
                    for phase in workflow_report["phases"].values()
                ),
                "test_artifacts_captured": self._count_artifacts(execution_phase),
                "cross_validation_performed": "validation_results" in analysis_phase.get("analysis_result", {})
            },
            "next_steps": self._generate_next_steps(verdict, all_recommendations),
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "workflow_version": "1.0.0",
                "agents_used": ["PlannerAgent", "RankerAgent", "ExecutorAgent", "AnalyzerAgent"]
            }
        }
        
        return final_report

    def _extract_key_findings(self, workflow_report: Dict[str, Any]) -> List[str]:
        """Extract key findings from workflow phases."""
        
        findings = []
        
        # Planning findings
        planning = workflow_report["phases"].get("planning", {})
        if planning.get("status") == "success":
            findings.append(f"Successfully generated {planning.get('test_cases_generated', 0)} test cases using LangChain")
        
        # Execution findings
        execution = workflow_report["phases"].get("execution", {})
        if execution.get("execution_statistics"):
            stats = execution["execution_statistics"]
            findings.append(f"Test execution: {stats.get('passed', 0)}/{stats.get('total_executed', 0)} tests passed")
        
        # Analysis findings
        analysis = workflow_report["phases"].get("analysis", {})
        if "analysis_result" in analysis:
            analysis_data = analysis["analysis_result"]
            if "summary" in analysis_data:
                summary = analysis_data["summary"]
                findings.append(f"Success rate: {summary.get('success_rate', 0):.1%}")
                findings.append(f"Average execution time: {summary.get('execution_times', {}).get('average', 0):.1f}s")
        
        return findings

    def _count_artifacts(self, execution_phase: Dict[str, Any]) -> int:
        """Count total artifacts captured during execution."""
        
        total_artifacts = 0
        for result in execution_phase.get("test_results", []):
            total_artifacts += len(result.get("artifacts", []))
            total_artifacts += len(result.get("screenshots", []))
        
        return total_artifacts

    def _generate_next_steps(self, verdict: str, recommendations: List[str]) -> List[str]:
        """Generate next steps based on verdict and recommendations."""
        
        next_steps = []
        
        if verdict == "POOR":
            next_steps.extend([
                "Investigate failing tests immediately",
                "Review test environment setup",
                "Consider reducing test scope until issues are resolved"
            ])
        elif verdict == "FAIR":
            next_steps.extend([
                "Address identified issues in failing tests",
                "Optimize slow-running tests",
                "Expand test coverage gradually"
            ])
        elif verdict in ["GOOD", "EXCELLENT"]:
            next_steps.extend([
                "Integrate into CI/CD pipeline",
                "Expand test coverage",
                "Monitor test performance over time"
            ])
        
        # Add specific recommendations as next steps
        for recommendation in recommendations[:3]:  # Top 3 recommendations
            if recommendation not in next_steps:
                next_steps.append(recommendation)
        
        return next_steps

    def get_orchestrator_info(self) -> Dict[str, Any]:
        """Get orchestrator information."""
        return {
            "orchestrator_type": "GameTestOrchestrator",
            "version": "1.0.0",
            "agents": [
                self.planner.get_agent_info(),
                self.ranker.get_agent_info(),
                self.executor.get_agent_info(),
                self.analyzer.get_agent_info()
            ],
            "workflow_phases": ["planning", "ranking", "execution", "analysis", "reporting"]
        }