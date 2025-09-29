# main.py 
import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# Import from agents package - FIXED
from agents.orchestrator import GameTestOrchestrator

app = FastAPI(title="Multi-Agent Game Tester", version="1.0.0", debug=True)

# Create directories
for directory in ["artifacts", "reports", "frontend"]:
    Path(directory).mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Global state
current_test_run = None
test_status = {"status": "idle", "progress": 0, "message": ""}

class TestRequest(BaseModel):
    game_url: str = "https://play.ezygamers.com/"
    num_candidates: int = 20
    num_execute: int = 10
    test_types: List[str] = ["basic_gameplay", "edge_cases", "performance", "ui_validation"]

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        # Open with UTF-8 encoding
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Frontend files not found. Please check frontend/index.html exists.</h1>")

@app.post("/api/start-test")
async def start_test(request: TestRequest, background_tasks: BackgroundTasks):
    global current_test_run, test_status
    
    if test_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Test already running")
    
    test_run_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    current_test_run = test_run_id
    
    background_tasks.add_task(execute_test_workflow, request, test_run_id)
    
    return {"test_run_id": test_run_id, "status": "started"}

@app.get("/api/status")
async def get_status():
    return test_status

@app.get("/api/reports")
async def list_reports():
    reports_dir = Path("reports")
    reports = []
    
    if reports_dir.exists():
        for file in reports_dir.glob("*.json"):
            stats = file.stat()
            reports.append({
                "name": file.name,
                "created": datetime.fromtimestamp(stats.st_ctime).isoformat(),
                "size": stats.st_size
            })
    
    return {"reports": sorted(reports, key=lambda x: x["created"], reverse=True)}

@app.get("/api/reports/{report_name}")
async def get_report(report_name: str):
    report_path = Path("reports") / report_name
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    return FileResponse(report_path, media_type="application/json")

@app.get("/api/artifacts/{test_run_id}")
async def list_artifacts(test_run_id: str):
    artifacts_dir = Path("artifacts") / test_run_id
    artifacts = []
    
    if artifacts_dir.exists():
        for file in artifacts_dir.rglob("*"):
            if file.is_file():
                artifacts.append({
                    "name": file.name,
                    "path": str(file.relative_to(artifacts_dir)),
                    "type": file.suffix[1:] if file.suffix else "unknown",
                    "size": file.stat().st_size
                })
    
    return {"artifacts": artifacts}

async def execute_test_workflow(request: TestRequest, test_run_id: str):
    global test_status
    
    try:
        test_status = {"status": "running", "progress": 0, "message": "Initializing orchestrator"}
        
        # Initialize orchestrator
        orchestrator = GameTestOrchestrator({
            "test_run_id": test_run_id,
            "game_url": request.game_url,
            "num_candidates": request.num_candidates,
            "num_execute": request.num_execute,
            "test_types": request.test_types
        })
        
        # Execute workflow with progress updates
        async def progress_callback(stage: str, progress: int, message: str):
            test_status["progress"] = progress
            test_status["message"] = f"{stage}: {message}"
        
        test_status["message"] = "Starting test workflow"
        report = await orchestrator.execute_full_workflow(progress_callback)
        
        # Save final report
        report_path = Path("reports") / f"{test_run_id}_final_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        test_status = {
            "status": "completed", 
            "progress": 100, 
            "message": f"Test completed successfully. Report: {report_path.name}"
        }
        
    except Exception as e:
        test_status = {
            "status": "failed", 
            "progress": 0, 
            "message": f"Test failed: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)