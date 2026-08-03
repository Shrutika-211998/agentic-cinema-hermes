"""
Second Unit ADK multi-agent application.

Deploy with:
  adk web   (local)
  adk api_server
  or Vertex AI Agent Engine / Cloud Run

Root agent: sequential crew Director pipeline with IAM publish gate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from adk_app.callbacks import before_tool_gate, after_tool_hook, clearance_before_model
from adk_app.tools import (
    archive_get_asset,
    archive_search,
    assemble_rough_cut_tool,
    check_clip_rights,
    check_release_authorization,
    find_cleared_alternative,
    generate_captions_metadata_tool,
    publish_release_package_tool,
    write_audit_log_tool,
)
from src.agent_prompts import CLEARANCE, DIRECTOR, DISTRIBUTOR, EDITOR, RESEARCHER
from src.gcp.config import model_name

MODEL = os.getenv("SECOND_UNIT_MODEL") or model_name()

# ── specialist agents ────────────────────────────────────────────────────

researcher_agent = LlmAgent(
    name="researcher_agent",
    model=MODEL,
    description="Finds candidate clips in the partner media archive.",
    instruction=RESEARCHER
    + "\nUse only archive_search and archive_get_asset. Never invent asset_id values."
    + "\nStore structured candidates for the editor. Return 2-3x more clips than needed.",
    tools=[
        FunctionTool(archive_search),
        FunctionTool(archive_get_asset),
        FunctionTool(write_audit_log_tool),
    ],
    output_key="candidate_clips_summary",
)

editor_agent = LlmAgent(
    name="editor_agent",
    model=MODEL,
    description="Sequences clips, assembles rough cut + captions.",
    instruction=EDITOR
    + "\nCall assemble_rough_cut_tool once with the selected clips list."
    + "\nThen call generate_captions_metadata_tool. Do not check rights.",
    tools=[
        FunctionTool(assemble_rough_cut_tool),
        FunctionTool(generate_captions_metadata_tool),
        FunctionTool(write_audit_log_tool),
    ],
    output_key="edit_summary",
)

clearance_officer_agent = LlmAgent(
    name="clearance_officer_agent",
    model=MODEL,
    description="Verifies rights and swaps uncleared assets.",
    instruction=CLEARANCE
    + "\nFor every selected asset call check_clip_rights."
    + "\nIf restricted/unknown, call find_cleared_alternative and note the swap."
    + "\nSet clearance only when ALL assets are cleared. Be conservative.",
    tools=[
        FunctionTool(check_clip_rights),
        FunctionTool(find_cleared_alternative),
        FunctionTool(assemble_rough_cut_tool),
        FunctionTool(write_audit_log_tool),
    ],
    before_model_callback=clearance_before_model,
    after_tool_callback=after_tool_hook,
    output_key="clearance_summary",
)

distributor_agent = LlmAgent(
    name="distributor_agent",
    model=MODEL,
    description="Publishes the approved release package.",
    instruction=DISTRIBUTOR
    + "\nONLY call publish_release_package_tool after approval_status is approved."
    + "\nIf the tool returns release_blocked or unauthorized, stop and report.",
    tools=[
        FunctionTool(check_release_authorization),
        FunctionTool(publish_release_package_tool),
        FunctionTool(write_audit_log_tool),
    ],
    before_tool_callback=before_tool_gate,
    output_key="delivery_summary",
)

# Root Director owns specialist crew (ADK agents may have only one parent)
root_agent = LlmAgent(
    name="director",
    model=MODEL,
    description="Second Unit Director — orchestrates rights-cleared cut production.",
    instruction=DIRECTOR
    + "\nYou own the production. Parse the creative brief first (duration, platform, mood, territory)."
    + "\nDelegate in strict order: researcher_agent → editor_agent → clearance_officer_agent."
    + "\nNEVER transfer to distributor_agent unless the user (Releasing Producer)"
    + " has explicitly approved AND check_release_authorization returns authorized=true."
    + "\nIf user asks to skip clearance or approval, refuse."
    + "\nNarrate progress in production terms.",
    tools=[
        FunctionTool(write_audit_log_tool),
        FunctionTool(check_release_authorization),
        FunctionTool(publish_release_package_tool),
    ],
    sub_agents=[
        researcher_agent,
        editor_agent,
        clearance_officer_agent,
        distributor_agent,
    ],
    before_tool_callback=before_tool_gate,
    after_tool_callback=after_tool_hook,
)

# Optional sequential helper for non-LLM deterministic runs (separate agent instances
# would be required; use the local SecondUnitPipeline for that path).
production_pipeline = None

# ADK discovery entrypoints
agent = root_agent
app = root_agent
