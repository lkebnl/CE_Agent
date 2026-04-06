# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : NL intent parsing via Ollama/Qwen3, action dispatch, and result summarisation
"""
femb_nl_agent.py — Natural-language driven FEMB QC agent.

Uses Ollama + Qwen3:8b via the HTTP API (requests.post, NOT the ollama library)
to parse user intent, then dispatches to the appropriate action.
"""

import json
import logging
import os
import sys

import requests

from core.femb_config_preview import confirm_config
from core.femb_constants import (
    OLLAMA_HOST, OLLAMA_MODEL,
    GAIN_MAP, PEAKING_MAP, BASELINE_MAP,
)
from core.femb_ssh_lib import (
    femb_power_on, femb_power_off,
    run_full_rms, run_single_config, run_config_matrix,
)
from core.femb_analysis_lib import analyze_from_manifest
from agent.femb_prompt_templates import SYSTEM_PROMPT_TEMPLATE, FEW_SHOT_EXAMPLES

log = logging.getLogger(__name__)

# Registry path relative to this file
_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "femb_function_registry.json")


class FEMBNLAgent:
    """
    Natural-language driven FEMB QC agent.

    Responsibilities:
      1. Parse user natural-language input → structured parameters (JSON).
      2. Select the appropriate instruction sequence.
      3. Call femb_ssh_lib / femb_analysis_lib to execute.
      4. Translate results into human-readable output.
    """

    def __init__(self, ollama_host=None, model=None):
        """
        Initialise the Ollama client and load the function registry.

        Parameters
        ----------
        ollama_host : str or None
            Ollama server base URL. Defaults to OLLAMA_HOST constant.
        model : str or None
            Model name. Defaults to OLLAMA_MODEL constant.
        """
        self.ollama_host = ollama_host or OLLAMA_HOST
        self.model = model or OLLAMA_MODEL
        self.api_url = "{host}/api/chat".format(host=self.ollama_host)

        # Load function registry
        try:
            with open(_REGISTRY_PATH, "r") as fh:
                self.registry = json.load(fh)
        except Exception as exc:
            log.warning("Could not load function registry: %s", exc)
            self.registry = {}

        # Intent → action mapping
        self._intent_map = {
            "run_rms":         self._action_run_full_rms,
            "run_single":      self._action_run_single_config,
            "run_and_analyze": self._action_run_and_analyze,
            "analyze_rms":     self._action_analyze_rms,
            "power_on":        self._action_power_on,
            "power_off":       self._action_power_off,
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse_intent(self, user_input):
        """
        Call Qwen3:8b to parse user intent into structured parameters.

        Uses a few-shot prompt with the system prompt from femb_prompt_templates.

        Parameters
        ----------
        user_input : str
            The raw user message (Chinese or English).

        Returns
        -------
        dict
            Parsed intent with keys: intent, params, confidence,
            clarification_needed, clarification_question.
        """
        messages = self._build_messages(user_input)
        raw = self._call_ollama(messages)

        # Extract JSON — strip any markdown code fences
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(
                l for l in lines
                if not l.startswith("```")
            )

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("JSON parse error: %s\nRaw response: %s", exc, raw[:300])
            parsed = {
                "intent": "unknown",
                "params": {},
                "confidence": 0.0,
                "clarification_needed": True,
                "clarification_question": "Could not parse intent. Please rephrase.",
            }
        return parsed

    def execute(self, user_input, interactive=True, preview_dir="./config_previews"):
        """
        Full execution pipeline.

        Steps:
          1. parse_intent(user_input) → params
          2. Generate config preview TXT and prompt tester to confirm/edit/cancel
          3. If tester edits, reload params from the saved TXT
          4. Call the corresponding function with final params
          5. Return structured result + human-readable summary

        Parameters
        ----------
        user_input : str
            Raw user message.
        interactive : bool
            Whether to show config preview and prompt for confirmation.
        preview_dir : str
            Directory to save config_preview_*.txt files.

        Returns
        -------
        dict
            {'intent': str, 'params': dict, 'result': dict, 'summary': str}
        """
        intent_dict = self.parse_intent(user_input)

        if interactive:
            # Show config preview and let tester confirm / edit / cancel
            intent_dict = confirm_config(intent_dict, save_dir=preview_dir)
            if intent_dict is None:
                return {
                    "intent":  "unknown",
                    "params":  {},
                    "result":  {},
                    "summary": "已取消。",
                }

        # Dispatch
        params      = intent_dict.get("params", {})
        intent_name = intent_dict.get("intent", "unknown")
        action = self._intent_map.get(intent_name)

        if action is None:
            summary = "Unknown intent: '{}'. Supported: {}.".format(
                intent_name, ", ".join(self._intent_map.keys())
            )
            return {
                "intent":  intent_name,
                "params":  params,
                "result":  {},
                "summary": summary,
            }

        try:
            result = action(params)
        except Exception as exc:
            log.error("Action failed: %s", exc, exc_info=True)
            result = {"error": str(exc)}

        summary = result.get("summary", str(result))
        return {
            "intent":  intent_name,
            "params":  params,
            "result":  result,
            "summary": summary,
        }

    # ── Private: Prompt Construction ────────────────────────────────────────────

    def _build_system_prompt(self):
        """Return the system prompt string."""
        return SYSTEM_PROMPT_TEMPLATE

    def _build_few_shot_examples(self):
        """Return the few-shot example message list."""
        return list(FEW_SHOT_EXAMPLES)

    def _build_messages(self, user_input):
        """
        Assemble the full messages list for the Ollama API.

        Structure: [system, few-shot user/assistant pairs, current user message]
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        messages.extend(self._build_few_shot_examples())
        messages.append({"role": "user", "content": user_input})
        return messages

    # ── Private: Ollama HTTP Call ────────────────────────────────────────────────

    def _call_ollama(self, messages):
        """
        Send a chat completion request to the Ollama HTTP API.

        Uses requests.post to http://localhost:11434/api/chat with stream=false.
        Does NOT use the ollama Python library.

        Parameters
        ----------
        messages : list
            List of {"role": ..., "content": ...} dicts.

        Returns
        -------
        str
            The assistant message content string.
        """
        payload = {
            "model":  self.model,
            "messages": messages,
            "stream": False,
            "think":  False,   # disable qwen3 chain-of-thought thinking mode
            "options": {
                "temperature": 0.1,  # low temperature for deterministic JSON output
                "num_predict": 400,  # JSON response never exceeds ~300 tokens
            },
        }
        log.info("[Ollama] POST %s model=%s", self.api_url, self.model)
        try:
            resp = requests.post(self.api_url, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            log.debug("[Ollama] Response: %s", content[:200])
            return content
        except requests.exceptions.ConnectionError:
            msg = (
                "Cannot reach Ollama at {}. "
                "Is 'ollama serve' running?".format(self.ollama_host)
            )
            log.error(msg)
            raise RuntimeError(msg)
        except requests.exceptions.Timeout:
            msg = "Ollama request timed out."
            log.error(msg)
            raise RuntimeError(msg)
        except Exception as exc:
            log.error("Ollama API error: %s", exc)
            raise

    # ── Private: Intent → Action Mapping ────────────────────────────────────────

    def _map_intent_to_action(self, intent):
        """
        Map an intent string to the corresponding action callable.

        Parameters
        ----------
        intent : dict
            Parsed intent dict (with 'intent' key).

        Returns
        -------
        callable or None
        """
        name = intent.get("intent", "")
        return self._intent_map.get(name)

    # ── Private: Action Implementations ─────────────────────────────────────────

    def _action_run_full_rms(self, params):
        """Execute full item-5 RMS test."""
        slots    = params.get("fembs") or [0]
        operator = params.get("operator") or "unknown"
        env      = params.get("env") or "RT"

        print("\n[Agent] Running full RMS on slots {} env={}...".format(slots, env))
        result = run_full_rms(slots=slots, operator=operator, env=env)

        if result["success"]:
            result["summary"] = (
                "Full RMS complete. Data saved to: {}".format(result["data_dir"])
            )
        else:
            result["summary"] = "Full RMS FAILED. Check logs."
        return result

    def _action_run_single_config(self, params):
        """Execute single-configuration RMS acquisition."""
        slots   = params.get("fembs") or [0]
        env     = params.get("env") or "RT"
        n_samp  = int(params.get("num_samples") or 5)

        # Convert human-readable labels to bit codes
        snc_label = params.get("snc")
        gain_label = params.get("gain")
        peak_label = params.get("peaking")

        snc = BASELINE_MAP.get(snc_label, 1) if snc_label else 1
        sg0, sg1 = GAIN_MAP.get(gain_label, (0, 0)) if gain_label else (0, 0)
        st0, st1 = PEAKING_MAP.get(peak_label, (1, 1)) if peak_label else (1, 1)

        print("\n[Agent] Running single config: slots={} snc={} sg=({},{}) st=({},{})".format(
            slots, snc, sg0, sg1, st0, st1))

        result = run_single_config(
            slots=slots, snc=snc, sg0=sg0, sg1=sg1, st0=st0, st1=st1,
            num_samples=n_samp,
        )

        if result["success"]:
            result["summary"] = (
                "Single config acquisition complete. File: {}".format(result["file"])
            )
        else:
            result["summary"] = "Single config acquisition FAILED. Check logs."
        return result

    def _action_run_and_analyze(self, params):
        """Acquire a single config then immediately analyze the result."""
        # Step 1: acquire
        acq = self._action_run_single_config(params)
        if not acq.get("success"):
            acq["summary"] = "Acquisition FAILED — skipping analysis. Check logs."
            return acq

        # Step 2: analyze using the manifest written during acquisition
        print("\n[Agent] Acquisition done, starting analysis...")
        analysis = self._action_analyze_rms(params)

        # Merge summaries
        analysis["summary"] = (
            "[采集] {}\n[分析] {}".format(
                acq.get("summary", ""),
                analysis.get("summary", ""),
            )
        )
        return analysis

    def _action_analyze_rms(self, params):
        """Analyze existing data using the manifest."""
        femb_id   = int((params.get("fembs") or [0])[0])
        snc_label = params.get("snc")
        gain_label = params.get("gain")
        peak_label = params.get("peaking")

        chips           = params.get("chips")
        chip_channels   = params.get("chip_channels")
        global_channels = params.get("global_channels")

        # Try to find the most recent manifest
        manifest_path = _find_latest_manifest()
        if manifest_path is None:
            return {
                "summary": (
                    "No acquisition_manifest.json found in ./data/. "
                    "Please run an acquisition first."
                )
            }

        print("\n[Agent] Analyzing FEMB {} from manifest: {}".format(
            femb_id, manifest_path))

        result = analyze_from_manifest(
            manifest_path=manifest_path,
            femb_id=femb_id,
            snc_label=snc_label,
            gain_label=gain_label,
            peaking_label=peak_label,
            chips=chips,
            chip_channels=chip_channels,
            global_channels=global_channels,
            plot=True,
        )
        return result

    def _action_power_on(self, params):
        """Power on FEMB slots."""
        slots = params.get("fembs") or [0]
        env   = params.get("env") or "RT"

        print("\n[Agent] Powering on slots {} env={}...".format(slots, env))
        result = femb_power_on(slots=slots, env=env)

        if result["success"]:
            result["summary"] = "Power ON successful for slots {}.".format(slots)
        else:
            result["summary"] = "Power ON FAILED for slots {}. Check logs.".format(slots)
        return result

    def _action_power_off(self, params):
        """Power off all FEMBs."""
        print("\n[Agent] Powering off all FEMBs...")
        success = femb_power_off()
        return {
            "success": success,
            "summary": "All FEMBs powered off." if success else "Power OFF failed.",
        }


# ── Module helpers ─────────────────────────────────────────────────────────────

def _find_latest_manifest(data_root="./data"):
    """
    Search data_root for the most recently modified acquisition_manifest.json.

    Returns
    -------
    str or None
        Absolute path to the manifest file, or None if not found.
    """
    manifests = []
    if not os.path.isdir(data_root):
        return None
    for root, dirs, files in os.walk(data_root):
        for fname in files:
            if fname == "acquisition_manifest.json":
                full = os.path.join(root, fname)
                manifests.append((os.path.getmtime(full), full))
    if not manifests:
        return None
    manifests.sort(reverse=True)
    return manifests[0][1]
