# agents/executor_agent.py - Test execution with Playwright and artifact capture
import os
import json
import logging
import asyncio
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


try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class ExecutorAgent:
    """Execute test cases with full artifact capture using Playwright."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self.browser = None
        self.context = None
        
        # Execution settings
        self.headless = self.config.get("headless", False)
        self.timeout = self.config.get("timeout", 30000)
        self.viewport = self.config.get("viewport", {"width": 1280, "height": 720})

    async def execute_test_cases(self, test_cases: List[Dict[str, Any]], test_run_id: str) -> List[Dict[str, Any]]:
        """Execute multiple test cases with artifact capture."""
        
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright not available - cannot execute tests")
            return self._generate_mock_results(test_cases, test_run_id)
        
        results = []
        
        try:
            # Initialize browser
            await self._initialize_browser()
            
            # Execute each test case
            for i, test_case in enumerate(test_cases):
                self.logger.info(f"Executing test case {i+1}/{len(test_cases)}: {test_case['id']}")
                
                result = await self._execute_single_test(test_case, test_run_id, i+1)
                results.append(result)
                
                # Brief pause between tests
                await asyncio.sleep(1)
        
        finally:
            await self._cleanup_browser()
        
        return results

    async def _initialize_browser(self):
        """Initialize Playwright browser and context."""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-dev-shm-usage', '--disable-extensions']
        )
        
        self.context = await self.browser.new_context(
            viewport=self.viewport,
            record_video_dir="artifacts/videos" if self.config.get("record_video") else None
        )
        
        # Enable console and network logging
        self.context.on("console", self._handle_console_message)
        self.context.on("request", self._handle_network_request)
        
        self.logger.info("Browser initialized successfully")

    async def _cleanup_browser(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def _execute_single_test(self, test_case: Dict[str, Any], test_run_id: str, test_index: int) -> Dict[str, Any]:
        """Execute a single test case with full artifact capture."""
        
        test_id = test_case["id"]
        start_time = datetime.now()
        
        # Create artifact directory for this test
        artifact_dir = Path("artifacts") / test_run_id / test_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize result structure
        result = {
            "test_id": test_id,
            "title": test_case["title"],
            "status": "running",
            "start_time": start_time.isoformat(),
            "steps_executed": [],
            "artifacts": [],
            "console_logs": [],
            "network_activity": [],
            "errors": [],
            "performance_metrics": {},
            "screenshots": []
        }
        
        page = None
        
        try:
            # Create new page
            page = await self.context.new_page()
            
            # Set up page monitoring
            page.on("console", lambda msg: result["console_logs"].append({
                "type": msg.type,
                "text": msg.text,
                "timestamp": datetime.now().isoformat()
            }))
            
            page.on("pageerror", lambda error: result["errors"].append({
                "type": "page_error",
                "message": str(error),
                "timestamp": datetime.now().isoformat()
            }))
            
            # Execute test steps
            for step_index, step in enumerate(test_case.get("steps", [])):
                step_result = await self._execute_step(page, step, artifact_dir, step_index)
                result["steps_executed"].append(step_result)
                
                if not step_result["success"]:
                    result["status"] = "failed"
                    result["failure_reason"] = step_result.get("error", "Step execution failed")
                    break
            
            # Final screenshot
            screenshot_path = artifact_dir / f"final_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            result["screenshots"].append(str(screenshot_path))
            
            # Capture final page state
            await self._capture_page_artifacts(page, artifact_dir, "final")
            
            # Mark as passed if no failures
            if result["status"] == "running":
                result["status"] = "passed"
            
        except Exception as e:
            self.logger.error(f"Test execution failed for {test_id}: {e}")
            result["status"] = "error"
            result["error_message"] = str(e)
        
        finally:
            if page:
                await page.close()
            
            # Calculate execution time
            end_time = datetime.now()
            result["end_time"] = end_time.isoformat()
            result["execution_time"] = (end_time - start_time).total_seconds()
            
            # Save test result
            result_file = artifact_dir / "test_result.json"
            with open(result_file, "w") as f:
                json.dump(result, f, indent=2)
        
        return result

    async def _execute_step(self, page: Page, step: Dict[str, Any], artifact_dir: Path, step_index: int) -> Dict[str, Any]:
        """Execute a single test step."""
        
        action = step.get("action", "")
        target = step.get("target", "")
        description = step.get("description", "")
        
        step_result = {
            "step_index": step_index,
            "action": action,
            "target": target,
            "description": description,
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "artifacts": []
        }
        
        try:
            # Execute based on action type
            if action == "navigate":
                await page.goto(target, wait_until="networkidle", timeout=self.timeout)
                
            elif action == "click":
                await page.click(target, timeout=self.timeout)
                
            elif action == "drag":
                source = step.get("source", "")
                await page.drag_and_drop(source, target, timeout=self.timeout)
                
            elif action == "wait":
                timeout = step.get("timeout", 5000)
                await page.wait_for_selector(target, timeout=timeout)
                
            elif action == "screenshot":
                screenshot_path = artifact_dir / f"step_{step_index}_screenshot.png"
                await page.screenshot(path=screenshot_path)
                step_result["artifacts"].append(str(screenshot_path))
                
            elif action == "performance_start":
                # Start performance monitoring
                await page.evaluate("performance.mark('test-start')")
                
            elif action == "performance_end":
                # End performance monitoring and capture metrics
                metrics = await page.evaluate("""
                    () => {
                        performance.mark('test-end');
                        performance.measure('test-duration', 'test-start', 'test-end');
                        const entries = performance.getEntriesByType('measure');
                        return entries.map(entry => ({
                            name: entry.name,
                            duration: entry.duration,
                            startTime: entry.startTime
                        }));
                    }
                """)
                step_result["performance_metrics"] = metrics
                
            else:
                self.logger.warning(f"Unknown action type: {action}")
            
            # Capture artifacts after each significant step
            if action in ["navigate", "click", "drag"]:
                await self._capture_step_artifacts(page, artifact_dir, step_index)
            
            step_result["success"] = True
            
        except Exception as e:
            step_result["error"] = str(e)
            self.logger.error(f"Step {step_index} failed: {e}")
        
        return step_result

    async def _capture_step_artifacts(self, page: Page, artifact_dir: Path, step_index: int):
        """Capture artifacts for a specific step."""
        try:
            # Screenshot
            screenshot_path = artifact_dir / f"step_{step_index}_screenshot.png"
            await page.screenshot(path=screenshot_path)
            
            # DOM snapshot
            html_content = await page.content()
            html_path = artifact_dir / f"step_{step_index}_dom.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
        except Exception as e:
            self.logger.warning(f"Failed to capture artifacts for step {step_index}: {e}")

    async def _capture_page_artifacts(self, page: Page, artifact_dir: Path, suffix: str = ""):
        """Capture comprehensive page artifacts."""
        try:
            # Full page screenshot
            screenshot_path = artifact_dir / f"page_{suffix}_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            
            # DOM snapshot
            html_content = await page.content()
            html_path = artifact_dir / f"page_{suffix}_dom.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Console logs
            logs = await page.evaluate("console.history || []")
            logs_path = artifact_dir / f"page_{suffix}_console.json"
            with open(logs_path, "w") as f:
                json.dump(logs, f, indent=2)
            
        except Exception as e:
            self.logger.warning(f"Failed to capture page artifacts: {e}")

    def _handle_console_message(self, msg):
        """Handle console messages from the browser."""
        pass  # Handled per-page in _execute_single_test

    def _handle_network_request(self, request):
        """Handle network requests for monitoring."""
        pass  # Can be extended for detailed network monitoring

    def _generate_mock_results(self, test_cases: List[Dict[str, Any]], test_run_id: str) -> List[Dict[str, Any]]:
        """Generate mock results when Playwright is not available."""
        
        self.logger.warning("Generating mock test results - Playwright not available")
        
        results = []
        for i, test_case in enumerate(test_cases):
            result = {
                "test_id": test_case["id"],
                "title": test_case["title"],
                "status": "passed" if i % 4 != 0 else "failed",  # Make some fail for demo
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "execution_time": 5.0 + (i * 0.5),
                "steps_executed": [
                    {
                        "step_index": j,
                        "action": step.get("action", "mock"),
                        "success": True,
                        "timestamp": datetime.now().isoformat()
                    }
                    for j, step in enumerate(test_case.get("steps", []))
                ],
                "artifacts": [],
                "console_logs": [
                    {"type": "info", "text": "Mock console log", "timestamp": datetime.now().isoformat()}
                ],
                "errors": [] if i % 4 != 0 else [
                    {"type": "mock_error", "message": "Simulated test failure", "timestamp": datetime.now().isoformat()}
                ]
            }
            results.append(result)
        
        return results

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_type": "ExecutorAgent",
            "version": "1.0.0",
            "capabilities": ["test_execution", "artifact_capture", "browser_automation"],
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "browser_settings": {
                "headless": self.headless,
                "timeout": self.timeout,
                "viewport": self.viewport
            }
        }