# agents/planner_agent.py - LangChain-powered test case generation
import os
import json
import logging
from typing import Dict, List, Any
from datetime import datetime
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
    from langchain_google_genai import GoogleGenerativeAI
    from langchain.schema import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

class PlannerAgent:
    """Generate comprehensive test cases using LangChain for SumLink puzzle game."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize LangChain LLM
        self.llm = None
        if LANGCHAIN_AVAILABLE:
            api_key = os.getenv("GOOGLE_API_KEY") or self.config.get("api_key")
            if api_key:
                try:
                    self.llm = GoogleGenerativeAI(
                        google_api_key=api_key,
                        model="gemini-1.5-pro",
                        temperature=0.8
                    )
                    self.logger.info("LangChain Gemini LLM initialized successfully")
                except Exception as e:
                    self.logger.error(f"Failed to initialize LangChain LLM: {e}")
        
        if not self.llm:
            self.logger.warning("Using fallback mode - no LangChain LLM available")

    async def generate_test_cases(self, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate comprehensive test cases for SumLink puzzle game."""
        
        game_url = requirements.get("game_url", "https://play.ezygamers.com/")
        num_candidates = requirements.get("num_candidates", 20)
        test_types = requirements.get("test_types", ["basic_gameplay", "edge_cases"])
        
        if self.llm:
            return await self._generate_with_langchain(game_url, num_candidates, test_types)
        else:
            return self._generate_fallback_cases(game_url, num_candidates, test_types)

    async def _generate_with_langchain(self, game_url: str, num_candidates: int, test_types: List[str]) -> List[Dict[str, Any]]:
        """Generate test cases using LangChain LLM."""
        
        prompt = f"""
You are an expert game testing AI analyzing the SumLink number puzzle game at {game_url}.

GAME ANALYSIS:
- SumLink is a number matching puzzle game
- Players drag to connect numbers that sum to target values
- Game has scoring, hints, tutorials, and multiple languages
- Key UI elements: game board, score display, hint button, settings
- Game mechanics: drag selection, sum calculation, target matching

Generate {num_candidates} comprehensive test cases covering these categories:
{', '.join(test_types)}

For each test case, provide:
1. Unique test ID and clear description
2. Specific game interactions (clicks, drags, inputs)
3. Expected outcomes and validation points
4. Priority level (high/medium/low)
5. Test category and complexity score
6. Playwright-compatible selectors and actions

Return ONLY valid JSON in this format:
{{
  "test_cases": [
    {{
      "id": "TC_001",
      "title": "Basic Number Connection Test",
      "description": "Verify player can connect numbers to reach target sum",
      "category": "basic_gameplay",
      "priority": "high",
      "complexity_score": 7.5,
      "steps": [
        {{
          "action": "navigate",
          "target": "{game_url}",
          "description": "Load game page"
        }},
        {{
          "action": "wait",
          "target": ".game-board",
          "timeout": 5000,
          "description": "Wait for game board to load"
        }},
        {{
          "action": "click",
          "target": "button:has-text('New Game')",
          "description": "Start new game"
        }},
        {{
          "action": "drag",
          "source": ".number-cell:nth-child(1)",
          "target": ".number-cell:nth-child(2)",
          "description": "Drag to connect numbers"
        }}
      ],
      "expected_results": {{
        "game_state_changes": ["sum_calculated", "score_updated"],
        "ui_updates": ["selection_highlighted", "feedback_shown"],
        "performance_metrics": {{"response_time": "<200ms"}}
      }},
      "validation_points": [
        "Sum calculation is correct",
        "Score updates appropriately",
        "Visual feedback is provided"
      ],
      "artifacts_to_capture": ["screenshot", "console_logs", "network_activity"]
    }}
  ]
}}

Generate diverse, realistic test cases covering:
- Basic gameplay mechanics
- Edge cases (boundary conditions, invalid inputs)
- UI validation (button states, visual feedback)
- Performance testing (load times, responsiveness)
- Cross-browser compatibility scenarios
- Accessibility features
- Error handling and recovery
"""

        try:
            # Use LangChain to generate test cases
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # Parse response
            response_text = response.content if hasattr(response, 'content') else str(response)
            test_cases_data = self._parse_llm_response(response_text)
            
            # Validate and enrich test cases
            validated_cases = []
            for i, case in enumerate(test_cases_data.get("test_cases", [])):
                try:
                    validated_case = self._validate_test_case(case, i)
                    validated_cases.append(validated_case)
                except Exception as e:
                    self.logger.warning(f"Skipping invalid test case {i}: {e}")
            
            self.logger.info(f"Generated {len(validated_cases)} test cases using LangChain")
            return validated_cases
            
        except Exception as e:
            self.logger.error(f"LangChain generation failed: {e}")
            return self._generate_fallback_cases(game_url, num_candidates, test_types)

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse and clean LLM response."""
        try:
            # Clean response
            cleaned = response_text.strip()
            
            # Remove markdown code blocks
            if "```json" in cleaned:
                start = cleaned.find("```json") + 7
                end = cleaned.rfind("```")
                cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                lines = cleaned.split('\n')
                cleaned = '\n'.join(line for line in lines if not line.strip().startswith('```'))
            
            # Find JSON content
            start_idx = cleaned.find('{')
            if start_idx > 0:
                cleaned = cleaned[start_idx:]
            
            return json.loads(cleaned)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            # Save for debugging
            os.makedirs("artifacts", exist_ok=True)
            with open(f"artifacts/llm_response_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as f:
                f.write(f"Original Response:\n{response_text}\n\nCleaned Response:\n{cleaned}\n\nError: {e}")
            raise

    def _validate_test_case(self, case: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Validate and enrich test case structure."""
        validated = {
            "id": case.get("id", f"TC_{index+1:03d}"),
            "title": case.get("title", f"Test Case {index+1}"),
            "description": case.get("description", ""),
            "category": case.get("category", "basic_gameplay"),
            "priority": case.get("priority", "medium"),
            "complexity_score": float(case.get("complexity_score", 5.0)),
            "steps": case.get("steps", []),
            "expected_results": case.get("expected_results", {}),
            "validation_points": case.get("validation_points", []),
            "artifacts_to_capture": case.get("artifacts_to_capture", ["screenshot"]),
            "metadata": {
                "generated_by": "langchain_planner",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }
        }
        
        # Validate steps format
        if not isinstance(validated["steps"], list):
            validated["steps"] = []
        
        # Ensure required step fields
        for step in validated["steps"]:
            if "action" not in step:
                step["action"] = "unknown"
            if "description" not in step:
                step["description"] = "No description provided"
        
        return validated

    def _generate_fallback_cases(self, game_url: str, num_candidates: int, test_types: List[str]) -> List[Dict[str, Any]]:
        """Generate fallback test cases when LangChain is not available."""
        
        self.logger.info(f"Generating {num_candidates} fallback test cases")
        
        fallback_cases = []
        
        # Basic gameplay tests
        basic_tests = [
            {
                "title": "Basic Game Load Test",
                "description": "Verify game loads properly and displays main elements",
                "category": "basic_gameplay",
                "steps": [
                    {"action": "navigate", "target": game_url, "description": "Navigate to game"},
                    {"action": "wait", "target": ".game-container", "timeout": 5000, "description": "Wait for game to load"},
                    {"action": "screenshot", "description": "Capture initial state"}
                ]
            },
            {
                "title": "New Game Initialization",
                "description": "Test starting a new game",
                "category": "basic_gameplay", 
                "steps": [
                    {"action": "click", "target": "button:has-text('New Game')", "description": "Click New Game"},
                    {"action": "wait", "target": ".game-board", "timeout": 3000, "description": "Wait for board"},
                    {"action": "screenshot", "description": "Capture game board"}
                ]
            },
            {
                "title": "Number Selection Test",
                "description": "Test basic number selection mechanics",
                "category": "basic_gameplay",
                "steps": [
                    {"action": "click", "target": ".number-cell:first-child", "description": "Select first number"},
                    {"action": "screenshot", "description": "Capture selection state"}
                ]
            }
        ]
        
        # Edge case tests
        edge_tests = [
            {
                "title": "Boundary Value Test",
                "description": "Test game behavior with boundary values",
                "category": "edge_cases",
                "steps": [
                    {"action": "custom", "description": "Test maximum score scenarios"},
                    {"action": "screenshot", "description": "Capture boundary state"}
                ]
            },
            {
                "title": "Invalid Selection Test", 
                "description": "Test invalid number combinations",
                "category": "edge_cases",
                "steps": [
                    {"action": "drag", "source": ".invalid-cell", "target": ".another-cell", "description": "Attempt invalid drag"},
                    {"action": "screenshot", "description": "Capture error state"}
                ]
            }
        ]
        
        # Performance tests
        performance_tests = [
            {
                "title": "Load Performance Test",
                "description": "Measure game load performance",
                "category": "performance",
                "steps": [
                    {"action": "performance_start", "description": "Start performance monitoring"},
                    {"action": "navigate", "target": game_url, "description": "Load game"},
                    {"action": "performance_end", "description": "End performance monitoring"}
                ]
            }
        ]
        
        # UI validation tests
        ui_tests = [
            {
                "title": "Settings Menu Test",
                "description": "Test settings menu functionality", 
                "category": "ui_validation",
                "steps": [
                    {"action": "click", "target": "button:has-text('Settings')", "description": "Open settings"},
                    {"action": "screenshot", "description": "Capture settings menu"}
                ]
            }
        ]
        
        # Combine test templates
        test_templates = basic_tests + edge_tests + performance_tests + ui_tests
        
        # Generate required number of test cases
        for i in range(num_candidates):
            template = test_templates[i % len(test_templates)]
            
            test_case = {
                "id": f"TC_{i+1:03d}",
                "title": f"{template['title']} #{i+1}",
                "description": f"{template['description']} (Fallback generated)",
                "category": template["category"],
                "priority": "medium" if i < num_candidates // 2 else "low",
                "complexity_score": 5.0 + (i % 5),
                "steps": template["steps"],
                "expected_results": {
                    "status": "success",
                    "validations": ["Basic functionality works"]
                },
                "validation_points": [
                    "No console errors",
                    "UI responds appropriately", 
                    "Performance within acceptable range"
                ],
                "artifacts_to_capture": ["screenshot", "console_logs"],
                "metadata": {
                    "generated_by": "fallback_planner",
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0"
                }
            }
            
            fallback_cases.append(test_case)
        
        self.logger.info(f"Generated {len(fallback_cases)} fallback test cases")
        return fallback_cases

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_type": "PlannerAgent",
            "version": "1.0.0",
            "capabilities": ["test_case_generation", "langchain_integration"],
            "langchain_available": LANGCHAIN_AVAILABLE,
            "llm_initialized": self.llm is not None
        }