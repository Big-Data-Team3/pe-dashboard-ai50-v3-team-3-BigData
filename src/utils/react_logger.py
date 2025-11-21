"""
ReAct Pattern Logger — Enhanced
--------------------------------

A structured logger for tracking ReAct-style execution:

Thought → Action → Observation → Final Answer

Features:
- JSONL logging
- Run identifiers
- Company identifiers
- Metadata on every step
- Clean console output
- Automatic truncation for long observations
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReActLogger:
    """Structured logger for ReAct (Reasoning + Acting) execution traces."""

    def __init__(
        self,
        log_file: str = "logs/react_traces.jsonl",
        run_id: Optional[str] = None
    ):
        self.log_file = Path(log_file)
        self.run_id = run_id or str(uuid4())
        self.step_counter = 0

        # Create directory if needed
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"ReAct Logger initialized | run_id={self.run_id}")

    # ---------------------------------------------------------
    # PUBLIC LOGGING METHODS
    # ---------------------------------------------------------

    def log_thought(self, thought: str, company_id: Optional[str] = None, metadata: Dict = None):
        """Log the internal reasoning step."""
        self._log_step("thought", thought, company_id, metadata)

    def log_action(
        self,
        tool_name: str,
        tool_input: Any,
        company_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log the chosen tool and parameters."""
        content = {
            "tool": tool_name,
            "input": tool_input
        }
        self._log_step("action", content, company_id, metadata)

    def log_observation(self, observation: Any, company_id: Optional[str] = None, metadata: Dict = None):
        """Log the observation returned by a tool."""
        # Clean and truncate long values
        if isinstance(observation, (dict, list)):
            obs = json.dumps(observation, ensure_ascii=False)
        else:
            obs = str(observation)

        if len(obs) > 800:
            obs = obs[:800] + "... (truncated)"

        self._log_step("observation", obs, company_id, metadata)

    def log_final_answer(self, answer: str, company_id: Optional[str] = None, metadata: Dict = None):
        """Log the final answer."""
        self._log_step("final_answer", answer, company_id, metadata)

    # ---------------------------------------------------------
    # INTERNAL METHOD
    # ---------------------------------------------------------

    def _log_step(
        self,
        step_type: str,
        content: Any,
        company_id: Optional[str],
        metadata: Optional[Dict]
    ):
        """Internal helper to write JSONL step."""
        self.step_counter += 1

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": self.run_id,
            "company_id": company_id,
            "step": self.step_counter,
            "type": step_type,
            "content": content,
            "metadata": metadata or {}
        }

        # Write JSONL
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"[ReActLogger] Failed writing log: {e}")

        # Pretty console output
        icons = {
            "thought": "💭",
            "action": "🔧",
            "observation": "👁️",
            "final_answer": "✅"
        }
        icon = icons.get(step_type, "📝")

        print(f"\n{icon} [{step_type.upper()}] Step {self.step_counter}")
        if isinstance(content, dict):
            print(json.dumps(content, indent=2))
        else:
            print(content)

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def get_trace_summary(self) -> Dict[str, Any]:
        """Return a summary of the trace."""
        return {
            "run_id": self.run_id,
            "steps": self.step_counter,
            "log_file": str(self.log_file)
        }
