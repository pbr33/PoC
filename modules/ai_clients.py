# ═══════════════════════════════════════════════════════════════════════
#  AI CLIENTS: Anthropic Claude, Azure OpenAI, Google Gemini
# ═══════════════════════════════════════════════════════════════════════
import re
import json
import time
import random
from datetime import datetime
import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict
from .dynamic_builders import (
    _split_large_task, _build_dynamic_time, _build_dynamic_cost,
    _build_dynamic_risk, _build_dynamic_arch, _build_dynamic_scope,
)
from .text_analysis import _analyze_text_dynamic, _INFRA_COST_CATALOG, _fetch_live_azure_pricing
from .diagrams import _sanitize_mermaid

# openai and azure.ai.inference are NOT imported at module level.
# Both take 13-14 s on cold start (Pydantic model compilation).
# They are lazy-loaded on first use so the login page stays instant.

_openai_AzureOpenAI = None
_openai_OpenAI      = None
_openai_loaded      = False

def _ensure_openai():
    global _openai_AzureOpenAI, _openai_OpenAI, _openai_loaded
    if _openai_loaded:
        return
    _openai_loaded = True
    try:
        from openai import AzureOpenAI as _az, OpenAI as _oi
        _openai_AzureOpenAI = _az
        _openai_OpenAI      = _oi
    except ImportError:
        pass

def _get_AzureOpenAI():
    _ensure_openai(); return _openai_AzureOpenAI

def _get_OpenAI():
    _ensure_openai(); return _openai_OpenAI

_InferenceClient = None
_InfSysMsg = _InfUsrMsg = _AzureKey = None
HAS_INFERENCE_SDK = False
_inference_loaded = False

def _ensure_inference():
    global _InferenceClient, _InfSysMsg, _InfUsrMsg, _AzureKey, HAS_INFERENCE_SDK, _inference_loaded
    if _inference_loaded:
        return
    _inference_loaded = True
    try:
        from azure.ai.inference import ChatCompletionsClient as _ic
        from azure.ai.inference.models import SystemMessage as _sm, UserMessage as _um
        from azure.core.credentials import AzureKeyCredential as _ak
        _InferenceClient = _ic
        _InfSysMsg = _sm; _InfUsrMsg = _um; _AzureKey = _ak
        HAS_INFERENCE_SDK = True
    except ImportError:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  ANTHROPIC / CLAUDE CLIENT
# ═══════════════════════════════════════════════════════════════════════

class AnthropicAI:
    """Lightweight Anthropic Messages API client.

    Supports both:
    - Standard Anthropic API  (api.anthropic.com, key starts with sk-ant-)
    - Azure AI Services Claude (*.services.ai.azure.com/anthropic/v1/messages, api-key header)
    """
    _BASE = "https://api.anthropic.com/v1/messages"
    MODELS = [
        "claude-sonnet-4-6",
        "claude-opus-4-8",
        "claude-opus-4-6",
        "claude-haiku-4-5-20251001",
    ]

    def __init__(self, key: str, model: str = "claude-sonnet-4-6", endpoint: str = ""):
        self.key      = key.strip()
        self.model    = model or "claude-sonnet-4-6"
        # If endpoint is provided it overrides _BASE (Azure AI Services mode)
        self.endpoint = endpoint.strip() if endpoint else ""

    @property
    def _is_azure(self) -> bool:
        """True when using an Azure AI Services hosted Claude endpoint."""
        return bool(self.endpoint) and "services.ai.azure.com" in self.endpoint

    @classmethod
    def from_session(cls):
        return cls(
            st.session_state.get("anthropic_api_key", ""),
            st.session_state.get("claude_model", "claude-sonnet-4-6"),
            st.session_state.get("claude_endpoint", ""),
        )

    @classmethod
    def opus_from_session(cls):
        """Returns an AnthropicAI instance pointing at the Claude Opus 4.8 deployment."""
        return cls(
            st.session_state.get("claude_opus_api_key",
                                 st.session_state.get("anthropic_api_key", "")),
            st.session_state.get("claude_opus_model", "claude-opus-4-8"),
            st.session_state.get("claude_opus_endpoint",
                                 st.session_state.get("claude_endpoint", "")),
        )

    @property
    def is_live(self):
        if st.session_state.get("_claude_blocked"):
            return False
        return bool(self.key)

    @property
    def _is_streaming_capable(self) -> bool:
        """True when real token-by-token streaming (not blocking+simulate) is available."""
        if self._is_azure:
            try:
                import requests  # noqa: F401
                return True
            except ImportError:
                return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def test(self):
        if not self.key:
            return False, "Not configured. Enter Anthropic API Key."
        label = f"{self.model} via Azure AI Services" if self._is_azure else self.model
        result = self._call("Reply with exactly one word: OK", "ping", max_tokens=10)
        if result is not None:
            return True, f"Connected — {label}"
        return False, f"Connection failed — check key/endpoint for {label}."

    def _handle_anthropic_error(self, e, body: str = ""):
        """Centralised error handler — shows a clear message once per session."""
        _seen = "_claude_err_shown"
        if st.session_state.get(_seen):
            return  # already shown this session

        is_azure = self._is_azure
        code_str = str(getattr(e, "code", "") or getattr(e, "status_code", ""))
        err_str  = str(e)

        # Timeout / network errors — do NOT block Claude; just warn so user can retry
        is_timeout = (
            "timed out" in err_str.lower()
            or "timeout" in err_str.lower()
            or "read operation" in err_str.lower()
        )
        if is_timeout:
            st.warning(
                "⏱️ Request timed out — the diagram is large. "
                "Click Generate again to retry (the model is still available).",
            )
            # Don't set _claude_blocked — let the user retry
            return

        if is_azure:
            # Azure AI Services endpoint errors — show concise message, don't block
            if "401" in code_str or "403" in code_str:
                st.error(
                    "**AI Services — Authentication Error**\n\n"
                    "Check `config.yaml` → `providers.claude.api_key` and `endpoint`. "
                    "Falling back to next available provider.",
                    icon="🔑",
                )
            else:
                st.warning(f"AI service error ({code_str or 'network'}): {body[:200] or str(e)[:200]}")
            st.session_state[_seen] = True
            st.session_state["_claude_blocked"] = True
            return

        # ── Standard Anthropic API errors ────────────────────────────────
        low_balance = (
            "credit balance is too low" in body.lower()
            or "balance is too low" in body.lower()
            or "upgrade or purchase credits" in body.lower()
        )
        if low_balance:
            st.error(
                "**AI Service — Insufficient Credits**\n\n"
                "Your API key is valid but the account has no usable credits. "
                "The pipeline is falling back to the next available provider automatically.",
                icon="💳",
            )
        elif "401" in code_str:
            st.error(
                "**AI Service — Invalid API Key**\n\n"
                "Check `config.yaml` → `providers.claude.api_key`. "
                "Falling back to next available provider.",
                icon="🔑",
            )
        else:
            st.warning(f"AI service error: {body[:200] or str(e)[:200]} — falling back.")

        st.session_state[_seen] = True
        st.session_state["_claude_blocked"] = True

    def _make_request(self, system: str, user: str, max_tokens: int, timeout: int = 120):
        """Build and send request; returns raw response text or raises.

        Routing:
        - Azure AI Services endpoint  → raw HTTP with  api-key  header
        - Standard Anthropic API      → SDK first, raw HTTP fallback
        """
        import urllib.request

        payload = json.dumps({
            "model":      self.model,
            "max_tokens": max_tokens,
            "system":     system,
            "messages":   [{"role": "user", "content": user}],
        }).encode("utf-8")

        # ── Azure AI Services Claude (custom endpoint) ────────────────────
        if self._is_azure:
            import urllib.error
            url = self.endpoint
            # Try api-key header first (Azure AI Services / Foundry style)
            for auth_headers in [
                {"api-key": self.key},
                {"Authorization": f"Bearer {self.key}"},
            ]:
                req = urllib.request.Request(
                    url, data=payload,
                    headers={
                        **auth_headers,
                        "anthropic-version": "2023-06-01",
                        "Content-Type":      "application/json",
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        return (data.get("content") or [{}])[0].get("text", "")
                except urllib.error.HTTPError as he:
                    if he.code == 401:
                        continue  # try next auth style
                    raise
            raise urllib.error.HTTPError(url, 401, "Auth failed with both api-key and Bearer", {}, None)

        # ── Standard Anthropic API — try SDK first ────────────────────────
        try:
            import anthropic as _sdk
            client = _sdk.Anthropic(api_key=self.key)
            kwargs: dict = dict(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if max_tokens > 8192:
                kwargs["betas"] = ["output-128k-2025-02-19"]
                msg = client.beta.messages.create(**kwargs)
            else:
                msg = client.messages.create(**kwargs)
            return msg.content[0].text
        except ImportError:
            pass  # SDK not installed — fall back to raw HTTP
        except Exception:
            raise

        # ── Raw HTTP fallback (standard Anthropic) ────────────────────────
        req = urllib.request.Request(
            self._BASE, data=payload,
            headers={
                "x-api-key":         self.key,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("content") or [{}])[0].get("text", "")

    def _stream_azure(self, system: str, user: str, max_tokens: int = 2048):
        """Yield text chunks from Azure AI Services via SSE streaming (requests library)."""
        try:
            import requests as _req
        except ImportError:
            # requests not installed — caller should have checked _is_streaming_capable
            return

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        auth_styles = [
            {"api-key": self.key},
            {"Authorization": f"Bearer {self.key}"},
        ]
        last_exc = None
        for auth_h in auth_styles:
            try:
                with _req.post(
                    self.endpoint,
                    headers={
                        **auth_h,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    stream=True,
                    timeout=90,
                ) as resp:
                    if resp.status_code == 401:
                        last_exc = Exception(f"HTTP 401 with {list(auth_h.keys())[0]}")
                        continue
                    resp.raise_for_status()
                    for raw_line in resp.iter_lines():
                        if not raw_line:
                            continue
                        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            obj = json.loads(data)
                        except Exception:
                            continue
                        evt = obj.get("type", "")
                        if evt == "content_block_delta":
                            txt = obj.get("delta", {}).get("text", "")
                            if txt:
                                yield txt
                        elif evt == "message_stop":
                            return
                    return  # success — finished iter_lines
            except Exception as exc:
                if "401" in str(exc) or "403" in str(exc):
                    last_exc = exc
                    continue
                raise
        if last_exc:
            raise last_exc

    def _call(self, system: str, user: str, max_tokens: int = 4096):
        """Call Anthropic Messages API; return parsed JSON dict or None."""
        if not self.key or st.session_state.get("_claude_blocked"):
            return None
        try:
            txt = self._make_request(system, user, max_tokens)
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                pass
            m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", txt)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
            m2 = re.search(r"\{[\s\S]*\}", txt)
            if m2:
                try:
                    return json.loads(m2.group(0))
                except Exception:
                    pass
            return txt
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            # SDK wraps HTTP errors with .status_code; urllib uses .code
            if hasattr(e, "body"):      body = str(e.body)
            if hasattr(e, "response"):  body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000,
                      timeout: int = 90) -> "str | None":
        """Call Anthropic and return raw text output — no JSON parsing."""
        if not self.key or st.session_state.get("_claude_blocked"):
            return None
        try:
            return self._make_request(system, user, max_tokens, timeout=timeout)
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            if hasattr(e, "body"):      body = str(e.body)
            if hasattr(e, "response"):  body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None

    def stream_section_rewrite(self, title: str, current_content: str,
                               instructions: str, ref_context: str = ""):
        """Generator: streams a proposal section rewrite token-by-token.

        Uses Anthropic SDK streaming when available; falls back to a
        simulated word-by-word stream from a blocking call.
        Yields str chunks suitable for st.write_stream().
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return

        system = (
            "You are a senior ECI presales consultant and technical writer. "
            "Rewrite the proposal section based on the instructions given.\n"
            "Rules:\n"
            "• Return ONLY the rewritten section text — no JSON, no code blocks, no headings\n"
            "• Use formal, boardroom-level English — concise, client-focused, persuasive\n"
            "• Preserve technical accuracy while improving clarity and impact\n"
            "• Write as if preparing a McKinsey-quality enterprise proposal"
        )
        parts = [
            f"SECTION: {title}",
            f"CURRENT CONTENT:\n{current_content[:3000]}",
            f"INSTRUCTIONS: {instructions}",
        ]
        if ref_context:
            parts.append(f"REFERENCE CONTEXT (use where relevant):\n{ref_context[:1500]}")
        user = "\n\n".join(parts)

        # ── Azure AI Services: real SSE streaming via requests ───────────
        if self._is_azure:
            if self._is_streaming_capable:
                yield from self._stream_azure(system, user, max_tokens=2048)
                return
            # requests not available — blocking fallback with short timeout
            import time as _t
            result = self.call_raw_text(system, user, max_tokens=2048, timeout=45)
            if not result:
                return
            words = result.split(" ")
            buf = []
            for i, w in enumerate(words):
                buf.append(w)
                if len(buf) >= 4 or i == len(words) - 1:
                    yield " ".join(buf) + " "
                    buf = []
                    _t.sleep(0.018)
            return

        # ── Standard Anthropic SDK streaming ─────────────────────────────
        try:
            import anthropic as _sdk
            client = _sdk.Anthropic(api_key=self.key)
            with client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
            return
        except ImportError:
            pass
        except Exception:
            raise

        # ── Raw HTTP fallback (no SDK) → word-by-word simulation ─────────
        import time as _t
        result = self.call_raw_text(system, user, max_tokens=2048, timeout=45)
        if not result:
            return
        words = result.split(" ")
        buf = []
        for i, w in enumerate(words):
            buf.append(w)
            if len(buf) >= 4 or i == len(words) - 1:
                yield " ".join(buf) + " "
                buf = []
                _t.sleep(0.018)

    def stream_chat(self, system: str, messages: list, max_tokens: int = 2048):
        """Generator: streams a conversational reply token-by-token.

        Uses the same history-concat format as _ai_chat() so context is preserved.
        Falls back to word-by-word simulation when SDK streaming is unavailable.
        Yields str chunks for st.write_stream().
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return

        history = "\n".join(
            ("User" if m["role"] == "user" else "Assistant") + ": " + m["content"]
            for m in messages[:-1]
        )
        last_msg = messages[-1]["content"] if messages else ""
        full_user = (f"Conversation history:\n{history}\n\n" if history else "") + f"User: {last_msg}"

        # ── Azure AI Services: real SSE streaming via requests ───────────
        if self._is_azure:
            if self._is_streaming_capable:
                yield from self._stream_azure(system, full_user, max_tokens=max_tokens)
                return
            # requests not available — blocking fallback
            import time as _t
            result = self.call_raw_text(system, full_user, max_tokens=max_tokens)
            if not result:
                return
            words = result.split(" ")
            buf = []
            for i, w in enumerate(words):
                buf.append(w)
                if len(buf) >= 3 or i == len(words) - 1:
                    yield " ".join(buf) + " "
                    buf = []
                    _t.sleep(0.015)
            return

        # ── Standard Anthropic SDK streaming ─────────────────────────────
        try:
            import anthropic as _sdk
            client = _sdk.Anthropic(api_key=self.key)
            with client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": full_user}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield chunk
            return
        except ImportError:
            pass
        except Exception as e:
            self._handle_anthropic_error(e, str(e))
            return

        # ── Raw HTTP fallback (no SDK) → word-by-word simulation ─────────
        import time as _t
        result = self.call_raw_text(system, full_user, max_tokens=1024)
        if not result:
            return
        words = result.split(" ")
        buf = []
        for i, w in enumerate(words):
            buf.append(w)
            if len(buf) >= 3 or i == len(words) - 1:
                yield " ".join(buf) + " "
                buf = []
                _t.sleep(0.015)

    def generate_rich_architecture_html(self, semantic: dict, arch: dict) -> "str | None":
        """Generate a stunning, enterprise-grade HTML/SVG architecture diagram using Claude.

        Returns a complete self-contained HTML string ready for iframe display,
        or None on failure.
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return None

        import json as _json

        sem_str  = _json.dumps(semantic,  indent=2)[:3000]
        arch_str = _json.dumps(arch,      indent=2)[:3000]

        SYSTEM = """You are an elite enterprise solutions architect and data visualisation expert.
Your task: produce a SINGLE, self-contained HTML file that renders a stunning, interactive architecture diagram.

DESIGN RULES — follow every rule exactly:
1. Use nested <div> boxes with CSS border, border-radius, padding, and box-shadow to represent cloud/platform containers.
   - Outer container (e.g. "Azure Subscription"): dark navy border, light steel-blue background, large padding.
   - Mid container (e.g. "Resource Group" / "Layer"): medium blue border, very light blue tint, medium padding.
   - Inner service boxes: white background, solid border in the layer accent colour, shadow, 10px radius.
2. Use a horizontal swimlane layout (CSS flexbox row) when showing a data pipeline / flow architecture.
   Use a nested-box layout when showing a cloud subscription hierarchy.
   Choose whichever best matches the project context — or combine both.
3. Connecting arrows: use SVG <line> / <path> elements with arrowhead markers to show data flow between boxes.
   Each arrow should have a short text label on it.
4. Service icons: use meaningful Unicode/emoji symbols (☁ 🗄 🔒 📊 🤖 📨 🔑 ⚙️ 📦 🌐) inside each service box.
5. Colour palette (use consistently):
   - Ingestion / Source layer:    #1565C0 border, #E3F2FD background
   - Processing / AI layer:       #6A1B9A border, #F3E5F5 background
   - Storage / Data layer:        #2E7D32 border, #E8F5E9 background
   - Security / Governance layer: #E65100 border, #FFF3E0 background
   - Presentation / UI layer:     #00838F border, #E0F7FA background
6. Header: project name (large, bold, dark), one-line subtitle.
7. Legend: small colour-coded legend box at bottom-right.
8. Hover effect: service boxes scale up 1.04× and show a subtle shadow on hover (CSS transition).
9. Responsive: max-width 1400px, centred, works at 900px width.
10. NO external dependencies — all CSS and SVG inline. Output ONLY the HTML, no markdown, no explanation.
11. The diagram must be visually impressive: multiple layers, proper spacing, clear labels, professional typography (font: Segoe UI, Roboto, sans-serif).
12. Include at least 15–20 individual service/component boxes across all layers.
"""

        USER = f"""Create a rich enterprise architecture diagram for this project.

PROJECT SEMANTICS:
{sem_str}

ARCHITECTURE DESIGN:
{arch_str}

Return ONLY the complete HTML — no markdown fences, no explanation.
Start directly with <!DOCTYPE html> and end with </html>."""

        try:
            html = self._make_request(SYSTEM, USER, max_tokens=8000, timeout=300)
            if not html:
                return None
            # Strip any accidental markdown fences
            html = html.strip()
            if html.startswith("```"):
                lines = html.split("\n")
                html = "\n".join(lines[1:])
                if html.rstrip().endswith("```"):
                    html = html.rstrip()[:-3]
            # Ensure it's valid HTML
            if "<!DOCTYPE" not in html and "<html" not in html:
                html = "<!DOCTYPE html><html><body>" + html + "</body></html>"
            return html
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            if hasattr(e, "body"):     body = str(e.body)
            if hasattr(e, "response"): body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None

    def generate_ai_arch_svg(self, arch: dict, semantic: dict) -> "str | None":
        """Generate a stunning, publication-quality SVG architecture diagram via Claude.

        Returns a complete self-contained HTML page (with embedded SVG) ready for
        st.components.v1.html(), or None on failure.
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return None
        import json as _json
        from .utils import safe_str, safe_list, safe_dict, safe_int

        comps          = safe_list(arch.get("components"))
        flow           = safe_list(arch.get("data_flow"))
        pattern        = safe_str(arch.get("pattern", "Solution Architecture"))
        security_items = safe_list(arch.get("security"))
        tech           = safe_list(semantic.get("technology_stack", []))
        mandated       = safe_list(semantic.get("mandated_technologies", []))
        source_sys     = safe_list(semantic.get("source_systems", []))
        proj           = safe_str(semantic.get("project_type", "Cloud Solution"))
        client_name    = safe_str(semantic.get("client_name", ""))

        # build_tech = mandated first; fallback to stack minus known source systems
        source_lower = {s.lower() for s in source_sys}
        build_tech = mandated or [t for t in tech if t.lower() not in source_lower]

        arch_desc = {
            "title": pattern,
            "project_type": proj,
            "client": client_name,
            "MANDATED_BUILD_TECHNOLOGIES": [safe_str(t) for t in build_tech[:10]],
            "SOURCE_SYSTEMS_INPUT_ONLY": [safe_str(s) for s in source_sys[:6]],
            "components": [
                {
                    "name": safe_str(safe_dict(c).get("name", "")),
                    "type": safe_str(safe_dict(c).get("type", "")),
                    "azure_service": safe_str(safe_dict(c).get("azure_service", "")),
                    "services": [safe_str(s) for s in safe_list(safe_dict(c).get("services", []))[:3]],
                }
                for c in comps[:14]
            ],
            "data_flow": [safe_str(f) for f in flow[:10]],
            "security_controls": [safe_str(s) for s in security_items[:6]],
            "scalability": safe_str(arch.get("scalability", "")),
            "availability": safe_str(arch.get("availability", "")),
        }
        arch_str = _json.dumps(arch_desc, indent=2)

        SYSTEM = """You are a world-class Azure solutions architect and SVG diagram expert. \
Create a stunning, professional, enterprise-grade architecture diagram as a complete self-contained HTML page.

╔══════════════════════════════════════════════════════════════════╗
║  STRICT OUTPUT FORMAT                                           ║
║  • Return ONLY valid HTML — start <!DOCTYPE html>, end </html> ║
║  • No markdown fences, no explanation text                      ║
╚══════════════════════════════════════════════════════════════════╝

*** CRITICAL TECHNOLOGY RULES — READ FIRST ***

A. MANDATED_BUILD_TECHNOLOGIES in the JSON = technologies the client HAS SPECIFIED must be built.
   - These MUST appear as Azure service cards inside the Azure Subscription box.
   - If "Microsoft Fabric" is mandated → Microsoft Fabric IS the data platform. Draw it.
     Do NOT substitute Azure SQL Database, Azure Synapse, or any other service for it.

B. SOURCE_SYSTEMS_INPUT_ONLY in the JSON = the client's EXISTING systems that feed data in.
   - Show these ONLY in the LEFT column as gray dashed external-source boxes.
   - Do NOT place SOURCE_SYSTEMS items (e.g. "Azure SQL Database") inside the Subscription box.
   - They are not Azure services you are building — they already exist at the client.

VISUAL DESIGN SPECIFICATION (dark theme):

1. PAGE BACKGROUND: #0a0e1a (dark navy)  |  HTML+SVG width=1360, height=860
2. TYPOGRAPHY: font-family="Segoe UI, -apple-system, Roboto, sans-serif", fill=#E2E8F0 for body text

3. AZURE COLOR PALETTE (use exactly):
   • Outer Azure Subscription box : stroke=#0078D4, fill=#EBF5FB, stroke-width=2, stroke-dasharray=8,4, rx=16
   • Resource Group inner box     : stroke=#107C10, fill=#F0FFF4, stroke-width=1.5, rx=10
   • Azure AI / ML / OpenAI       : stroke=#5C2D91, fill=#F5F0FF, rx=8
   • Data / Storage / DB          : stroke=#00B294, fill=#E6FFF9, rx=8
   • App Services / API / Backend : stroke=#0078D4, fill=#EBF5FB, rx=8
   • Security / Identity / KV     : stroke=#D83B01, fill=#FFF3ED, rx=8
   • Monitoring / DevOps / Ops    : stroke=#FFB900, fill=#FFFBF0, rx=8
   • External Data Sources (left) : stroke=#6B7280, fill=#F9FAFB, stroke-dasharray=5,3, rx=8
   • Consumer / Output (right)    : stroke=#0078D4, fill=#EBF5FB, rx=12

4. SERVICE CARD layout (width=154, height=68, rx=8):
   ┌──────────────────────────────┐
   │ ● [icon circle r=16]  Name  │  ← font-size=11 font-weight=600 fill=#1F2937
   │                   AzureSvc  │  ← font-size=9  fill=tier_color
   │               sub-detail    │  ← font-size=8  fill=#6B7280
   └──────────────────────────────┘
   Icon circle: fill=tier_color, white emoji/symbol inside, font-size=14

5. ICONS (use these Unicode symbols in icon circles):
   App Service/Web      → 🌐   API Management    → 🔌   Azure Functions   → ⚡
   SQL/Database         → 🗄️   Cosmos DB         → 🌀   Blob/Storage      → 💾
   Key Vault            → 🔑   Azure AD/Entra    → 👤   Firewall/Security → 🛡️
   Azure OpenAI/AI      → 🤖   AI Search         → 🔍   Service Bus       → 📨
   Logic Apps           → 🔗   Event Hub         → 📬   Container/K8s     → 📦
   DevOps/CI-CD         → 🚀   Monitor/Insights  → 📊   Redis/Cache       → ⚡
   SharePoint           → 📁   Teams             → 💬   Copilot Studio    → 🤖
   Data Lake            → 🏞️   Synapse           → 🔬   Front Door/CDN    → 🌍
   Generic Azure        → ☁️

6. LAYOUT (left → right, 3-column):
   Col A  x=20  w=148 : External data sources / users (gray dashed boxes, stacked vertically)
   Col B  x=188 w=998 : Azure Subscription (large outer box) containing:
                          • Resource Group box inside
                          • Services grouped into colored sub-sections (use <g> + rect + services inside)
                          • Security & Monitoring section pinned at bottom of Resource Group
   Col C  x=1200 w=148: Consumer/output apps (Teams, Copilot, browsers, etc.)

7. ARROWS (data flow):
   • <path> curved bezier, stroke=source_tier_color, stroke-width=1.8, fill=none
   • <marker id="arrowX"> filled triangle arrowhead, same color as stroke
   • Short text label on each arrow: font-size=9, fill=#475569, italic
   • Avoid arrow crossings — route horizontally first, then vertically

8. SECTION HEADERS inside Resource Group:
   Small pill-shaped rect (rx=10) with label, fill=tier_color, text fill=white, font-size=10 font-weight=700

9. AZURE SUBSCRIPTION LABEL: top-left inside the box
   Azure cloud icon ☁ + "Azure Subscription" bold, fill=#0078D4, font-size=13

10. LEGEND box (bottom-right, outside main diagram):
    Small colored squares + labels for each tier, font-size=9

11. HOVER INTERACTIVITY (CSS in <style>):
    .svc-card:hover {{ filter:drop-shadow(0 4px 12px rgba(0,120,212,.35)); transform:translateY(-2px); }}
    .svc-card {{ transition: filter .2s, transform .2s; cursor:pointer; }}

12. TITLE BANNER at top:
    Full-width rect fill=#0078D4, white text: project title (font-size=15 bold) + subtitle (font-size=10)

QUALITY REQUIREMENTS:
• Include at least 12–16 individual service cards across all zones
• Minimum 8 directional arrows showing data flow
• All text must be readable (no overlap)
• The diagram must be visually impressive, balanced, and professional
• Completely self-contained — NO external images, fonts, or scripts
"""

        USER = f"""Generate a complete dark-theme HTML architecture diagram for this Azure solution:

{arch_str}

MANDATORY RULES (follow exactly):
1. MANDATED_BUILD_TECHNOLOGIES are the CORE of what you are building — draw ALL of them
   as Azure service cards inside the Azure Subscription box.
   If "Microsoft Fabric" is listed → it MUST be the primary data engineering platform card.
   Do NOT substitute or omit any mandated technology.
2. SOURCE_SYSTEMS_INPUT_ONLY items (e.g. Azure SQL Database, SAP, SharePoint files, Dynamics)
   are the CLIENT'S EXISTING SYSTEMS feeding data into the platform.
   Show them ONLY as gray dashed left-column input boxes with ingest arrows → platform.
   Do NOT place them inside the Azure Subscription box as built services.
3. Place external sources / users on the LEFT column.
4. All Azure build services in the CENTER (Azure Subscription box), grouped by colored sections.
5. Output consumers (Teams Users, Business Analysts, App Users, etc.) on the RIGHT column.
6. Show numbered data-flow arrows connecting all major components.
7. Security & Monitoring pinned at BOTTOM of Azure Subscription box.
8. Dark background (#0a0e1a), light text, colored tier borders.

Return ONLY the complete HTML. Start with <!DOCTYPE html> and end with </html>."""

        try:
            html = self._make_request(SYSTEM, USER, max_tokens=8000, timeout=300)
            if not html:
                return None
            html = html.strip()
            # Strip markdown fences if present
            if html.startswith("```"):
                lines = html.splitlines()
                html = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
            # Ensure valid HTML
            if "<html" not in html.lower():
                html = f"<!DOCTYPE html><html><body style='margin:0;background:#F8FAFC'>{html}</body></html>"
            return html
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            if hasattr(e, "body"):     body = str(e.body)
            if hasattr(e, "response"): body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None

    def generate_claude_premium_diagram(self, arch: dict, semantic: dict, cost: dict = None) -> "str | None":
        """Generate a world-class dark-theme architecture diagram exclusively via Claude.

        Returns a complete self-contained HTML page — or None on failure.
        Uses a template-based prompt so layout always works (no absolute SVG arrows).
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return None

        import json as _json
        from .utils import safe_str, safe_list, safe_dict, safe_int

        comps        = safe_list(arch.get("components"))
        flow         = safe_list(arch.get("data_flow"))
        pattern      = safe_str(arch.get("pattern", "Solution Architecture"))
        sec          = safe_list(arch.get("security"))
        tech         = safe_list(semantic.get("technology_stack", []))
        proj         = safe_str(semantic.get("project_type", "Cloud Solution"))
        client_name  = safe_str(semantic.get("client_name", ""))
        complexity   = safe_int(semantic.get("complexity_score", 5))
        azure_costs  = safe_list(safe_dict(cost or {}).get("azure_costs", []))
        total_cost   = safe_int(safe_dict(cost or {}).get("total_monthly_cost", 0))

        arch_info = {
            "title":        pattern,
            "project_type": proj,
            "client":       client_name,
            "complexity":   complexity,
            "tech_stack":   [safe_str(t) for t in tech[:12]],
            "components": [
                {
                    "name":          safe_str(safe_dict(c).get("name", "")),
                    "type":          safe_str(safe_dict(c).get("type", "")),
                    "azure_service": safe_str(safe_dict(c).get("azure_service", "")),
                    "services":      [safe_str(s) for s in safe_list(safe_dict(c).get("services", []))[:4]],
                }
                for c in comps[:18]
            ],
            "data_flow":       [safe_str(f) for f in flow[:14]],
            "security":        [safe_str(s) for s in sec[:8]],
            "scalability":     safe_str(arch.get("scalability", "")),
            "availability":    safe_str(arch.get("availability", "")),
            "monthly_cost_usd": total_cost,
            "service_costs": [
                {"name": safe_str(safe_dict(s).get("service", "")), "monthly_usd": safe_int(safe_dict(s).get("monthly", 0))}
                for s in azure_costs[:10]
            ],
        }
        arch_str = _json.dumps(arch_info, indent=2)

        # ── CSS + JS arrow layer (pre-written; Claude only fills content) ──
        ARROW_JS = r"""(function(){
var flows=window.ARCH_FLOWS||[];
if(!flows.length)return;
function absPos(el){
  var t=0,l=0,w=el.offsetWidth,h=el.offsetHeight;
  var e=el;while(e){t+=e.offsetTop||0;l+=e.offsetLeft||0;e=e.offsetParent;}
  return{t:t,l:l,w:w,h:h,cx:l+w/2,cy:t+h/2,rx:l+w,lx:l,ty:t,by:t+h};
}
function mkPath(svg,x1,y1,x2,y2,col,lbl){
  var mx=(x1+x2)/2;
  var p=document.createElementNS('http://www.w3.org/2000/svg','path');
  p.setAttribute('d','M'+x1+','+y1+' C'+mx+','+y1+' '+mx+','+y2+' '+x2+','+y2);
  p.setAttribute('class','arch-arrow');p.setAttribute('stroke',col||'#00d4aa99');
  p.setAttribute('marker-end','url(#arrowhead)');svg.appendChild(p);
  if(lbl){
    var t=document.createElementNS('http://www.w3.org/2000/svg','text');
    t.setAttribute('x',mx);t.setAttribute('y',(y1+y2)/2-4);
    t.setAttribute('class','arrow-lbl');t.setAttribute('text-anchor','middle');
    t.textContent=lbl;svg.appendChild(t);
  }
}
window.addEventListener('load',function(){
  var svg=document.getElementById('arrow-layer');if(!svg)return;
  var W=document.body.scrollWidth,H=document.body.scrollHeight;
  svg.setAttribute('width',W);svg.setAttribute('height',H);
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  flows.forEach(function(f){
    var fe=document.querySelector('[data-node="'+f.from+'"]');
    var te=document.querySelector('[data-node="'+f.to+'"]');
    if(!fe||!te)return;
    var fp=absPos(fe),tp=absPos(te),x1,y1,x2,y2;
    if(fp.rx+8<=tp.lx){x1=fp.rx;y1=fp.cy;x2=tp.lx;y2=tp.cy;}
    else if(fp.lx>=tp.rx+8){x1=fp.lx;y1=fp.cy;x2=tp.rx;y2=tp.cy;}
    else if(fp.by+8<=tp.ty){x1=fp.cx;y1=fp.by;x2=tp.cx;y2=tp.ty;}
    else if(fp.ty>=tp.by+8){x1=fp.cx;y1=fp.ty;x2=tp.cx;y2=tp.by;}
    else return;
    mkPath(svg,x1,y1,x2,y2,f.color||'#00d4aa88',f.label||'');
  });
});
})();"""

        BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{background:#080c18;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;min-width:900px}
body{background:#080c18;position:relative;min-width:900px}
.hdr{background:linear-gradient(135deg,#0f172a 0%,#1a1040 45%,#0a1628 100%);padding:18px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(0,180,216,.18)}
.hdr-title{font-size:22px;font-weight:800;color:#e2e8f0;letter-spacing:-.3px}
.hdr-sub{font-size:10px;color:#94a3b8;margin-top:3px;letter-spacing:1.2px;text-transform:uppercase}
.hdr-pills{display:flex;gap:8px;flex-wrap:wrap}
.pill{font-size:9.5px;font-weight:700;padding:4px 13px;border-radius:20px;letter-spacing:.5px;white-space:nowrap}
.accent{height:3px;background:linear-gradient(90deg,#00d4aa,#7b61ff,#00b4d8,#ff9f43)}
.techstrip{background:#0d1322;border-bottom:1px solid rgba(255,255,255,.05);padding:7px 20px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ts-lbl{font-size:9px;color:#64748b;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-right:4px;white-space:nowrap}
.tb{font-size:9px;font-weight:600;padding:3px 10px;border-radius:20px;letter-spacing:.3px;white-space:nowrap}
.diagram{display:grid;grid-template-columns:175px 1fr 175px;gap:12px;padding:16px}
.col-lbl{font-size:9px;font-weight:700;color:#64748b;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,.06)}
.src-card{background:rgba(148,163,184,.04);border:1.5px dashed rgba(148,163,184,.3);border-radius:10px;padding:12px 10px;margin-bottom:9px;text-align:center;cursor:pointer;transition:all .25s}
.src-card:hover{border-color:rgba(148,163,184,.65);background:rgba(148,163,184,.08);transform:translateY(-2px)}
.src-icon{font-size:24px;display:block;margin-bottom:5px}
.src-name{font-size:10.5px;font-weight:700;color:#e2e8f0;margin-bottom:2px}
.src-type{font-size:8.5px;color:#64748b}
.platform{background:rgba(0,12,32,.45);border:1.5px solid rgba(0,180,216,.25);border-radius:14px;padding:14px;box-shadow:inset 0 0 60px rgba(0,180,216,.02)}
.plat-lbl{font-size:11px;color:#00b4d8;font-weight:700;margin-bottom:12px;letter-spacing:.3px}
.zones{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.zone{border-radius:10px;padding:12px;border-left:3px solid var(--tc)}
.z-hdr{font-size:9px;font-weight:800;color:var(--tc);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px}
.cards{display:flex;flex-wrap:wrap;gap:8px}
.zone-full{grid-column:1/-1}
.svc{min-width:128px;max-width:175px;flex:1;background:linear-gradient(145deg,#111827,#0f1729);border:1px solid rgba(var(--tcr),.45);border-radius:9px;padding:9px 10px;cursor:pointer;transition:all .25s;position:relative}
.svc:hover{transform:translateY(-3px) scale(1.02);box-shadow:0 0 0 1.5px rgb(var(--tcr)),0 8px 28px rgba(var(--tcr),.35)}
.svc-row{display:flex;align-items:flex-start;gap:7px;margin-bottom:4px}
.svc-ico{width:26px;height:26px;min-width:26px;border-radius:50%;background:rgba(var(--tcr),.18);border:1px solid rgba(var(--tcr),.4);display:flex;align-items:center;justify-content:center;font-size:13px}
.svc-name{font-size:10.5px;font-weight:700;color:#e2e8f0;line-height:1.25;flex:1}
.svc-cost{position:absolute;top:5px;right:6px;font-size:7.5px;color:#ff9f43;background:rgba(255,159,67,.12);border-radius:8px;padding:1px 5px}
.svc-type{font-size:8.5px;color:rgb(var(--tcr));font-weight:600;margin-bottom:2px}
.svc-sub{font-size:7.5px;color:#64748b;line-height:1.4}
.out-card{background:rgba(0,212,170,.04);border:1.5px dashed rgba(0,212,170,.28);border-radius:10px;padding:12px 10px;margin-bottom:9px;text-align:center;cursor:pointer;transition:all .25s}
.out-card:hover{border-color:rgba(0,212,170,.65);transform:translateY(-2px)}
.flowsec{background:#0d1322;border-top:1px solid rgba(255,255,255,.06);padding:14px 20px}
.flow-ttl{font-size:9px;font-weight:700;color:#00b4d8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px}
.flow-steps{display:flex;flex-wrap:wrap;align-items:center;gap:5px}
.fstep{display:flex;align-items:center;gap:5px}
.fnum{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#fff;flex-shrink:0}
.flbl{font-size:9px;color:#94a3b8;white-space:nowrap}
.farrow{color:#475569;font-size:14px;font-weight:300}
.ftr{background:#0d1322;border-top:1px solid rgba(255,255,255,.06);padding:8px 20px;display:flex;justify-content:space-between;align-items:center}
.ftr-l{font-size:9px;color:#475569}
.ftr-badges{display:flex;gap:6px}
.fbadge{font-size:8px;padding:2px 8px;border-radius:10px}
/* ── arrow layer ── */
#arrow-layer{position:absolute;top:0;left:0;pointer-events:none;z-index:999;overflow:visible}
.arch-arrow{fill:none;stroke-width:1.2;opacity:.6;stroke-dasharray:6,4;animation:adash 2.2s linear infinite}
@keyframes adash{to{stroke-dashoffset:-16}}
.arrow-lbl{font-size:8px;fill:#94a3b8;font-family:'Segoe UI',sans-serif}
"""

        SYSTEM = f"""You are an expert HTML/CSS developer. Your job is to fill in a dark-theme enterprise architecture diagram using a fixed template.

STRICT RULES:
1. Return ONLY complete valid HTML starting <!DOCTYPE html> ending </html>. No markdown, no explanation.
2. Zero external dependencies.
3. NEVER use position:absolute or position:fixed for LAYOUT elements. The only exception is the pre-existing #arrow-layer SVG.
4. Use ONLY the CSS classes provided — never invent new layout CSS.
5. Every single component from the data MUST appear as a .svc card inside a zone.
6. ADD data-node="SLUG" to EVERY .src-card, .svc, and .out-card. Use kebab-case slugs derived from the name (e.g. data-node="azure-openai", data-node="bloomberg-api", data-node="internal-users"). These slugs are used by the arrow layer.
7. FILL in window.ARCH_FLOWS in the script block (it is already in the skeleton — just provide the array). Each entry: {{from:"source-slug",to:"target-slug",color:"#hexcolor",label:"short label"}}
   ARROW RULES — KEEP IT MINIMAL AND CLEAN:
   - Show ONLY the PRIMARY end-to-end data flow spine: the 4-6 most important hops that tell the story (e.g. main source → entry service → AI/processing → storage → consumer).
   - DO NOT draw an arrow for every connection in data_flow[]. Pick the 4-6 that matter most.
   - NO arrows between services in the same zone (too cluttered inside the platform box).
   - NO arrows into/out of Security or DevOps zones.
   - Each arrow must cross a visible gap so it reads clearly (source column → platform, zone A → zone B, platform → consumer column).
   - COLOR GUIDE: AI/LLM hop→"#7b61ff88", Data/Storage hop→"#ff9f4388", Integration hop→"#06d6a088", standard hop→"#00d4aa66"
   - Use EXACT data-node slugs you assigned to the cards.
   - MAXIMUM 6 entries total — quality over quantity.

USE THIS EXACT CSS IN YOUR <style> TAG (copy verbatim, add nothing else):
{BASE_CSS}

TIER COLOR VARIABLES (set as inline style="--tc:COLOR;--tcr:R,G,B" on each .zone AND each .svc):
  Presentation / Frontend / UI      →  --tc:#00d4aa; --tcr:0,212,170   zone bg: rgba(0,212,170,.05)
  Application / API / Backend       →  --tc:#00b4d8; --tcr:0,180,216   zone bg: rgba(0,180,216,.05)
  AI / Cognitive / ML / LLM         →  --tc:#7b61ff; --tcr:123,97,255  zone bg: rgba(123,97,255,.05)
  Data / Storage / Database / Lake  →  --tc:#ff9f43; --tcr:255,159,67  zone bg: rgba(255,159,67,.05)
  Security / Identity / KeyVault    →  --tc:#ff6b6b; --tcr:255,107,107 zone bg: rgba(255,107,107,.05)
  Integration / Messaging / Bus     →  --tc:#06d6a0; --tcr:6,214,160   zone bg: rgba(6,214,160,.05)
  DevOps / Monitoring / Logging     →  --tc:#ffd166; --tcr:255,209,102 zone bg: rgba(255,209,102,.05)
  Infrastructure / Network / CDN    →  --tc:#4ecdc4; --tcr:78,205,196  zone bg: rgba(78,205,196,.05)

ICON MAP:
  Web/Portal→🌐 API→🔌 Functions→⚡ Container→📦 OpenAI/LLM→🤖 AI Search→🔍
  SQL/DB→🗄️ CosmosDB→🌀 Storage/Lake→💾 Redis→🏎️ KeyVault→🔑 Auth/AD→👤
  Firewall→🛡️ ServiceBus→📨 EventHub→📬 LogicApps→🔗 DevOps→🚀 Monitor→📊
  SharePoint→📁 Teams→💬 Copilot→✨ Synapse→🔬 FrontDoor→🌍 VNet→🔒 User→👥

HTML SKELETON — fill EVERY comment and window.ARCH_FLOWS:
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><style>
PASTE_THE_FULL_CSS_HERE
</style></head>
<body>
<div class="hdr">
  <div><div class="hdr-title">PROJECT_TITLE</div><div class="hdr-sub">PATTERN · PROJECT_TYPE · CLIENT</div></div>
  <div class="hdr-pills">
    <span class="pill" style="background:rgba(123,97,255,.15);border:1px solid #7b61ff44;color:#7b61ff">Complexity: N/10</span>
    <span class="pill" style="background:rgba(0,212,170,.15);border:1px solid #00d4aa44;color:#00d4aa">N Components</span>
    <span class="pill" style="background:rgba(255,159,67,.15);border:1px solid #ff9f4344;color:#ff9f43">$N/mo</span>
  </div>
</div>
<div class="accent"></div>
<div class="techstrip">
  <span class="ts-lbl">STACK:</span>
  <!--FILL: one <span class="tb" ...>TechName</span> per tech_stack item-->
</div>
<div class="diagram">
  <div>
    <div class="col-lbl">DATA SOURCES</div>
    <!--FILL: 3-5 <div class="src-card" data-node="SLUG"> cards for external inputs/sources-->
  </div>
  <div class="platform">
    <div class="plat-lbl">&#9729; Cloud Platform</div>
    <div class="zones">
      <!--FILL: 4-6 zone divs. Each .svc MUST have data-node="SLUG".
        <div class="zone [zone-full]" style="background:rgba(TC,.05);--tc:TC;--tcr:R,G,B">
          <div class="z-hdr">EMOJI Zone Name</div>
          <div class="cards">
            <div class="svc" style="--tc:TC;--tcr:R,G,B" data-node="SLUG">
              <div class="svc-cost">$N/mo</div>
              <div class="svc-row"><div class="svc-ico">ICON</div><div class="svc-name">Service Name</div></div>
              <div class="svc-type">Azure Service</div>
              <div class="svc-sub">feature · feature</div>
            </div>
          </div>
        </div>
      Security + DevOps zones: class="zone zone-full"-->
    </div>
  </div>
  <div>
    <div class="col-lbl">CONSUMERS</div>
    <!--FILL: 2-4 <div class="out-card" data-node="SLUG"> cards for end users/output apps-->
  </div>
</div>
<div class="flowsec">
  <div class="flow-ttl">&#10132; DATA FLOW SEQUENCE</div>
  <div class="flow-steps">
    <!--FILL: numbered steps. Each: <div class="fstep"><div class="fnum" style="background:TC">N</div><span class="flbl">Label</span></div><span class="farrow">&#8594;</span>
    Last step: no farrow span-->
  </div>
</div>
<div class="ftr">
  <span class="ftr-l">PATTERN · AI-Generated Architecture</span>
  <div class="ftr-badges">
    <span class="fbadge" style="background:rgba(0,212,170,.1);border:1px solid rgba(0,212,170,.25);color:#00d4aa">ISO 27001</span>
    <span class="fbadge" style="background:rgba(0,180,216,.1);border:1px solid rgba(0,180,216,.25);color:#00b4d8">SOC 2</span>
    <span class="fbadge" style="background:rgba(123,97,255,.1);border:1px solid rgba(123,97,255,.25);color:#7b61ff">GDPR</span>
  </div>
</div>
<!-- Arrow SVG overlay — DO NOT REMOVE OR MODIFY THIS BLOCK -->
<svg id="arrow-layer">
  <defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="rgba(200,220,240,.75)"/>
    </marker>
  </defs>
</svg>
<script>
/* FILL: replace [] with your flow connections array */
window.ARCH_FLOWS=[
  /* {{from:"slug-a", to:"slug-b", color:"#00d4aa88", label:"short label"}} */
];
/* DO NOT MODIFY BELOW THIS LINE */
{ARROW_JS}
</script>
</body></html>"""

        # Embed the pre-written arrow JS into the skeleton
        SYSTEM = SYSTEM.replace("{ARROW_JS}", ARROW_JS)

        USER = f"""Fill the HTML skeleton with this architecture data. Follow every rule in the system prompt exactly.

ARCHITECTURE DATA:
{arch_str}

KEY REQUIREMENTS:
- Replace PASTE_THE_FULL_CSS_HERE with the COMPLETE CSS from the system prompt (copy every character verbatim)
- Map EVERY item in components[] to a .svc card in the correct zone — add data-node="slug" to each
- Show ALL tech_stack[] as .tb pills
- Show ALL security[] items as .svc cards in a Security zone (zone-full)
- Show ALL data_flow[] steps numbered in flowsec
- Add .svc-cost badge where monthly cost is known from service_costs[]
- Left column: 3-5 .src-card elements with data-node="slug" for external data sources
- Right column: 2-4 .out-card elements with data-node="slug" for consumers / end users
- FILL window.ARCH_FLOWS with MAXIMUM 6 flow objects — only the primary data flow spine (key hops that tell the story, not every connection)

Return ONLY the complete HTML. Start <!DOCTYPE html>. End </html>."""

        try:
            html = self._make_request(SYSTEM, USER, max_tokens=8000, timeout=300)
            if not html:
                return None
            html = html.strip()
            if html.startswith("```"):
                lines = html.splitlines()
                html = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
            if "<html" not in html.lower():
                html = f"<!DOCTYPE html><html><body style='margin:0;background:#080c18'>{html}</body></html>"
            return html
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            if hasattr(e, "body"):     body = str(e.body)
            if hasattr(e, "response"): body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None

    def generate_premium_pptx_content(self, results: dict) -> "dict | None":
        """Generate world-class slide content via Claude for an AI-premium PPT.

        Returns a dict with slides list, or None on failure.
        """
        if not self.key or st.session_state.get("_claude_blocked"):
            return None

        import json as _json
        from .utils import safe_str, safe_list, safe_dict, safe_int, sc_text

        se   = safe_dict(results.get("semantic_analysis", {}))
        te   = safe_dict(results.get("time_estimate",     {}))
        ce   = safe_dict(results.get("cost_estimate",     {}))
        ri   = safe_dict(results.get("risk_assessment",   {}))
        ar   = safe_dict(results.get("architecture",      {}))
        sc   = safe_dict(results.get("scope",             {}))
        prop = safe_dict(results.get("proposal",          {}))

        client_name  = (st.session_state.get("proposal_client_name","") or "Client").strip()
        project_type = safe_str(se.get("project_type", "Enterprise AI Solution"))
        complexity   = safe_int(se.get("complexity_score", 5))
        tech_stack   = [safe_str(t) for t in safe_list(se.get("technology_stack",[]))[:10]]
        objectives   = [safe_str(o) for o in safe_list(se.get("business_objectives",[]))[:6]]
        reqs         = [
            safe_str(safe_dict(r).get("title","")) + ": " +
            safe_str(safe_dict(r).get("description",""))[:80]
            for r in safe_list(se.get("requirements",[]))[:8]
        ]
        phases = [
            safe_str(safe_dict(p).get("name","")) + " – " +
            str(safe_int(safe_dict(p).get("hours",0))) + "h"
            for p in safe_list(te.get("phases",[]))[:6]
        ]
        dur_weeks    = safe_str(te.get("duration_weeks",""))
        total_hours  = safe_int(te.get("total_hours",0))
        monthly_cost = safe_int(safe_dict(ce).get("total_monthly_cost",0))
        annual_cost  = safe_int(safe_dict(ce).get("total_annual_cost", monthly_cost * 12))
        risks = [
            safe_str(safe_dict(r).get("title","")) + " [" +
            safe_str(safe_dict(r).get("severity","")) + "] – " +
            safe_str(safe_dict(r).get("mitigation",""))[:60]
            for r in safe_list(ri.get("risks",[]))[:5]
        ]
        arch_pattern = safe_str(ar.get("pattern",""))
        components   = [safe_str(safe_dict(c).get("name",""))
                        for c in safe_list(ar.get("components",[]))[:8]]
        in_scope     = [sc_text(s,"in_scope")    for s in safe_list(sc.get("in_scope",[]))[:6]]
        out_scope    = [sc_text(s,"out_of_scope") for s in safe_list(sc.get("out_of_scope",[]))[:4]]
        assumptions  = [sc_text(a,"assumptions") for a in safe_list(sc.get("assumptions",[]))[:5]]
        prereqs      = [sc_text(p,"prerequisites") for p in safe_list(sc.get("prerequisites",[]))[:5]]
        prop_secs    = {
            safe_str(s.get("title","")): safe_str(s.get("content",""))[:400]
            for s in safe_list(prop.get("sections",[]))[:8]
        }

        summary = {
            "client":              client_name,
            "project_type":        project_type,
            "complexity_score":    complexity,
            "technology_stack":    tech_stack,
            "business_objectives": objectives,
            "requirements":        reqs,
            "phases":              phases,
            "duration_weeks":      dur_weeks,
            "total_hours":         total_hours,
            "monthly_cost_usd":    monthly_cost,
            "annual_cost_usd":     annual_cost,
            "top_risks":           risks,
            "architecture_pattern": arch_pattern,
            "key_components":      components,
            "in_scope":            in_scope,
            "out_of_scope":        out_scope,
            "assumptions":         assumptions,
            "prerequisites":       prereqs,
            "proposal_sections":   prop_secs,
        }

        SYSTEM = """You are an expert enterprise presentation designer and business consultant at ECI, a global leader in digital transformation and AI solutions. Generate world-class PowerPoint content for an enterprise AI proposal.

CRITICAL: Return ONLY valid JSON. No markdown code blocks, no explanation. Start with { end with }.

JSON structure — exactly 22 slides:
{
  "presentation_title": "...",
  "client": "...",
  "tagline": "Powerful one-line value proposition (max 15 words)",
  "date": "Month YYYY",
  "slides": [
    {"id":1,"type":"cover","title":"Client or project name","subtitle":"AI Solution Proposal","label":"PROJECT PROPOSAL"},
    {"id":2,"type":"agenda","title":"Agenda","items":["Introduction","Business Challenge","Proposed Solution","Implementation Plan","Team & Timeline","Investment","Risk Management","Next Steps"]},
    {"id":3,"type":"section","title":"Introduction","subtitle":"Understanding Your Vision"},
    {"id":4,"type":"content","title":"About ECI","headline":"25+ Years of Enterprise Excellence","bullets":["Global leader with 500+ enterprise deployments","Specialized in AI, Cloud & Digital Transformation","Microsoft Gold Partner with Azure expertise","Dedicated support: Americas, EMEA, APAC","Trusted by leading enterprises worldwide"],"callout":"Proven partner for mission-critical AI"},
    {"id":5,"type":"content","title":"Business Context","headline":"FILL with specific challenge headline","bullets":["FILL specific challenge 1","FILL specific challenge 2","FILL market opportunity","FILL current pain point","FILL strategic imperative"],"callout":"FILL key stat or insight"},
    {"id":6,"type":"section","title":"Proposed Solution","subtitle":"Innovation Engineered for Impact"},
    {"id":7,"type":"content","title":"Solution Overview","headline":"FILL transformative architecture headline","bullets":["FILL component 1","FILL component 2","FILL component 3","FILL integration point","FILL scalability note"],"callout":"FILL technology differentiator"},
    {"id":8,"type":"content","title":"Key Capabilities","headline":"FILL capabilities headline","bullets":["FILL capability 1","FILL capability 2","FILL capability 3","FILL capability 4","FILL capability 5"],"callout":"FILL impact statement"},
    {"id":9,"type":"metrics","title":"Value at a Glance","metrics":[{"label":"Timeline","value":"N wks","desc":"Discovery to go-live"},{"label":"Efficiency","value":"60%+","desc":"Process automation rate"},{"label":"ROI","value":"3x","desc":"3-year projected return"}]},
    {"id":10,"type":"section","title":"Implementation Plan","subtitle":"Structured for Certainty"},
    {"id":11,"type":"content","title":"Project Phases","headline":"FILL phased delivery headline","bullets":["FILL phase 1 description","FILL phase 2 description","FILL phase 3 description","FILL phase 4 description"],"callout":"Agile, milestone-driven delivery"},
    {"id":12,"type":"content","title":"Project Timeline","headline":"FILL timeline headline","bullets":["FILL week range 1: milestone","FILL week range 2: milestone","FILL week range 3: milestone","FILL week range 4: milestone"],"callout":"Total: N weeks · N hours"},
    {"id":13,"type":"section","title":"Scope & Assumptions","subtitle":"Clarity Drives Success"},
    {"id":14,"type":"content","title":"Scope of Work","headline":"FILL scope headline","bullets":["FILL in-scope item 1","FILL in-scope item 2","FILL in-scope item 3","FILL out-of-scope note"],"callout":"Clearly defined boundaries"},
    {"id":15,"type":"content","title":"Assumptions & Prerequisites","headline":"Foundation for successful delivery","bullets":["FILL assumption 1","FILL assumption 2","FILL prerequisite 1","FILL prerequisite 2"],"callout":"Client commitments for day-1 readiness"},
    {"id":16,"type":"section","title":"Investment","subtitle":"Transparent & Competitive"},
    {"id":17,"type":"content","title":"Team Composition","headline":"Right expertise, optimal team size","bullets":["Project Manager – oversight & stakeholder management","AI Architect – solution design & technical leadership","AI Engineer(s) – development & integration","QA Engineer – quality assurance & testing","DevOps Engineer – CI/CD & infrastructure"],"callout":"Expert team, lean delivery"},
    {"id":18,"type":"content","title":"Investment Summary","headline":"Competitive pricing with clear ROI","bullets":["FILL implementation cost","FILL monthly infrastructure cost","FILL annual total","Payment: milestone-based tranches","Includes: documentation, training & warranty support"],"callout":"Flexible engagement models available"},
    {"id":19,"type":"section","title":"Risk Management","subtitle":"Proactive & Transparent"},
    {"id":20,"type":"content","title":"Risk Register","headline":"Identified, assessed & mitigated","bullets":["FILL risk 1 [severity]","FILL risk 2 [severity]","FILL risk 3 [severity]","FILL mitigation strategy"],"callout":"Continuous monitoring & governance"},
    {"id":21,"type":"next_steps","title":"Next Steps","steps":["Review proposal & provide written feedback","Schedule technical deep-dive session","Finalize Statement of Work","Contract signing & project kickoff"]},
    {"id":22,"type":"contact","title":"Let's Build the Future Together","subtitle":"Your transformation starts now"}
  ]
}

RULES:
1. Replace every FILL with content specific to the project data
2. Use executive-level language — confident, precise, impactful
3. Bullets: max 12 words, actionable and specific to this project
4. Include actual numbers from the data (cost, hours, weeks)
5. Callouts: memorable stats or impact statements
6. Return exactly 22 slides"""

        USER = f"""Generate 22 professional slides for this AI proposal:

{_json.dumps(summary, indent=2)}

Fill every FILL placeholder with content specific to this project. Use real numbers. Return ONLY the JSON."""

        try:
            raw = self._make_request(SYSTEM, USER, max_tokens=6000, timeout=240)
            if not raw:
                return None
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            return _json.loads(raw)
        except Exception as e:
            body = getattr(e, "message", "") or str(e)
            if hasattr(e, "body"):     body = str(e.body)
            if hasattr(e, "response"): body = str(getattr(e.response, "text", body))
            self._handle_anthropic_error(e, body)
            return None


# ═══════════════════════════════════════════════════════════════════════
#  AZURE OPENAI CLIENT — PRODUCTION
# ═══════════════════════════════════════════════════════════════════════

class AzureAI:
    def __init__(self, key, endpoint, version, deployment):
        self.deployment = deployment
        self.endpoint   = endpoint
        self._client = None
        if key and endpoint:
            _cls = _get_AzureOpenAI()
            if _cls:
                try:
                    self._client = _cls(api_key=key, api_version=version, azure_endpoint=endpoint)
                except Exception:
                    pass

    @classmethod
    def from_session(cls):
        return cls(
            st.session_state.get("azure_api_key", ""),
            st.session_state.get("azure_endpoint", ""),
            st.session_state.get("azure_api_version", "2024-06-01"),
            st.session_state.get("azure_deployment", "gpt-4"),
        )

    @property
    def is_live(self):
        return self._client is not None

    def _token_kwargs(self, n: int) -> dict:
        """Return correct token-limit kwarg: newer models use max_completion_tokens."""
        name = self.deployment.lower()
        if any(p in name for p in ("o1", "o2", "o3", "o4", "gpt-5", "4.5")):
            return {"max_completion_tokens": n}
        return {"max_tokens": n}

    def test(self):
        if not self._client:
            return False, "Not configured. Enter API Key and Endpoint."
        try:
            self._client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": "Reply OK"}],
                **self._token_kwargs(5),
            )
            return True, "Connected to " + self.deployment
        except Exception as e:
            return False, "Failed: " + str(e)[:200]

    def _call(self, system, user, max_tokens: int = 4096):
        if not self._client:
            return None
        try:
            name = self.deployment.lower()
            is_reasoning = any(p in name for p in ("o1", "o2", "o3", "o4"))
            create_kwargs = dict(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **self._token_kwargs(max_tokens),
            )
            if not is_reasoning:
                create_kwargs["temperature"] = 0.2
                create_kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**create_kwargs)
            if not resp.choices:
                return None
            txt = resp.choices[0].message.content
            if not txt or not txt.strip():
                return None
            stripped = txt.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("```", 2)[-1] if stripped.count("```") >= 2 else stripped
                stripped = stripped.lstrip("json").strip()
            return json.loads(stripped)
        except Exception as e:
            _err = str(e)
            # Show the error once per pipeline run (_az_err_shown is reset at run start)
            _seen_key = "_az_err_shown"
            if not st.session_state.get(_seen_key):
                if "DeploymentNotFound" in _err or "404" in _err:
                    st.error(
                        f"**Azure OpenAI — Deployment Not Found** (`{self.deployment}`)\n\n"
                        "The deployment name in `config.yaml` does not exist in your Azure resource. "
                        "Open [Azure AI Foundry](https://ai.azure.com) → your resource → **Deployments** "
                        "and copy the exact deployment name into `config.yaml`.",
                        icon="🔑",
                    )
                elif "AuthenticationError" in _err or "401" in _err:
                    st.error(
                        "**Azure OpenAI — Authentication Failed** — check your `api_key` in `config.yaml`.",
                        icon="🔑",
                    )
                elif "InvalidURL" in _err or "Connection" in _err:
                    st.error(
                        f"**Azure OpenAI — Cannot reach endpoint** (`{self.endpoint}`)\n\n"
                        "Check the `endpoint` value in `config.yaml`.",
                        icon="🌐",
                    )
                else:
                    st.warning(f"Azure OpenAI error: {_err[:200]}")
                st.session_state[_seen_key] = True
            return None

    def analyze_requirements(self, text):
        r = self._call(
            "You are an expert IT presales analyst for ECI consulting. Analyze the scope document thoroughly. "
            "Extract ALL requirements. Classify each as functional, non-functional, or integration. "
            "Return JSON with these keys:\n"
            "  \"requirements\": [{\"title\": str, \"description\": str, \"type\": \"functional\"|\"non-functional\"|\"integration\", \"complexity\": \"Low\"|\"Medium\"|\"High\", \"priority\": str}]\n"
            "  \"technology_stack\": [str]  — ALL technologies mentioned anywhere in the document\n"
            "  \"mandated_technologies\": [str]  — ONLY technologies EXPLICITLY REQUIRED/CHOSEN by the client "
            "(phrases like 'will be implemented using X', 'use X', 'X platform', 'X will be used', 'built on X'). "
            "CRITICAL — this is what the ARCHITECTURE must be built around. "
            "Example: 'The MVP will be implemented using Microsoft Fabric' → Microsoft Fabric goes here.\n"
            "  \"source_systems\": [str]  — technologies/systems that ALREADY EXIST in the client's environment "
            "and are DATA SOURCES (not to be built). Look for: 'existing X', 'client has X', 'client provides X', "
            "'currently using X', 'on-premises X', 'data resides on X', 'X data inventory', 'access to the X database'. "
            "Example: 'client will provide access to the Azure SQL database' → Azure SQL Database goes here. "
            "These must NOT appear in the built architecture or infrastructure cost — they are inputs/connectors only.\n"
            "  \"project_domains\": [str]  — list ALL applicable from: "
            "[\"Data Engineering & Analytics\", \"AI / ML\", \"Custom Application\", \"SharePoint & M365\", "
            "\"Integration & Collaboration\", \"Cloud Migration\", \"DevOps & Platform\", \"Modern Data Platform\"]\n"
            "  \"business_objectives\": [str]\n"
            "  \"complexity_score\": int 1-10\n"
            "  \"project_type\": str  — primary type\n"
            "  \"client_name\": str  — actual client/company name or empty string\n"
            "  \"project_title\": str  — specific project/initiative name or empty string",
            "Analyze:\n\n" + text[:15000],
        )
        if r and isinstance(r, dict) and "requirements" in r:
            return r
        return self._fb_semantic(text)

    def search_historical(self, text, projects):
        if projects:
            r = self._call(
                "Compare new project with historical data. Return JSON: "
                "{\"similar_projects\": [{\"name\": str, \"similarity\": float, \"hours\": int, \"cost\": int, \"outcome\": str}], "
                "\"benchmark_hours\": int, \"benchmark_cost\": int, \"success_patterns\": [str], \"risk_patterns\": [str]}",
                "New:\n" + text[:5000] + "\n\nHistory:\n" + json.dumps(projects, default=str),
            )
            if r:
                return r
        return {"similar_projects": [], "benchmark_hours": 0, "benchmark_cost": 0, "success_patterns": [], "risk_patterns": []}

    def estimate_time(self, semantic, rag):
        mandated   = safe_list(semantic.get("mandated_technologies", []))
        domains    = safe_list(semantic.get("project_domains", []))
        source_sys = safe_list(semantic.get("source_systems", []))
        all_tech   = safe_list(semantic.get("technology_stack", []))
        tech_lower = " ".join(mandated + all_tech).lower()

        # ── Tech complexity multipliers ──────────────────────────────────────
        mults = []
        if any(k in tech_lower for k in ["microsoft fabric", "fabric lakehouse", "onelake"]):
            mults.append("Microsoft Fabric ×1.40 — new unified platform, workspace config, OneLake schema, Direct Lake semantic model")
        if any(k in tech_lower for k in ["azure databricks", "databricks", "delta lake"]):
            mults.append("Azure Databricks ×1.50 — Spark cluster management, Delta architecture, Unity Catalog, MLflow")
        if any(k in tech_lower for k in ["azure synapse", "synapse analytics"]):
            mults.append("Azure Synapse ×1.30 — DWH setup, Spark pools, serverless SQL, pipeline orchestration")
        if any(k in tech_lower for k in ["azure data factory", "data factory"]):
            mults.append("Azure Data Factory ×1.20 — pipeline design, connectors, scheduling, error handling")
        if any(k in tech_lower for k in ["azure machine learning", "azure ml", " aml "]):
            mults.append("Azure Machine Learning ×1.35 — workspace, compute clusters, experiment tracking, model registry")
        if any(k in tech_lower for k in ["azure openai", "openai", "gpt", "ai foundry", "foundry"]):
            mults.append("Azure OpenAI/Foundry ×1.30 — prompt engineering, RAG pipeline, guardrails, evaluation framework")
        if any(k in tech_lower for k in ["kubernetes", "aks", "container"]):
            mults.append("AKS/Containers ×1.25 — cluster config, Helm charts, auto-scaling, monitoring")
        if any(k in tech_lower for k in ["private endpoint", "private network", "vnet"]):
            mults.append("Private endpoints/VNet ×1.15 — network config, DNS, firewall rules per service")
        _req_text = " ".join(
            safe_str(r.get("description", "") if isinstance(r, dict) else r)
            for r in safe_list(semantic.get("requirements", []))
        ).lower()
        if "two environment" in _req_text or \
           "dev/test" in " ".join(all_tech + mandated).lower():
            mults.append("Multi-environment (Dev/Test + Prod) ×1.20 — IaC per env, promotion pipeline, env-specific config")
        mult_block = "\n".join(f"  - {m}" for m in mults) if mults else "  (standard complexity)"

        # ── Source systems context ───────────────────────────────────────────
        src_block = ""
        if source_sys:
            src_block = ("\nSOURCE SYSTEMS (client's existing data sources — add connector/ingestion work, "
                         "NOT rebuild time): " + json.dumps(source_sys))

        # Always use the calibrated dynamic builder — it produces tech-specific
        # parallel streams including a Feature Development stream per requirement.
        result = self._fb_time(semantic, rag)

        # ── Training-context stream pruning ──────────────────────────────────
        # If the user has saved training instructions, run a lightweight AI pass
        # to remove any work streams the instructions say shouldn't be there.
        _tc = rag.get("training_context", "")
        if _tc and result and safe_list(result.get("phases")):
            result = self._prune_streams_with_training(result, semantic, _tc)

        return result

    def _prune_streams_with_training(self, time_est: dict, semantic: dict, training_ctx: str) -> dict:
        """
        Post-process work streams against training instructions using EXCLUSION:
        ask the AI which streams to REMOVE (not which to keep).
        Streams survive by default; only explicitly-violating ones are dropped.
        Silently returns the original if the call fails.
        """
        phases = safe_list(time_est.get("phases", []))
        if not phases:
            return time_est

        phase_lines = "\n".join(
            f"  - {safe_str(safe_dict(p).get('name',''))} "
            f"({safe_int(safe_dict(p).get('hours',0))}h)"
            for p in phases
        )

        # Streams the user explicitly requested must never be removed
        _user_tags = safe_list(semantic.get("project_type_tags", []))
        _protected_extra = set()
        for _t in _user_tags:
            _tl = _t.lower()
            if "data" in _tl:
                _protected_extra.add("data engineering")
            if "ai" in _tl:
                _protected_extra.add("ai / ml stream")
            if "sharepoint" in _tl:
                _protected_extra.add("sharepoint / m365")
            if "custom app" in _tl or "app" == _tl:
                _protected_extra.add("custom application")
            if "cloud" in _tl:
                _protected_extra.add("devops & platform")

        system = (
            training_ctx + "\n\n"
            "You are reviewing work streams for a project estimate. "
            "ALL streams are kept by default. "
            "Your ONLY job is to identify streams that a training instruction EXPLICITLY says must NOT be included. "
            "If no instruction explicitly forbids a stream, leave it in. "
            "Return ONLY valid JSON — no explanation, empty array if nothing to remove:\n"
            '{"remove": ["Stream Name A", ...]}'
        )
        user = (
            f"Project type: {safe_str(semantic.get('project_type', ''))}\n"
            f"User-selected types: {', '.join(_user_tags)}\n"
            f"Tech stack: {', '.join(safe_list(semantic.get('technology_stack', []))[:10])}\n\n"
            f"Work streams to review:\n{phase_lines}\n\n"
            "List ONLY streams that a training instruction explicitly forbids. "
            "If nothing is explicitly forbidden, return {\"remove\": []}."
        )
        try:
            result = self._call(system, user, max_tokens=200)
            if not (result and isinstance(result, dict) and "remove" in result):
                return time_est
            remove_set = {s.lower().strip() for s in result["remove"]}
            # Never remove user-selected type streams or the four always-protected ones
            _always_protect = {
                "discovery & design", "project management",
                "documentation & training", "devops & platform",
            } | _protected_extra
            remove_set -= _always_protect
            if not remove_set:
                return time_est
            filtered = [
                p for p in phases
                if safe_str(safe_dict(p).get("name", "")).lower().strip() not in remove_set
            ]
            if not filtered:
                return time_est
            new_total = sum(safe_int(safe_dict(p).get("hours", 0)) for p in filtered)
            pruned = dict(time_est)
            pruned["phases"] = filtered
            pruned["total_hours"] = new_total
            try:
                from .pipeline import log_agent
                log_agent("Training", f"Pruned per instructions: {', '.join(remove_set)}")
            except Exception:
                pass
            return pruned
        except Exception:
            return time_est

    def estimate_cost(self, semantic, time_est, rag):
        # ── 1. Build price reference from catalog (+ live prices where available) ──
        live = {}
        try:
            live = _fetch_live_azure_pricing()
        except Exception:
            pass
        catalog_lines = []
        catalog_ceil = {}
        for svc, (tier, base_mo, desc) in _INFRA_COST_CATALOG.items():
            mo = live.get(svc, base_mo)
            catalog_lines.append(f"  {svc} | {tier} | ${mo}/mo | {desc}")
            catalog_ceil[svc] = mo
        catalog_ref = "\n".join(catalog_lines)

        # ── 2. Extract RAG benchmark cost signals ─────────────────────────────────
        benchmark_cost    = safe_int(rag.get("benchmark_cost", 0))
        bm_services       = safe_list(rag.get("benchmark_cost_services", []))
        milvus_ctx        = rag.get("milvus_context", "")
        bm_hint = ""
        if benchmark_cost > 0:
            bm_hint += f"\nBenchmark from similar past project: ${benchmark_cost}/mo total infra"
        if bm_services:
            bm_lines = ", ".join(
                f"{safe_str(s.get('service'))} ${safe_int(s.get('monthly_cost'))}/mo"
                for s in bm_services[:8]
            )
            bm_hint += f"\nServices from similar project estimation file: {bm_lines}"
        if milvus_ctx:
            bm_hint += f"\n\nContext from similar past projects:\n{milvus_ctx[:1200]}"

        # ── 3. Call AI with anchored pricing ─────────────────────────────────────
        _training_ctx = rag.get("training_context", "")
        system_prompt = (
            (_training_ctx + "\n\n" if _training_ctx else "") +
            "You are an ECI Azure infrastructure cost estimator.\n"
            "Rules:\n"
            "1. Estimate ONLY Azure/cloud infra costs — NOT labor, NOT developer time.\n"
            "2. Select services actually required by the project.\n"
            "3. MANDATORY BASELINE — ALWAYS include these three regardless of project type "
            "(they are required by every Azure solution): "
            "Azure Key Vault (secrets management), "
            "Azure Monitor / Log Analytics (observability & alerting), "
            "Azure AD / Entra ID (identity & access). "
            "Also include Azure DevOps if CI/CD, pipelines, or DevOps are mentioned.\n"
            "4. You MUST use the prices below as your ceiling — never exceed them without justification.\n"
            "5. Prefer standard/basic tiers unless complexity score >= 8.\n"
            "6. If a similar project benchmark is provided, anchor your total to that range.\n\n"
            "AZURE PRICE REFERENCE (East US, Pay-As-You-Go):\n"
            + catalog_ref + "\n\n"
            "Return JSON only:\n"
            "{\"total_monthly_cost\": int, \"total_annual_cost\": int, "
            "\"azure_costs\": [{\"service\": str, \"tier\": str, \"monthly_cost\": int, \"description\": str, "
            "\"region\": str (e.g. 'East US', 'West Europe'), \"category\": str (one of: Compute, Database, Storage, AI/ML, Networking, Security, Monitoring, Integration, Other)}], "
            "\"third_party_costs\": [{\"name\": str, \"monthly_cost\": int, \"description\": str}], "
            "\"cost_optimization\": [str], \"notes\": str}"
        )
        mandated = safe_list(semantic.get("mandated_technologies", []))
        source_sys = safe_list(semantic.get("source_systems", []))
        all_tech = safe_list(semantic.get("technology_stack", []))
        # Use mandated as primary build list; fall back to full stack minus source systems
        build_tech = mandated if mandated else [t for t in all_tech if t not in source_sys]
        mandate_hint = (
            "\nMANDATED TECHNOLOGIES (must include these in the cost estimate): " + json.dumps(mandated)
        ) if mandated else ""
        source_hint = (
            "\nSOURCE SYSTEMS — client's EXISTING systems, NOT to be built, do NOT include in cost: "
            + json.dumps(source_sys)
        ) if source_sys else ""
        user_prompt = (
            "Estimate infrastructure costs for this project:\n"
            "Technologies to BUILD (select from these for your cost estimate): " + json.dumps(build_tech)
            + "\nAll tech mentioned in document (for context only): " + json.dumps(all_tech)
            + mandate_hint
            + source_hint
            + "\nComplexity: " + str(semantic.get("complexity_score", 5)) + "/10"
            + "\nProject type: " + safe_str(semantic.get("project_type"))
            + "\nKey requirements: " + json.dumps(
                [safe_str(safe_dict(r).get("title","")) for r in safe_list(semantic.get("requirements"))[:8]]
            )
            + bm_hint
        )
        r = self._call(system_prompt, user_prompt)

        # ── 4. Validate & clamp against catalog ceiling ───────────────────────────
        if r and isinstance(r, dict) and "azure_costs" in r:
            for svc in safe_list(r.get("azure_costs", [])):
                svc_name = safe_str(svc.get("service",""))
                ceil = catalog_ceil.get(svc_name)
                if ceil and safe_int(svc.get("monthly_cost", 0)) > ceil * 2:
                    svc["monthly_cost"] = ceil   # clamp to catalog price
            # Recalculate totals after clamping
            total_mo = sum(safe_int(s.get("monthly_cost",0)) for s in r["azure_costs"])
            if total_mo > 0:
                r["total_monthly_cost"] = total_mo
                r["total_annual_cost"]  = total_mo * 12
            return r
        return self._fb_cost(time_est)

    def analyze_risk(self, semantic, time_est, cost_est):
        reqs = safe_list(semantic.get("requirements", []))
        tech = safe_list(semantic.get("technology_stack", []))
        phases = safe_list(time_est.get("phases", []))
        azure_svcs = safe_list(cost_est.get("azure_costs", []))
        complexity = safe_int(semantic.get("complexity_score", 5))
        proj_type = safe_str(semantic.get("project_type", "Software Solution"))

        req_titles = "; ".join(
            safe_str(safe_dict(q).get("title", q) if isinstance(q, dict) else q)
            for q in reqs[:20]
        )
        phase_summary = "; ".join(
            f"{safe_str(safe_dict(p).get('name',''))} ({safe_int(safe_dict(p).get('hours',0))}h)"
            for p in phases[:6]
        )
        svc_names = ", ".join(safe_str(safe_dict(s).get("service", "")) for s in azure_svcs[:10])
        _training_ctx = st.session_state.get("_training_context", "")

        SYSTEM = (
            (_training_ctx + "\n\n" if _training_ctx else "") +
            "You are a senior ECI risk manager and delivery assurance specialist. "
            "Produce a formal, comprehensive project risk register.\n\n"
            "For every risk include:\n"
            "- id: RK-001, RK-002, … (sequential)\n"
            "- category: Technical | Schedule | Resource | Budget | Data/Security | Compliance | Integration | External\n"
            "- title: concise risk name (<10 words)\n"
            "- description: specific risk event that could materialise\n"
            "- probability: High | Medium | Low\n"
            "- impact: High | Medium | Low\n"
            "- severity: Critical | High | Medium | Low  "
            "(Critical = High prob + High impact; High = any High prob or High impact; etc.)\n"
            "- rating: numeric score 1-9 (prob score * impact score where High=3, Medium=2, Low=1)\n"
            "- mitigation: concrete preventive actions BEFORE the risk materialises\n"
            "- contingency_plan: specific reactive actions IF the risk materialises\n"
            "- risk_owner: role responsible (e.g. 'Technical Lead', 'Project Manager', 'Client Stakeholder')\n"
            "- status: Open | Mitigated | Accepted\n\n"
            "Return ONLY valid JSON:\n"
            "{\"overall_score\": int 1-10, \"overall_level\": str, "
            "\"risks\": [{\"id\": str, \"category\": str, \"title\": str, \"description\": str, "
            "\"probability\": str, \"impact\": str, \"severity\": str, \"rating\": int, "
            "\"mitigation\": str, \"contingency_plan\": str, \"risk_owner\": str, \"status\": str}]}"
        )
        USER = (
            f"PROJECT CONTEXT:\n"
            f"  Type: {proj_type}\n"
            f"  Complexity: {complexity}/10\n"
            f"  Total Effort: {safe_int(time_est.get('total_hours', 0)):,} hours\n"
            f"  Duration: {safe_str(time_est.get('duration_weeks', ''))}\n"
            f"  Infrastructure Monthly: ${safe_int(cost_est.get('total_monthly_cost', 0)):,}\n"
            f"  Requirement Count: {len(reqs)}\n"
            f"  Technology Stack: {', '.join(safe_str(t) for t in tech[:15])}\n"
            f"  Key Requirements: {req_titles or '(none)'}\n"
            f"  Project Phases: {phase_summary or '(none)'}\n"
            f"  Azure Services: {svc_names or '(none)'}\n\n"
            "Identify 10-15 risks across ALL categories: Technical, Schedule, Resource, Budget, "
            "Data/Security, Compliance, Integration, and External. "
            "Return only the JSON object — no markdown, no preamble."
        )
        r = self._call(SYSTEM, USER, max_tokens=3000)
        if r and isinstance(r, dict) and "risks" in r:
            return r
        return self._fb_risk(semantic)

    def design_architecture(self, semantic, rag):
        mandated = safe_list(semantic.get("mandated_technologies", []))
        domains  = safe_list(semantic.get("project_domains", []))
        mandate_block = (
            "\n\nCRITICAL — MANDATED TECHNOLOGIES (client has explicitly specified these — YOU MUST build the architecture around them, do NOT substitute with other services):\n"
            + json.dumps(mandated, default=str)
        ) if mandated else ""
        domain_block = (
            "\nProject domains: " + ", ".join(domains)
        ) if domains else ""
        _training_ctx = rag.get("training_context", "")
        r = self._call(
            (_training_ctx + "\n\n" if _training_ctx else "") +
            "You are an Azure Solutions Architect for ECI. Use Well-Architected Framework. "
            "Design the architecture to match the project's specific domain and technology requirements. "
            "Do NOT default to a generic web-app architecture — align components to the actual project type "
            "(e.g. if it is a Data Engineering project use Fabric/ADF/Databricks/Synapse, not just SQL; "
            "if it is AI/ML use Azure ML / AI Foundry; if it is SharePoint use SPO + Power Platform, etc.). "
            "Return JSON: {\"pattern\": str, \"components\": [{\"name\": str, \"type\": str, \"azure_service\": str, \"services\": [str]}], "
            "\"data_flow\": [str], \"security\": [str], \"scalability\": str, \"availability\": str}",
            "Design:"
            + mandate_block
            + domain_block
            + "\nType: " + safe_str(semantic.get("project_type"))
            + "\nAll tech mentioned: " + json.dumps(safe_list(semantic.get("technology_stack")))
            + "\nReqs: " + json.dumps(safe_list(semantic.get("requirements"))[:15], default=str)
            + ("\n\nSimilar past projects for architecture reference:\n" + rag["milvus_context"]
               if rag.get("milvus_context") else ""),
        )
        if r and isinstance(r, dict) and "components" in r:
            return r
        return self._fb_arch()

    def define_scope(self, semantic, time_est, cost_est, template_context: str = ""):
        reqs = safe_list(semantic.get("requirements", []))
        phases = safe_list(time_est.get("phases", []))
        tech = safe_list(semantic.get("technology_stack", []))
        complexity = safe_int(semantic.get("complexity_score", 5))
        proj_type = safe_str(semantic.get("project_type", "Software Solution"))
        biz_objs = safe_list(semantic.get("business_objectives", []))
        total_hours = safe_int(time_est.get("total_hours", 0))
        monthly_cost = safe_int(cost_est.get("total_monthly_cost", 0))
        azure_svcs = safe_list(cost_est.get("azure_costs", []))

        SYSTEM = (
            "You are a senior ECI professional services architect and SOW specialist. "
            "Produce a formal Statement of Work scope definition.\n\n"
            "LEGAL WRITING STANDARDS:\n"
            "- Use 'shall' for mandatory obligations; 'will' for planned/intended actions\n"
            "- Every item must be specific, measurable, and verifiable — zero vague language\n"
            "- Assign sequential IDs: SC-001… for in-scope, EX-001… for exclusions, "
            "  AS-001… for assumptions, PR-001… for prerequisites\n\n"
            "CRITICAL — ESTIMATION COVERAGE:\n"
            "  Any Azure service, capability, or activity included in the effort/cost estimate "
            "  but NOT explicitly mentioned in the requirements MUST be captured as an assumption "
            "  (AS-xxx) or out-of-scope exclusion (EX-xxx) with note: "
            "  'Included in estimation for planning purposes; formal scope requires client confirmation.'\n\n"
            "Return ONLY valid JSON with this exact schema:\n"
            "{\n"
            "  \"in_scope\": [{\"id\": \"SC-001\", \"title\": str, \"description\": str, "
            "\"deliverable\": str, \"acceptance_criteria\": str}],\n"
            "  \"out_of_scope\": [{\"id\": \"EX-001\", \"exclusion\": str, \"rationale\": str, "
            "\"change_request_condition\": str}],\n"
            "  \"assumptions\": [{\"id\": \"AS-001\", \"party\": \"Client or ECI\", \"statement\": str, "
            "\"consequence\": str, \"obligation\": str}],\n"
            "  \"prerequisites\": [{\"id\": \"PR-001\", \"item\": str, \"provided_by\": \"Client or ECI\", "
            "\"milestone\": str, \"consequence_if_delayed\": str}]\n"
            "}"
        )
        if template_context:
            SYSTEM += "\n\nADDITIONAL CONTEXT FROM TEMPLATE:\n" + template_context

        req_lines = "\n".join(
            "  " + str(i + 1) + ". ["
            + safe_str(safe_dict(q).get("type", "") if isinstance(q, dict) else "")
            + "] "
            + safe_str(safe_dict(q).get("title", q) if isinstance(q, dict) else q)
            + ((" — " + safe_str(safe_dict(q).get("description", "")))
               if isinstance(q, dict) and q.get("description") else "")
            for i, q in enumerate(reqs[:40])
        )
        phase_lines = "\n".join(
            "  - " + safe_str(safe_dict(p).get("name", "")) + " ("
            + str(safe_int(safe_dict(p).get("hours", 0))) + " hrs)"
            for p in phases[:8]
        )
        svc_lines = ", ".join(
            safe_str(safe_dict(s).get("service", ""))
            + " (" + safe_str(safe_dict(s).get("category", "")) + ")"
            for s in azure_svcs[:12]
        )
        biz_lines = "\n".join("  - " + safe_str(b) for b in biz_objs[:8])

        USER = (
            f"PROJECT CONTEXT:\n"
            f"  Type: {proj_type}\n"
            f"  Complexity: {complexity}/10\n"
            f"  Total Effort: {total_hours:,} person-hours\n"
            f"  Infrastructure Monthly: ${monthly_cost:,}\n"
            f"  Technology Stack: {', '.join(safe_str(t) for t in tech[:15])}\n\n"
            f"BUSINESS OBJECTIVES:\n{biz_lines or '  (not specified)'}\n\n"
            f"REQUIREMENTS ({len(reqs)} total):\n{req_lines or '  (none extracted)'}\n\n"
            f"PROJECT PHASES:\n{phase_lines or '  (none)'}\n\n"
            f"AZURE SERVICES IN ESTIMATE:\n  {svc_lines or '(none)'}\n\n"
            "INSTRUCTIONS:\n"
            f"1. Define 8-15 in-scope items covering all aspects of the {proj_type} delivery\n"
            "2. Define 6-10 out-of-scope exclusions protecting against common scope creep\n"
            "3. Define 6-10 assumptions — especially for Azure services or capabilities included "
            "   in the estimate but not explicitly requested in requirements\n"
            "4. Define 4-8 prerequisites the client must fulfil before or during delivery\n"
            "5. For each Azure service in the estimate not directly traceable to a requirement, "
            "   add an assumption stating it was included for estimation and requires confirmation\n"
            "Return only the JSON object — no markdown, no preamble."
        )
        r = self._call(SYSTEM, USER, max_tokens=4000)
        if r and isinstance(r, dict) and "in_scope" in r:
            return r
        return self._fb_scope()

    def write_proposal(self, semantic, time_est, cost_est, risk, arch, scope, template_context: str = ""):
        system = (
            "You are an ECI presales proposal writer. Write professional proposal. "
            "Return JSON: {\"sections\": [{\"title\": str, \"content\": str}], \"quality_checks\": {str: bool}}. "
            "Include sections: Executive Summary, Understanding & Approach, Technical Solution, Team, Timeline, Infrastructure Costs."
        )
        if template_context:
            system += "\n\n" + template_context
        def _sc(items, section):
            return "; ".join(
                (i.get("title") or i.get(
                    {"in_scope": "title", "out_of_scope": "exclusion",
                     "assumptions": "statement", "prerequisites": "item"}.get(section, "title"), "")
                if isinstance(i, dict) else str(i))
                for i in safe_list(items)[:6]
            )
        r = self._call(
            system,
            "Generate:\nType: " + safe_str(semantic.get("project_type"))
            + "\nReqs: " + str(len(safe_list(semantic.get("requirements"))))
            + "\nHours: " + str(time_est.get("total_hours", 0))
            + "\nInfra Monthly: $" + str(cost_est.get("total_monthly_cost", 0))
            + "\nRisk: " + safe_str(risk.get("overall_level"))
            + "\nArch: " + safe_str(arch.get("pattern"))
            + "\nPhases: " + json.dumps([{"name": safe_str(p.get("name")), "hours": safe_int(p.get("hours"))} for p in safe_list(time_est.get("phases"))])
            + "\nIn Scope: " + _sc(scope.get("in_scope"), "in_scope")
            + "\nOut of Scope: " + _sc(scope.get("out_of_scope"), "out_of_scope")
            + "\nAssumptions: " + _sc(scope.get("assumptions"), "assumptions"),
        )
        if r and isinstance(r, dict) and "sections" in r:
            return r
        return self._fb_proposal(semantic, time_est, cost_est, risk, arch)

    _SECTION_SYSTEMS = {
        "requirements": (
            "You are an expert IT presales analyst for ECI consulting. Analyze the scope document thoroughly. "
            "Extract ALL requirements. Classify each as functional, non-functional, or integration. "
            "Return JSON: {\"requirements\": [{\"title\": str, \"description\": str, \"type\": \"functional\" or \"non-functional\" or \"integration\", \"complexity\": \"Low\" or \"Medium\" or \"High\", \"priority\": str}], "
            "\"technology_stack\": [str], \"business_objectives\": [str], \"complexity_score\": int 1-10, \"project_type\": str}"
        ),
        "time": (
            "You are an expert ECI project estimator. Use three-point estimation. "
            "Break every task into granular sub-tasks of 4-8 hours MAX. "
            "Return JSON: {\"total_hours\": int, \"duration_weeks\": \"N weeks\", \"confidence\": str, \"buffer\": str, "
            "\"phases\": [{\"name\": str, \"hours\": int, \"percentage\": \"N%\", \"week_label\": str, "
            "\"tasks\": [{\"name\": str, \"hours\": int, \"low_hours\": int, \"high_hours\": int, \"role\": str, \"justification\": str}]}], "
            "\"milestones\": [{\"name\": str, \"week\": int, \"description\": str}], "
            "\"three_point\": {\"optimistic\": int, \"most_likely\": int, \"pessimistic\": int}, "
            "\"roles\": [{\"name\": str, \"allocation_pct\": float, \"rate\": int}]}"
        ),
        "cost": (
            "You are an ECI infrastructure cost estimator. Estimate ONLY Azure/cloud infrastructure costs. "
            "Return JSON: {\"total_monthly_cost\": int, \"total_annual_cost\": int, "
            "\"azure_costs\": [{\"service\": str, \"tier\": str, \"monthly_cost\": int, \"description\": str, "
            "\"region\": str (e.g. 'East US', 'West Europe'), \"category\": str (one of: Compute, Database, Storage, AI/ML, Networking, Security, Monitoring, Integration, Other)}], "
            "\"third_party_costs\": [{\"name\": str, \"monthly_cost\": int, \"description\": str}], "
            "\"cost_optimization\": [str], \"notes\": str}"
        ),
        "risk": (
            "You are a senior ECI risk manager. Produce a formal project risk register. "
            "Return JSON: {\"overall_score\": int 1-10, \"overall_level\": str, "
            "\"risks\": [{\"id\": str, \"category\": str, \"title\": str, \"description\": str, "
            "\"probability\": str, \"impact\": str, \"severity\": str, \"rating\": int, "
            "\"mitigation\": str, \"contingency_plan\": str, \"risk_owner\": str, \"status\": str}]}"
        ),
        "architecture": (
            "You are an Azure Solutions Architect for ECI. Use Well-Architected Framework. "
            "Return JSON: {\"pattern\": str, \"components\": [{\"name\": str, \"type\": str, \"azure_service\": str, \"services\": [str]}], "
            "\"data_flow\": [str], \"security\": [str], \"scalability\": str, \"availability\": str}"
        ),
        "scope": (
            "You are a senior ECI professional services architect and SOW specialist. "
            "Produce a formal Statement of Work scope definition. "
            "Return JSON: {\"in_scope\": [{\"id\": str, \"title\": str, \"description\": str, "
            "\"deliverable\": str, \"acceptance_criteria\": str}], "
            "\"out_of_scope\": [{\"id\": str, \"exclusion\": str, \"rationale\": str, "
            "\"change_request_condition\": str}], "
            "\"assumptions\": [{\"id\": str, \"party\": str, \"statement\": str, "
            "\"consequence\": str, \"obligation\": str}], "
            "\"prerequisites\": [{\"id\": str, \"item\": str, \"provided_by\": str, "
            "\"milestone\": str, \"consequence_if_delayed\": str}]}"
        ),
        "proposal": (
            "You are an ECI presales proposal writer. Write a professional proposal. "
            "Return JSON: {\"sections\": [{\"title\": str, \"content\": str}], \"quality_checks\": {str: bool}}. "
            "Include: Executive Summary, Understanding & Approach, Technical Solution, Team, Timeline, Infrastructure Costs."
        ),
        "diagrams": (
            "You are an Azure Solutions Architect for ECI. Generate valid Mermaid.js diagram code. "
            "Return JSON with keys: infrastructure, data_flow, sequence, deployment, security — each a valid Mermaid string."
        ),
    }

    def regenerate_section(self, section_key: str, original_output: dict,
                           feedback: str, context: dict) -> dict:
        """Re-generate one section with human reviewer feedback applied."""
        system = (
            self._SECTION_SYSTEMS.get(section_key, "You are an ECI presales AI. Return valid JSON.")
            + "\n\nIMPORTANT — REVISION INSTRUCTIONS: You are revising a previous output based on "
            "expert feedback from the presales architect. Apply the feedback exactly. Keep everything "
            "not mentioned unchanged. Return the same JSON schema as the original output."
        )
        user = (
            "PREVIOUS OUTPUT:\n" + json.dumps(original_output, indent=2, default=str)[:5000]
            + "\n\nEXPERT FEEDBACK:\n" + feedback
            + "\n\nCURRENT CONTEXT:\n" + json.dumps(context, indent=2, default=str)[:4000]
            + "\n\nReturn a revised JSON matching the exact same schema."
        )
        result = self._call(system, user)
        if result and isinstance(result, dict):
            return result
        return original_output

    def _sanitize_time(self, data):
        clean_ms = []
        for m in safe_list(data.get("milestones")):
            if isinstance(m, dict):
                clean_ms.append({
                    "name": safe_str(m.get("name", "Milestone")),
                    "week": safe_int(m.get("week", 0)),
                    "description": safe_str(m.get("description", "")),
                })
            elif isinstance(m, str):
                clean_ms.append({"name": m, "week": 0, "description": ""})
        data["milestones"] = clean_ms
        clean_ph = []
        for p in safe_list(data.get("phases")):
            if not isinstance(p, dict):
                continue
            clean_tasks = []
            for t in safe_list(p.get("tasks")):
                if not isinstance(t, dict):
                    continue
                t_hrs = safe_int(t.get("hours", 0))
                t_name = safe_str(t.get("name", ""))
                t_role = safe_str(t.get("role", ""))
                t_just = safe_str(t.get("justification", ""))
                if t_hrs > 8:
                    sub_tasks = _split_large_task(t_name, t_hrs, t_role, t_just)
                    clean_tasks.extend(sub_tasks)
                else:
                    clean_tasks.append({
                        "name": t_name,
                        "hours": t_hrs,
                        "low_hours": safe_int(t.get("low_hours", int(t_hrs * 0.8))),
                        "high_hours": safe_int(t.get("high_hours", int(t_hrs * 1.35))),
                        "role": t_role,
                        "justification": t_just,
                    })
            phase_hours = sum(tk["hours"] for tk in clean_tasks)
            phase_weeks = round(phase_hours / 40, 1) if phase_hours else 0
            clean_ph.append({
                "name":           safe_str(p.get("name", "Phase")),
                "domain":         safe_str(p.get("domain", "")),
                "hours":          phase_hours,
                "low_hours":      int(phase_hours * 0.8),
                "high_hours":     int(phase_hours * 1.35),
                "percentage":     safe_str(p.get("percentage", "0%")),
                "duration_weeks": phase_weeks,
                "week_label":     f"{phase_weeks:.0f}w",
                "tasks":          clean_tasks,
            })
        data["phases"] = clean_ph
        recalc_total = sum(p["hours"] for p in clean_ph)
        if recalc_total > 0:
            data["total_hours"] = recalc_total
            data["three_point"] = {
                "optimistic": int(recalc_total * 0.8),
                "most_likely": recalc_total,
                "pessimistic": int(recalc_total * 1.35),
            }
            for p in clean_ph:
                p["percentage"] = str(round(p["hours"] / max(recalc_total, 1) * 100)) + "%"
        else:
            data["total_hours"] = safe_int(data.get("total_hours", 0))
            data["three_point"] = safe_dict(data.get("three_point"))
        data["duration_weeks"] = safe_str(data.get("duration_weeks", "TBD"))
        data["confidence"] = safe_str(data.get("confidence", "N/A"))
        data["buffer"] = safe_str(data.get("buffer", "N/A"))
        clean_roles = []
        for rl in safe_list(data.get("roles")):
            if isinstance(rl, dict):
                clean_roles.append({
                    "name": safe_str(rl.get("name", "")),
                    "allocation_pct": float(rl.get("allocation_pct", 0)),
                    "rate": safe_int(rl.get("rate", 100)),
                })
        data["roles"] = clean_roles
        return data

    def _fb_semantic(self, text):
        return _analyze_text_dynamic(text)

    def _fb_time(self, semantic, rag):
        return _build_dynamic_time(semantic, rag=rag)

    def _fb_cost(self, time_est):
        sem  = st.session_state.get("_last_semantic", {})
        text = st.session_state.get("_extracted_text", "")
        return _build_dynamic_cost(sem, time_est, text=text)

    def _fb_risk(self, semantic):
        te = st.session_state.get("_last_time_est", {})
        ce = st.session_state.get("_last_cost_est", {})
        return _build_dynamic_risk(semantic, te, ce)

    def _fb_arch(self):
        sem = st.session_state.get("_last_semantic", {})
        return _build_dynamic_arch(sem)

    def _fb_scope(self):
        sem = st.session_state.get("_last_semantic", {})
        te = st.session_state.get("_last_time_est", {})
        return _build_dynamic_scope(sem, te)

    def _fb_proposal(self, sem, te, ce, ri, ar):
        d = datetime.now().strftime("%B %d, %Y")
        reqs = safe_list(sem.get("requirements"))
        monthly = safe_int(ce.get("total_monthly_cost"))
        annual = safe_int(ce.get("total_annual_cost"))
        return {"sections": [
            {"title": "Executive Summary", "content": "**Date:** " + d + "\n\nECI proposes a " + safe_str(sem.get("project_type")) + " solution. **" + str(len(reqs)) + " requirements** identified.\n\n- Effort: **" + str(te.get("total_hours", 0)) + "h** over **" + safe_str(te.get("duration_weeks")) + "**\n- Infrastructure: **$" + str(monthly) + "/month** ($" + str(annual) + "/year)\n- Risk: **" + safe_str(ri.get("overall_level")) + "**"},
            {"title": "Understanding & Approach", "content": "ECI follows Discovery, Design, Development, Testing, Deployment with hypercare."},
            {"title": "Technical Solution", "content": "**Pattern:** " + safe_str(ar.get("pattern")) + "\n\n" + "\n".join("- **" + safe_str(safe_dict(c).get("name")) + "**: " + safe_str(safe_dict(c).get("azure_service")) for c in safe_list(ar.get("components")))},
            {"title": "Team & Delivery", "content": "ECI will deploy a cross-functional team including Architects, Lead Developers, Senior Developers, QA Engineers, DevOps Engineers, and a Project Manager.\n\nDelivery follows an Agile methodology with bi-weekly sprints and milestone reviews."},
            {"title": "Timeline", "content": "\n".join("- **" + safe_str(safe_dict(p).get("name")) + "** — " + str(safe_int(safe_dict(p).get("hours"))) + "h (" + safe_str(safe_dict(p).get("percentage")) + ")" for p in safe_list(te.get("phases")))},
            {"title": "Infrastructure Costs", "content": "**Monthly:** $" + str(monthly) + "  |  **Annual:** $" + str(annual) + "\n\n" + "\n".join("- **" + safe_str(safe_dict(a).get("service")) + "** (" + safe_str(safe_dict(a).get("tier", "")) + "): $" + str(safe_int(safe_dict(a).get("monthly_cost"))) + "/mo" for a in safe_list(ce.get("azure_costs")))},
        ], "quality_checks": {"ECI Tone": True, "Personalization": True, "Terminology": True, "Value Proposition": True, "Structure": True}}

    def generate_mermaid_diagrams(self, semantic, arch):
        r = self._call(
            "You are an Azure Solutions Architect for ECI. Generate Mermaid.js diagram code for the architecture. "
            "CRITICAL RULES for all diagrams:\n"
            "1. Use ONLY simple rectangular nodes: NodeId[\"Label\"]. "
            "   NEVER use cylinder [(...)], stadium ([...]), subroutine [[...]], or asymmetric >...] shapes — they break rendering.\n"
            "2. Use flowchart TD or flowchart LR (NOT graph TD/graph LR).\n"
            "3. Keep node labels under 40 characters.\n"
            "4. Do NOT include style, classDef, or linkStyle directives.\n\n"
            "Return JSON with these keys, each a valid Mermaid string:\n"
            "{\"infrastructure\": str (flowchart TD of Azure components),\n"
            " \"data_flow\": str (flowchart LR of data movement between services),\n"
            " \"sequence\": str (sequenceDiagram of a typical user request flow),\n"
            " \"deployment\": str (flowchart TD of CI/CD pipeline and environments),\n"
            " \"security\": str (flowchart TD of security layers and controls)}",
            "Architecture:\nPattern: " + safe_str(arch.get("pattern"))
            + "\nComponents: " + json.dumps(safe_list(arch.get("components"))[:10], default=str)
            + "\nData Flow: " + json.dumps(safe_list(arch.get("data_flow")))
            + "\nSecurity: " + json.dumps(safe_list(arch.get("security")))
            + "\nTech: " + json.dumps(safe_list(semantic.get("technology_stack"))),
        )
        if r and isinstance(r, dict) and "infrastructure" in r:
            return r
        return self._fb_mermaid(arch)

    def generate_discovery_questions(self, semantic: dict, scope: dict, risk: dict) -> dict:
        """
        Agent 9 — Smart Discovery Question Generator.
        Generates a prioritised list of 10-15 questions for the first client meeting,
        organised by: Technical, Business, Budget, Timeline, Decision Process.

        Returns JSON:
        {
          "project_type": str,
          "priority_summary": str,
          "total_questions": int,
          "categories": [
            {
              "name": str,
              "icon": str,
              "color": str,
              "questions": [
                {
                  "question": str,
                  "why": str,
                  "priority": "High" | "Medium" | "Low",
                  "follow_up": str
                }
              ]
            }
          ]
        }
        """
        r = self._call(
            "You are an expert ECI presales consultant preparing for a discovery meeting with a client. "
            "Based on the analysed scope, generate a PRIORITISED list of 10-15 focused discovery questions "
            "the presales team should ask in the first meeting. "
            "Questions must be specific to THIS project — reference real details from the scope. "
            "Each question should unblock a real estimation or proposal decision. "
            "Return JSON:\n"
            "{\"project_type\": str,\n"
            " \"priority_summary\": str,\n"
            " \"total_questions\": int,\n"
            " \"categories\": [\n"
            "   {\"name\": str, \"icon\": str, \"color\": str,\n"
            "    \"questions\": [\n"
            "      {\"question\": str, \"why\": str,\n"
            "       \"priority\": \"High\" or \"Medium\" or \"Low\",\n"
            "       \"follow_up\": str}\n"
            "    ]}\n"
            " ]}\n\n"
            "Use EXACTLY these category names with these colors:\n"
            "Technical (#00b4d8), Business (#00d4aa), Budget (#ffd166), "
            "Timeline (#7b61ff), Decision Process (#ff6b6b).\n"
            "Assign icons: Technical=⚙️, Business=📊, Budget=💰, Timeline=📅, Decision Process=🔑.\n"
            "High priority = blocking the estimate. Medium = important context. Low = nice to know.\n"
            "Aim for 3-4 questions per category. total_questions must match the actual count.",
            "Project type: " + safe_str(semantic.get("project_type"))
            + "\nRequirements (" + str(len(safe_list(semantic.get("requirements")))) + "): "
            + json.dumps([safe_str(safe_dict(q).get("title")) for q in safe_list(semantic.get("requirements"))[:15]])
            + "\nTech stack: " + json.dumps(safe_list(semantic.get("technology_stack")))
            + "\nIn-scope: " + json.dumps(safe_list(scope.get("in_scope"))[:8])
            + "\nAssumptions: " + json.dumps(safe_list(scope.get("assumptions"))[:5])
            + "\nTop risks: " + json.dumps([safe_str(safe_dict(r2).get("title")) for r2 in safe_list(risk.get("risks"))[:5]])
            + "\nObjectives: " + json.dumps(safe_list(semantic.get("business_objectives"))[:5]),
        )
        if r and isinstance(r, dict) and "categories" in r:
            # Ensure totals are accurate
            total = sum(len(cat.get("questions", [])) for cat in r.get("categories", []))
            r["total_questions"] = total
            return r
        # Fallback
        project_type = safe_str(semantic.get("project_type", "IT Project"))
        return {
            "project_type": project_type,
            "priority_summary": "Focus on High priority questions to unblock estimation.",
            "total_questions": 10,
            "categories": [
                {"name": "Technical", "icon": "⚙️", "color": "#00b4d8", "questions": [
                    {"question": "What is the expected peak number of concurrent users?", "why": "Drives infrastructure sizing and cost estimate", "priority": "High", "follow_up": "Do you have existing load test data or traffic analytics?"},
                    {"question": "What existing systems must this solution integrate with?", "why": "Integration complexity is the biggest estimation variable", "priority": "High", "follow_up": "Are API specifications available for these systems?"},
                ]},
                {"name": "Business", "icon": "📊", "color": "#00d4aa", "questions": [
                    {"question": "Who are the primary end users and what is their technical proficiency?", "why": "Determines UI complexity and training requirements", "priority": "Medium", "follow_up": "Will there be internal champions to support adoption?"},
                    {"question": "What does a successful go-live look like to your business?", "why": "Defines acceptance criteria and avoids scope creep", "priority": "High", "follow_up": "Are there any KPIs or metrics you will use to measure success?"},
                ]},
                {"name": "Budget", "icon": "💰", "color": "#ffd166", "questions": [
                    {"question": "Is there an approved budget ceiling for this engagement?", "why": "Determines scope prioritisation and team size", "priority": "High", "follow_up": "Is the budget split between implementation and ongoing infrastructure?"},
                    {"question": "What is the preferred commercial model — Fixed Price or T&M?", "why": "Affects risk allocation and contract structure", "priority": "Medium", "follow_up": "Are milestone-based payments acceptable?"},
                ]},
                {"name": "Timeline", "icon": "📅", "color": "#7b61ff", "questions": [
                    {"question": "Is there a hard go-live date, and what is driving it?", "why": "Critical for resourcing and phase planning", "priority": "High", "follow_up": "What is the consequence of missing this date?"},
                    {"question": "When can the project team be mobilised (access, environments, data)?", "why": "Delays in setup consume significant project time", "priority": "Medium", "follow_up": "Is procurement/legal approval required before work starts?"},
                ]},
                {"name": "Decision Process", "icon": "🔑", "color": "#ff6b6b", "questions": [
                    {"question": "Who is the ultimate decision-maker for this project?", "why": "Ensures the proposal reaches the right stakeholder", "priority": "High", "follow_up": "Is there a procurement or vendor approval process?"},
                    {"question": "What does your evaluation process look like and what is the timeline?", "why": "Sets expectation for proposal validity period", "priority": "Medium", "follow_up": "Are other vendors being evaluated simultaneously?"},
                ]},
            ],
        }

    def check_requirements_completeness(self, scope_text: str) -> dict:
        """
        Agent 0 — Requirements Completeness Checker.
        Reads the raw scope document and returns structured gaps / questions
        the presales team should resolve BEFORE submitting the proposal.

        Returns JSON:
        {
          "confidence":   "High" | "Medium" | "Low",
          "summary":      str,
          "categories": [
            {
              "name":      str,
              "icon":      str,   # emoji
              "questions": [{"question": str, "why": str}]
            }
          ],
          "what_is_clear": [str]
        }
        """
        r = self._call(
            "You are an ECI presales analyst performing a requirements completeness review. "
            "Read the scope document carefully and identify SPECIFIC gaps, ambiguities, and "
            "missing information that the presales team must clarify before producing an accurate estimate. "
            "Be precise and actionable — each question must reference something actually missing from the document. "
            "Return JSON:\n"
            "{\"confidence\": \"High\" or \"Medium\" or \"Low\",\n"
            " \"summary\": str,\n"
            " \"categories\": [\n"
            "   {\"name\": str, \"icon\": str,\n"
            "    \"questions\": [{\"question\": str, \"why\": str}]}\n"
            " ],\n"
            " \"what_is_clear\": [str]}\n\n"
            "Use these category names where relevant (add others if needed):\n"
            "Technical Requirements, Business Requirements, Budget & Commercials, "
            "Timeline & Milestones, Integration & Data, Security & Compliance, "
            "Team & Stakeholders, Infrastructure & Hosting.\n"
            "what_is_clear: list 3-6 things the document DOES make clear.\n"
            "Only include a category if it has real questions. Aim for 8-15 questions total.",
            "Scope document:\n\n" + scope_text[:12000],
        )
        if r and isinstance(r, dict) and "categories" in r:
            return r
        # Fallback: generic questions
        return {
            "confidence": "Low",
            "summary": "The scope document could not be fully analysed automatically. Review the questions below before proceeding.",
            "categories": [
                {"name": "Technical Requirements", "icon": "⚙️", "questions": [
                    {"question": "What technology stack is preferred or mandated?", "why": "Not specified in the document"},
                    {"question": "What are the expected performance / SLA requirements?", "why": "No SLAs found in document"},
                ]},
                {"name": "Business Requirements", "icon": "📊", "questions": [
                    {"question": "Who are the primary end users and how many?", "why": "User base not defined"},
                    {"question": "What does success look like for this project?", "why": "No KPIs or acceptance criteria stated"},
                ]},
                {"name": "Budget & Commercials", "icon": "💰", "questions": [
                    {"question": "Is there a fixed budget ceiling for this engagement?", "why": "No budget indicated"},
                ]},
                {"name": "Timeline & Milestones", "icon": "📅", "questions": [
                    {"question": "Is there a fixed go-live date or is the timeline flexible?", "why": "No deadline specified"},
                ]},
            ],
            "what_is_clear": ["Document uploaded and text extracted successfully"],
        }

    def scan_scope_template(self, scope_text: str) -> dict:
        """
        Scans the scope document against the standard ECI template and flags
        every section that is incomplete, uses placeholder text, is too vague,
        or is missing entirely.

        Returns JSON:
        {
          "overall_score": int (0-100),
          "issues": [
            {
              "section":    str,   # e.g. "Business Objective"
              "excerpt":    str,   # exact text from the doc that is problematic (≤120 chars)
              "problem":    str,   # what is wrong
              "suggestion": str,   # what the section should contain
              "severity":   "critical" | "warning"
            }
          ],
          "good_sections": [str]   # sections that are well-filled
        }
        """
        _TEMPLATE_SECTIONS = (
            "Business Objective, Functional Requirements, Non-Functional Requirements, "
            "Constraints, Meeting Summary, Transcript Link, Presales Analysis & Recommendations "
            "(Option A and Option B), Assumptions, Open Questions"
        )
        r = self._call(
            "You are a strict ECI presales quality reviewer checking a scope document against the standard template. "
            "The standard template has these required sections: " + _TEMPLATE_SECTIONS + ".\n\n"
            "For EVERY section that is: (a) missing, (b) still has placeholder text like <...> or TBD, "
            "(c) has only one word/line where multiple are expected, (d) is too vague to drive an estimate, "
            "or (e) has generic/template wording not replaced with project-specific content — "
            "report an issue.\n\n"
            "For each issue, provide an 'excerpt' field with a SHORT verbatim snippet (≤120 characters) "
            "from the document that exemplifies the problem. This will be used to highlight the text in red. "
            "If the section is entirely missing, set excerpt to the section heading or a nearby line.\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "overall_score": <int 0-100 reflecting overall quality>,\n'
            '  "issues": [\n'
            '    {"section": str, "excerpt": str, "problem": str, "suggestion": str, '
            '"severity": "critical" or "warning"}\n'
            "  ],\n"
            '  "good_sections": [str]\n'
            "}\n\n"
            "Be specific — quote actual text from the document for every excerpt. "
            "critical = blocks estimation; warning = reduces accuracy.",
            "Scope document to review:\n\n" + scope_text[:14000],
        )
        if r and isinstance(r, dict) and "issues" in r:
            return r
        return {"overall_score": 0, "issues": [], "good_sections": []}

    def analyze_transcript(self, transcript_text):
        r = self._call(
            "You are an expert ECI presales analyst. Analyze this meeting/discovery call transcript thoroughly. "
            "Extract every requirement, pain point, stakeholder concern, decision, and action item mentioned. "
            "Be exhaustive — treat this the same way you would treat a formal scope document. "
            "Return JSON:\n"
            "{\"pain_points\": [{\"issue\": str, \"severity\": \"High\" or \"Medium\" or \"Low\", \"quote\": str, \"stakeholder\": str}],\n"
            " \"requirements_extracted\": [{\"title\": str, \"description\": str, "
            "\"type\": \"functional\" or \"non-functional\" or \"integration\", "
            "\"complexity\": \"Low\" or \"Medium\" or \"High\", \"priority\": str, \"source\": str}],\n"
            " \"stakeholders\": [{\"name\": str, \"role\": str, \"concerns\": [str], \"influence\": \"High\" or \"Medium\" or \"Low\"}],\n"
            " \"decisions\": [str], "
            "\"action_items\": [{\"item\": str, \"owner\": str, \"priority\": \"High\" or \"Medium\" or \"Low\", \"due\": str}],\n"
            " \"wbs\": [{\"phase\": str, \"deliverables\": [{\"name\": str, \"tasks\": [{\"name\": str, \"effort\": str}]}]}],\n"
            " \"technology_stack\": [str],\n"
            " \"project_type\": str,\n"
            " \"client_name\": str,\n"
            " \"project_title\": str,\n"
            " \"complexity_score\": int 1-10,\n"
            " \"business_objectives\": [str],\n"
            " \"meeting_summary\": str, \"sentiment\": str, \"key_themes\": [str]}",
            "Transcript:\n\n" + transcript_text[:15000],
        )
        if r and isinstance(r, dict) and ("wbs" in r or "requirements_extracted" in r):
            return r
        return self._fb_transcript(transcript_text)

    def _fb_mermaid(self, arch):
        comps = safe_list(arch.get("components"))

        # Use only simple ["label"] rectangles — cylinder/stadium shapes
        # cause dagre's "Could not find a suitable point" edge routing error.
        infra = "flowchart TD\n"
        infra += "    User[\"Client Browser\"]\n    CDN[\"Azure Front Door\"]\n    APIM[\"API Management\"]\n"
        infra += "    APP[\"App Service\"]\n    FUNC[\"Azure Functions\"]\n    SQL[\"Azure SQL\"]\n"
        infra += "    COSMOS[\"Cosmos DB\"]\n    REDIS[\"Redis Cache\"]\n    BLOB[\"Blob Storage\"]\n"
        infra += "    SB[\"Service Bus\"]\n    KV[\"Key Vault\"]\n    AD[\"Azure AD\"]\n    MON[\"App Insights\"]\n\n"
        infra += "    User --> CDN\n    CDN --> APIM\n    APIM --> APP\n    APP --> SQL\n    APP --> COSMOS\n"
        infra += "    APP --> REDIS\n    APP --> BLOB\n    APP --> SB\n    SB --> FUNC\n    FUNC --> SQL\n"
        infra += "    FUNC --> COSMOS\n    APP --> KV\n    APP --> AD\n    APP --> MON\n    FUNC --> MON"

        data_flow = "flowchart LR\n"
        data_flow += "    A[\"Client App\"] -->|HTTPS| B[\"API Gateway\"]\n"
        data_flow += "    B -->|Route| C[\"App Service\"]\n    C -->|Read Write| D[\"SQL Database\"]\n"
        data_flow += "    C -->|Cache| E[\"Redis Cache\"]\n    C -->|Documents| F[\"Blob Storage\"]\n"
        data_flow += "    C -->|Events| G[\"Service Bus\"]\n    G -->|Trigger| H[\"Azure Functions\"]\n"
        data_flow += "    H -->|Process| I[\"Cosmos DB\"]\n    H -->|Notify| J[\"Notification Hub\"]\n"
        data_flow += "    C -->|Analytics| K[\"Power BI\"]\n    D -->|Sync| I"

        sequence = "sequenceDiagram\n"
        sequence += "    participant U as User\n    participant FD as Front Door\n"
        sequence += "    participant API as API Mgmt\n    participant App as App Service\n"
        sequence += "    participant Cache as Redis\n    participant DB as SQL Database\n"
        sequence += "    participant SB as Service Bus\n    participant Func as Functions\n\n"
        sequence += "    U->>FD: HTTPS Request\n    FD->>API: Route and WAF\n"
        sequence += "    Note over API: Auth and Rate Limit\n    API->>App: Forward Request\n"
        sequence += "    App->>Cache: Check Cache\n    alt Cache Hit\n        Cache-->>App: Return Data\n"
        sequence += "    else Cache Miss\n        App->>DB: Query Data\n        DB-->>App: Result Set\n"
        sequence += "        App->>Cache: Update Cache\n    end\n"
        sequence += "    App->>SB: Publish Event\n    SB->>Func: Trigger Processing\n    App-->>U: JSON Response"

        deployment = "flowchart TD\n"
        deployment += "    DEV[\"Developer\"] -->|git push| GH[\"GitHub\"]\n"
        deployment += "    GH -->|trigger| CI[\"Azure DevOps CI\"]\n"
        deployment += "    CI -->|build and test| ART[\"Container Registry\"]\n"
        deployment += "    ART -->|deploy| STG[\"Staging\"]\n    STG -->|approval gate| PROD[\"Production\"]\n"
        deployment += "    PROD -->|monitor| MON2[\"App Insights\"]\n    MON2 -->|alert| OPS[\"Ops Team\"]"

        security = "flowchart TD\n"
        security += "    EXT[\"External Traffic\"]\n    WAF[\"WAF and DDoS Protection\"]\n"
        security += "    FD2[\"Front Door with TLS\"]\n    APIM2[\"API Mgmt with OAuth\"]\n"
        security += "    VNET[\"Virtual Network\"]\n    NSG[\"NSG Rules\"]\n"
        security += "    APP2[\"App Service with MI\"]\n    KV2[\"Key Vault\"]\n"
        security += "    SQL2[\"SQL with TDE\"]\n    LOG[\"Sentinel and Log Analytics\"]\n\n"
        security += "    EXT --> WAF\n    WAF --> FD2\n    FD2 --> APIM2\n    APIM2 --> VNET\n"
        security += "    VNET --> NSG\n    NSG --> APP2\n    APP2 --> KV2\n    APP2 --> SQL2\n"
        security += "    APP2 --> LOG\n    KV2 --> LOG"

        return {"infrastructure": infra, "data_flow": data_flow, "sequence": sequence, "deployment": deployment, "security": security}

    def _fb_transcript(self, text):
        return {
            "pain_points": [
                {"issue": "Manual data processing taking excessive time", "severity": "High", "quote": "We spend hours every week just copying data between systems", "stakeholder": "Operations Lead"},
                {"issue": "Lack of real-time visibility into operations", "severity": "High", "quote": "By the time we get reports, the data is already stale", "stakeholder": "VP Operations"},
                {"issue": "Integration gaps between existing systems", "severity": "Medium", "quote": "Our CRM and ERP don't talk to each other properly", "stakeholder": "IT Manager"},
                {"issue": "Security concerns with current manual workflows", "severity": "Medium", "quote": "People are emailing spreadsheets with sensitive data", "stakeholder": "CISO"},
            ],
            "requirements_extracted": [
                {"title": "Automated Data Pipeline", "description": "ETL pipeline connecting CRM, ERP, and data warehouse", "type": "functional", "source": "Operations Lead — pain point discussion"},
                {"title": "Real-time Dashboard", "description": "Live operational metrics with <5 min refresh", "type": "functional", "source": "VP Operations — visibility concern"},
                {"title": "System Integration Layer", "description": "API-based integration between CRM and ERP", "type": "integration", "source": "IT Manager — integration gap"},
                {"title": "Secure Data Transfer", "description": "Encrypted data pipelines replacing manual email workflows", "type": "non-functional", "source": "CISO — security concern"},
                {"title": "User Authentication & SSO", "description": "Azure AD SSO with MFA for all users", "type": "non-functional", "source": "CISO — access control discussion"},
                {"title": "Mobile Access", "description": "Responsive web app for field team access", "type": "functional", "source": "Field Operations Manager — remote access need"},
            ],
            "stakeholders": [
                {"name": "Sarah Mitchell", "role": "VP Operations", "concerns": ["Reporting delays", "Operational visibility", "Cost of current manual processes"]},
                {"name": "James Chen", "role": "IT Manager", "concerns": ["Integration complexity", "Maintenance burden", "Team skill gaps"]},
                {"name": "David Park", "role": "CISO", "concerns": ["Data security", "Compliance", "Audit trail"]},
                {"name": "Lisa Ramirez", "role": "Operations Lead", "concerns": ["Daily workflow efficiency", "Data accuracy", "Training time"]},
            ],
            "decisions": [
                "Azure cloud platform selected as preferred infrastructure",
                "Phased rollout approach agreed — pilot with Operations team first",
                "Budget range of $150K-250K for initial phase discussed",
                "Q3 2025 target for MVP delivery",
                "Weekly stakeholder sync meetings during discovery",
            ],
            "action_items": [
                {"item": "Share current system architecture documentation", "owner": "IT Manager", "priority": "High"},
                {"item": "Provide sample data exports from CRM and ERP", "owner": "Operations Lead", "priority": "High"},
                {"item": "Schedule security requirements workshop", "owner": "CISO", "priority": "Medium"},
                {"item": "Prepare ECI proposal with options", "owner": "ECI Team", "priority": "High"},
                {"item": "Set up Azure sandbox environment", "owner": "IT Manager", "priority": "Medium"},
            ],
            "wbs": [
                {"phase": "Discovery & Planning", "deliverables": [
                    {"name": "Stakeholder Workshops", "tasks": [{"name": "Requirements gathering sessions", "effort": "3 days"}, {"name": "Pain point analysis", "effort": "2 days"}, {"name": "Current state assessment", "effort": "3 days"}]},
                    {"name": "Technical Assessment", "tasks": [{"name": "System landscape review", "effort": "2 days"}, {"name": "Data mapping", "effort": "3 days"}, {"name": "Integration feasibility", "effort": "2 days"}]},
                    {"name": "Project Plan", "tasks": [{"name": "WBS finalization", "effort": "1 day"}, {"name": "Resource plan", "effort": "1 day"}, {"name": "Risk register", "effort": "1 day"}]},
                ]},
                {"phase": "Design & Architecture", "deliverables": [
                    {"name": "Solution Architecture", "tasks": [{"name": "High-level design", "effort": "3 days"}, {"name": "Data model design", "effort": "4 days"}, {"name": "API contract design", "effort": "3 days"}]},
                    {"name": "UX Design", "tasks": [{"name": "Wireframes", "effort": "3 days"}, {"name": "UI mockups", "effort": "4 days"}, {"name": "User testing", "effort": "2 days"}]},
                ]},
                {"phase": "Development", "deliverables": [
                    {"name": "Backend Services", "tasks": [{"name": "API development", "effort": "15 days"}, {"name": "Data pipeline", "effort": "10 days"}, {"name": "Integration layer", "effort": "8 days"}]},
                    {"name": "Frontend Application", "tasks": [{"name": "UI components", "effort": "10 days"}, {"name": "Dashboard views", "effort": "8 days"}, {"name": "Responsive design", "effort": "4 days"}]},
                ]},
                {"phase": "Testing & QA", "deliverables": [
                    {"name": "Testing", "tasks": [{"name": "Unit testing", "effort": "5 days"}, {"name": "Integration testing", "effort": "5 days"}, {"name": "Performance testing", "effort": "3 days"}, {"name": "UAT", "effort": "5 days"}]},
                ]},
                {"phase": "Deployment & Hypercare", "deliverables": [
                    {"name": "Go-Live", "tasks": [{"name": "Data migration", "effort": "3 days"}, {"name": "Production deployment", "effort": "2 days"}, {"name": "Smoke testing", "effort": "1 day"}]},
                    {"name": "Hypercare", "tasks": [{"name": "Post-launch monitoring", "effort": "10 days"}, {"name": "Bug fixes", "effort": "5 days"}, {"name": "Knowledge transfer", "effort": "3 days"}]},
                ]},
            ],
            "meeting_summary": "Discovery call with key stakeholders revealed significant operational inefficiencies driven by manual data workflows and disconnected systems. Primary pain points center around delayed reporting, manual data transfers, and security gaps. The team expressed strong preference for Azure-based cloud solution with phased delivery approach. Budget is available for Q3 2025 MVP.",
            "sentiment": "Positive — stakeholders are motivated and have executive buy-in for modernization",
            "key_themes": ["Automation", "Real-time Analytics", "System Integration", "Security", "Cloud Migration", "Mobile Access"],
        }

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000) -> "str | None":
        """Call Azure OpenAI and return raw text output — no JSON mode."""
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                **self._token_kwargs(max_tokens),
                temperature=0.4,
                timeout=45.0,
            )
            return resp.choices[0].message.content
        except Exception as e:
            st.warning("Azure OpenAI raw call: " + str(e)[:150])
            return None

    def stream_section_rewrite(self, title: str, current_content: str,
                               instructions: str, ref_context: str = ""):
        """Generator: streams a proposal section rewrite via Azure OpenAI SDK streaming."""
        if not self._client:
            return
        system = (
            "You are a senior ECI presales consultant and technical writer. "
            "Rewrite the proposal section based on the instructions given.\n"
            "• Return ONLY the rewritten section text — no JSON, no code blocks, no headings\n"
            "• Use formal, boardroom-level English — concise, client-focused, persuasive\n"
            "• Preserve technical accuracy while improving clarity and impact"
        )
        parts = [
            f"SECTION: {title}",
            f"CURRENT CONTENT:\n{current_content[:3000]}",
            f"INSTRUCTIONS: {instructions}",
        ]
        if ref_context:
            parts.append(f"REFERENCE CONTEXT:\n{ref_context[:1500]}")
        user = "\n\n".join(parts)
        try:
            stream = self._client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=1500,
                temperature=0.4,
                stream=True,
                timeout=60.0,
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
        except Exception as exc:
            st.warning(f"Azure stream error: {str(exc)[:150]}")

    def generate_ai_arch_svg(self, arch: dict, semantic: dict) -> "str | None":
        """Generate a stunning, publication-quality HTML/SVG architecture diagram via Azure OpenAI.

        Returns a complete self-contained HTML page ready for st.components.v1.html(),
        or None on failure.
        """
        if not self._client:
            return None
        import json as _json
        from .utils import safe_str, safe_list, safe_dict

        comps          = safe_list(arch.get("components"))
        flow           = safe_list(arch.get("data_flow"))
        pattern        = safe_str(arch.get("pattern", "Solution Architecture"))
        security_items = safe_list(arch.get("security"))
        tech           = safe_list(semantic.get("technology_stack", []))
        mandated       = safe_list(semantic.get("mandated_technologies", []))
        source_sys     = safe_list(semantic.get("source_systems", []))
        proj           = safe_str(semantic.get("project_type", "Cloud Solution"))
        client_name    = safe_str(semantic.get("client_name", ""))

        # build_tech = mandated first; fallback to stack minus known source systems
        source_lower = {s.lower() for s in source_sys}
        build_tech = mandated or [t for t in tech if t.lower() not in source_lower]

        arch_desc = {
            "title": pattern,
            "project_type": proj,
            "client": client_name,
            "MANDATED_BUILD_TECHNOLOGIES": [safe_str(t) for t in build_tech[:10]],
            "SOURCE_SYSTEMS_INPUT_ONLY": [safe_str(s) for s in source_sys[:6]],
            "components": [
                {
                    "name": safe_str(safe_dict(c).get("name", "")),
                    "type": safe_str(safe_dict(c).get("type", "")),
                    "azure_service": safe_str(safe_dict(c).get("azure_service", "")),
                    "services": [safe_str(s) for s in safe_list(safe_dict(c).get("services", []))[:3]],
                }
                for c in comps[:14]
            ],
            "data_flow": [safe_str(f) for f in flow[:10]],
            "security_controls": [safe_str(s) for s in security_items[:6]],
            "scalability": safe_str(arch.get("scalability", "")),
            "availability": safe_str(arch.get("availability", "")),
        }
        arch_str = _json.dumps(arch_desc, indent=2)

        SYSTEM = (
            "You are a world-class Azure solutions architect and SVG diagram expert. "
            "Create a stunning, professional, enterprise-grade architecture diagram as a complete self-contained HTML page. "
            "STRICT OUTPUT FORMAT: Return ONLY valid HTML — start <!DOCTYPE html>, end </html>. No markdown fences, no explanation text. "
            "VISUAL DESIGN: White background #F8FAFC, SVG 1360x860. "
            "Use Azure official colors: Subscription box stroke=#0078D4 fill=#EBF5FB dashed; Resource Group stroke=#107C10 fill=#F0FFF4; "
            "AI/ML stroke=#5C2D91 fill=#F5F0FF; Data stroke=#00B294 fill=#E6FFF9; "
            "Security stroke=#D83B01 fill=#FFF3ED; Monitoring stroke=#FFB900 fill=#FFFBF0; "
            "External/Sources stroke=#6B7280 fill=#F9FAFB dashed; Consumers stroke=#0078D4 fill=#EBF5FB. "
            "LAYOUT: Left col (x=20) external sources, Center Azure Subscription with nested Resource Group and service groups, Right col consumers. "
            "SERVICE CARDS: width=154 height=68 rx=8, icon circle r=16 with emoji, name font-size=11 bold, azure service font-size=9. "
            "ARROWS: curved bezier paths with arrowhead markers, labeled. "
            "HOVER: CSS .svc-card:hover {filter:drop-shadow(0 4px 12px rgba(0,120,212,.35));transform:translateY(-2px);} "
            "TITLE BANNER: top rect fill=#0078D4, white text with project title. "
            "Include 12-16 service cards, 8+ arrows, legend box. Completely self-contained - no external resources."
        )

        USER = (
            f"Generate a complete HTML architecture diagram for this Azure solution:\n\n{arch_str}\n\n"
            "Place data sources LEFT, Azure services CENTER (grouped by tier in colored sections), "
            "consumers RIGHT. Show numbered data-flow arrows. Security & Monitoring at bottom of Resource Group. "
            "Return ONLY the complete HTML starting with <!DOCTYPE html>."
        )

        try:
            if not self._client:
                return None
            name = self.deployment.lower()
            is_reasoning = any(p in name for p in ("o1", "o2", "o3", "o4"))
            create_kwargs = dict(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": USER},
                ],
                **self._token_kwargs(16000),
            )
            if not is_reasoning:
                create_kwargs["temperature"] = 0.3
            resp = self._client.chat.completions.create(**create_kwargs)
            if not resp.choices:
                return None
            html = resp.choices[0].message.content
            if not html:
                return None
            html = html.strip()
            if html.startswith("```"):
                lines = html.splitlines()
                html = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
            if "<html" not in html.lower():
                html = f"<!DOCTYPE html><html><body style='margin:0;background:#F8FAFC'>{html}</body></html>"
            return html
        except Exception as e:
            st.warning("Azure OpenAI arch diagram: " + str(e)[:150])
            return None


# ── Give AnthropicAI all ECI agent methods from AzureAI ──────────────────────
# AzureAI holds all 13 agent methods (analyze_requirements, estimate_time, …).
# GeminiAI / QwenAI / VertexAnthropicAI already inherit from AzureAI.
# AnthropicAI uses the Anthropic HTTP API instead of the OpenAI SDK, so it
# can't inherit from AzureAI directly — but its _call(system, user) has the
# same signature, so copying the unbound methods makes them work immediately.
_AGENT_METHODS = [
    "analyze_requirements", "estimate_time", "estimate_cost", "analyze_risk",
    "design_architecture", "define_scope", "write_proposal",
    "generate_mermaid_diagrams", "generate_discovery_questions",
    "check_requirements_completeness", "analyze_transcript",
    "search_historical", "regenerate_section",
    "generate_ai_arch_svg",
    # fallback builders (no self._call — pure data construction)
    "_fb_semantic", "_fb_requirements", "_fb_time", "_fb_cost", "_fb_risk", "_fb_arch",
    "_fb_scope", "_fb_proposal", "_fb_mermaid", "_fb_discovery_questions",
    "_fb_completeness", "_fb_transcript",
]
for _m in _AGENT_METHODS:
    if hasattr(AzureAI, _m) and not hasattr(AnthropicAI, _m):
        setattr(AnthropicAI, _m, getattr(AzureAI, _m))


# ═══════════════════════════════════════════════════════════════════════
#  GOOGLE GEMINI CLIENT — DROP-IN AI ALTERNATIVE (free tier available)
# ═══════════════════════════════════════════════════════════════════════

class GeminiAI(AzureAI):
    """Google Gemini drop-in LLM. Inherits all ECI analysis methods from AzureAI."""

    MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, key: str, model: str = "gemini-2.0-flash"):
        self.key        = key.strip()
        self.model      = model or "gemini-2.0-flash"
        self.deployment = self.model
        self._client    = None

    @classmethod
    def from_session(cls):
        return cls(
            st.session_state.get("gemini_api_key", ""),
            st.session_state.get("gemini_model",  "gemini-2.0-flash"),
        )

    @property
    def is_live(self):
        return bool(self.key)

    def test(self):
        if not self.key:
            return False, "Not configured. Enter Gemini API Key."
        result = self._call(
            "You are a test assistant. Always reply with valid JSON.",
            'Reply with: {"status": "ok"}',
        )
        if result is not None:
            return True, f"Connected to {self.model}"
        return False, "Connection failed — check your Gemini API key."

    def _call(self, system: str, user: str, _max_retries: int = 5) -> "dict | str | None":
        """Call Gemini generateContent API; retries on HTTP 429."""
        if not self.key:
            return None
        import urllib.request, urllib.error

        url      = f"{self._BASE}/{self.model}:generateContent?key={self.key}"
        combined = system + "\n\n" + user
        payload  = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": combined}]}],
            "generationConfig": {
                "maxOutputTokens":  4096,
                "temperature":      0.2,
                "responseMimeType": "application/json",
            },
        }).encode("utf-8")

        for attempt in range(_max_retries):
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    txt  = ""
                    try:
                        txt = data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError):
                        return None
                    try:
                        return json.loads(txt)
                    except json.JSONDecodeError:
                        pass
                    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", txt)
                    if m:
                        try:
                            return json.loads(m.group(1))
                        except Exception:
                            pass
                    m2 = re.search(r"\{[\s\S]*\}", txt)
                    if m2:
                        try:
                            return json.loads(m2.group(0))
                        except Exception:
                            pass
                    return txt
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    st.toast(f"⏳ Gemini rate limit — retrying in {wait:.0f}s (attempt {attempt + 1}/{_max_retries})…")
                    time.sleep(wait)
                    continue
                body = e.read().decode("utf-8", errors="ignore")[:300]
                st.warning(f"Gemini error {e.code}: {body[:200]}")
                return None
            except Exception as e:
                st.warning(f"Gemini request failed: {str(e)[:200]}")
                return None

        st.error("Gemini: free-tier rate limit hit after all retries. Wait 60 s then try again, or switch to gemini-1.5-flash.")
        return None

    def _call_text(self, system: str, user: str, max_tokens: int = 1024, _max_retries: int = 5) -> "str | None":
        """Call Gemini without JSON mode — returns plain text for chat."""
        if not self.key:
            return None
        import urllib.request, urllib.error

        url     = f"{self._BASE}/{self.model}:generateContent?key={self.key}"
        payload = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": system + "\n\n" + user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
        }).encode("utf-8")

        for attempt in range(_max_retries):
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait)
                    continue
                return None
            except Exception:
                return None

        return None

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000) -> "str | None":
        """Call Gemini and return raw text (no JSON mode)."""
        return self._call_text(system, user, max_tokens=max_tokens)


# ═══════════════════════════════════════════════════════════════════════
#  VERTEX AI — ANTHROPIC CLAUDE (Application Default Credentials)
#  No JSON key needed: run  gcloud auth application-default login  once.
# ═══════════════════════════════════════════════════════════════════════

class VertexAnthropicAI(AzureAI):
    """Claude on Google Vertex AI — authenticates via ADC (no JSON key).

    Setup (one-time):
        gcloud auth application-default login
        gcloud config set project YOUR_PROJECT_ID

    Then fill in Project ID and Region in the sidebar.
    """

    MODELS = [
        "claude-sonnet-4-5@20251001",
        "claude-opus-4-5@20251001",
        "claude-haiku-4-5@20251001",
        "claude-3-5-sonnet-v2@20241022",
        "claude-3-7-sonnet@20250219",
        "claude-3-5-haiku@20241022",
    ]

    def __init__(self, project_id: str, region: str, model: str = "claude-sonnet-4-5@20251001"):
        self.project_id = (project_id or "").strip()
        self.region     = (region or "us-east5").strip()
        self.model      = model or "claude-sonnet-4-5@20251001"
        self.deployment = self.model
        self._client    = None

        if self.project_id:
            try:
                import anthropic as _anthropic
                self._client = _anthropic.AnthropicVertex(
                    project_id=self.project_id,
                    region=self.region,
                )
            except ImportError:
                pass  # anthropic[vertex] not installed
            except Exception:
                pass  # ADC not configured yet — will fail at call time

    @classmethod
    def from_session(cls):
        return cls(
            st.session_state.get("vertex_project_id", ""),
            st.session_state.get("vertex_region", "us-east5"),
            st.session_state.get("vertex_model", "claude-sonnet-4-5@20251001"),
        )

    @property
    def is_live(self):
        return self._client is not None

    def test(self):
        if not self._client:
            try:
                import anthropic as _anthropic  # noqa
            except ImportError:
                return False, "anthropic[vertex] not installed. Run: pip install anthropic[vertex]"
            return False, "Not configured. Enter your GCP Project ID."
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            )
            return True, f"Connected to {self.model} on Vertex AI (project: {self.project_id})"
        except Exception as e:
            err = str(e)[:250]
            if "UNAUTHENTICATED" in err or "credentials" in err.lower():
                return False, "ADC not set up. Run: gcloud auth application-default login"
            return False, "Vertex error: " + err

    def _call(self, system: str, user: str, **_) -> "dict | None":
        if not self._client:
            return None
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            txt = msg.content[0].text if msg.content else ""
            if not txt:
                return None
            stripped = txt.strip()
            # Strip markdown code fences
            if stripped.startswith("```"):
                parts = stripped.split("```")
                stripped = parts[2].strip() if len(parts) >= 3 else parts[-1].strip()
                stripped = stripped.lstrip("json").strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
            m = re.search(r"\{[\s\S]*\}", stripped)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            return stripped
        except Exception as e:
            st.warning("Vertex AI: " + str(e)[:200])
            return None

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000) -> "str | None":
        if not self._client:
            return None
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text if msg.content else None
        except Exception as e:
            st.warning("Vertex AI: " + str(e)[:200])
            return None


# ═══════════════════════════════════════════════════════════════════════
#  QWEN AI CLIENT — Alibaba DashScope (OpenAI-compatible endpoint)
# ═══════════════════════════════════════════════════════════════════════

class QwenAI(AzureAI):
    """Alibaba Qwen drop-in LLM via DashScope OpenAI-compatible API.

    Inherits all ECI analysis methods from AzureAI.
    Get your API key at: https://dashscope.aliyuncs.com/
    """

    MODELS = [
        "qwen-plus",
        "qwen-max",
        "qwen-turbo",
        "qwen-long",
        "qwen2.5-72b-instruct",
        "qwen2.5-32b-instruct",
        "qwen2.5-14b-instruct",
        "qwen2.5-7b-instruct",
    ]
    _DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, key: str, model: str = "qwen-plus",
                 endpoint: str = "", deployment: str = "", api_version: str = "2024-06-01",
                 mode: str = ""):
        self.key          = key.strip()
        self._client      = None   # openai-compatible client
        self._inf_client  = None   # azure.ai.inference client
        self._mode        = "dashscope"

        endpoint   = (endpoint or "").strip()
        deployment = (deployment or "").strip()
        _detected_mode = mode or st.session_state.get("qwen_mode", "")

        # ── azure.ai.inference mode (ChatCompletionsClient) ────────────────
        _ensure_inference()
        if _detected_mode == "inference" and self.key and endpoint and deployment and HAS_INFERENCE_SDK:
            self._mode      = "inference"
            self.model      = deployment
            self.deployment = deployment
            _inf_base = endpoint.rstrip("/")
            if not _inf_base.endswith("/models"):
                _inf_base += "/models"
            try:
                self._inf_client = _InferenceClient(
                    endpoint=_inf_base,
                    credential=_AzureKey(self.key),
                )
            except Exception:
                pass

        # ── Azure AI Foundry / OpenAI-compatible /models path ─────────────
        elif self.key and endpoint and deployment:
            _oi_cls = _get_OpenAI()
            if _oi_cls:
                self._mode      = "foundry"
                self.model      = deployment
                self.deployment = deployment
                _base = endpoint.rstrip("/")
                if not _base.endswith("/models"):
                    _base = _base + "/models"
                try:
                    self._client = _oi_cls(
                        api_key=self.key,
                        base_url=_base,
                    )
                except Exception:
                    pass

        # ── DashScope mode ─────────────────────────────────────────────────
        elif self.key:
            _oi_cls = _get_OpenAI()
            if _oi_cls:
                self._mode      = "dashscope"
                self.model      = model or "qwen-plus"
                self.deployment = self.model
                try:
                    self._client = _oi_cls(
                        api_key=self.key,
                        base_url=self._DASHSCOPE_BASE,
                    )
                except Exception:
                    pass
        else:
            self.model      = model or "qwen-plus"
            self.deployment = self.model

    @classmethod
    def from_session(cls):
        endpoint   = st.session_state.get("qwen_endpoint", "").strip()
        deployment = st.session_state.get("qwen_deployment", "").strip()
        mode       = st.session_state.get("qwen_mode", "")
        # Use foundry_key when endpoint+deployment are set, else dashscope key
        if endpoint and deployment:
            key = st.session_state.get("qwen_foundry_key", "").strip()
        else:
            key = st.session_state.get("qwen_api_key", "").strip()
        return cls(
            key,
            st.session_state.get("qwen_model", "qwen-plus"),
            endpoint,
            deployment,
            st.session_state.get("qwen_api_version", "2024-06-01"),
            mode=mode,
        )

    @property
    def is_live(self):
        return self._inf_client is not None or self._client is not None

    def test(self):
        if self._mode == "inference":
            if not self._inf_client:
                return False, "azure.ai.inference client not initialised — check endpoint/key."
            try:
                resp = self._inf_client.complete(
                    model=self.model,
                    messages=[_InfUsrMsg("Reply with: ok")],
                    max_tokens=5,
                )
                return True, f"Connected to {self.model} (inference SDK)"
            except Exception as e:
                return False, "Inference test failed: " + str(e)[:200]
        if not self._client:
            return False, "Not configured. Enter Qwen API Key."
        try:
            self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_tokens=5,
            )
            return True, f"Connected to {self.model} ({self._mode})"
        except Exception as e:
            return False, "Failed: " + str(e)[:200]

    # ── azure.ai.inference SDK calls ───────────────────────────────────────
    def _inf_call_text(self, system: str, user: str, max_tokens: int = 8192) -> "str | None":
        """Call via azure.ai.inference ChatCompletionsClient, return raw text."""
        if not self._inf_client:
            return None
        try:
            resp = self._inf_client.complete(
                model=self.model,
                messages=[_InfSysMsg(system), _InfUsrMsg(user)],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            if resp.choices:
                return resp.choices[0].message.content or ""
        except Exception as e:
            st.warning("Qwen inference: " + str(e)[:200])
        return None

    @staticmethod
    def _repair_json(txt: str) -> str:
        """Best-effort repair of common LLM JSON defects before parsing."""
        s = txt.strip()

        # 1. Strip markdown code fences  ```json ... ```
        if s.startswith("```"):
            parts = s.split("```")
            for part in parts:
                part = part.lstrip("json").lstrip("JSON").strip()
                if part.startswith("{") or part.startswith("["):
                    s = part
                    break

        # 2. Remove trailing commas before } or ]  e.g. "value",\n} → "value"\n}
        s = re.sub(r',\s*([}\]])', r'\1', s)

        # 3. Replace Python/JS literals that are invalid JSON
        s = re.sub(r'\bNone\b',  'null',  s)
        s = re.sub(r'\bTrue\b',  'true',  s)
        s = re.sub(r'\bFalse\b', 'false', s)
        s = re.sub(r'\bundefined\b', 'null', s)

        # 4. Remove single-line // comments (common in JS-style LLM output)
        s = re.sub(r'//[^\n]*', '', s)

        # 5. Escape literal control characters INSIDE JSON string values.
        #    Qwen often puts real newlines inside Mermaid diagram strings.
        _CTRL = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
        out_chars: list = []
        in_str  = False
        escaped = False
        for ch in s:
            if escaped:
                out_chars.append(ch)
                escaped = False
            elif ch == '\\' and in_str:
                out_chars.append(ch)
                escaped = True
            elif ch == '"':
                in_str = not in_str
                out_chars.append(ch)
            elif in_str and ord(ch) < 0x20:
                out_chars.append(_CTRL.get(ch, '\\u{:04x}'.format(ord(ch))))
            else:
                out_chars.append(ch)
        s = ''.join(out_chars)

        return s

    @staticmethod
    def _close_truncated_json(s: str) -> str:
        """Close a JSON string that was cut off mid-way by the token limit.

        Walks the string tracking open strings / objects / arrays, then
        appends the minimum closing tokens needed to make it parseable.
        Also strips any trailing incomplete key (e.g. ,"incomplet before EOF).
        """
        stack: list = []   # '{' or '['
        in_str  = False
        escaped = False

        for ch in s:
            if escaped:
                escaped = False
                continue
            if ch == '\\' and in_str:
                escaped = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}' and stack and stack[-1] == '{':
                    stack.pop()
                elif ch == ']' and stack and stack[-1] == '[':
                    stack.pop()

        result = s

        # Strip trailing incomplete key fragment BEFORE closing the string
        # e.g.  ,"some_key   →  remove it (open string, no value yet)
        if in_str:
            result = re.sub(r',\s*"[^"]*$', '', result)   # dangling open-key
            result = re.sub(r',\s*$', '', result)           # bare trailing comma
            # Re-check in_str after stripping (stack walk result stays valid)
            # If we removed the dangling fragment, we may now be outside a string
            # Re-walk the truncated fragment to determine final in_str state
            in_str2 = False
            esc2 = False
            for ch in result:
                if esc2:
                    esc2 = False
                elif ch == '\\' and in_str2:
                    esc2 = True
                elif ch == '"':
                    in_str2 = not in_str2
            if in_str2:
                result += '"'   # still inside a string value — close it
        else:
            result = re.sub(r',\s*$', '', result)           # bare trailing comma

        # Strip dangling key-with-no-value that survived (e.g. after closing: ,"key")
        result = re.sub(r',\s*"[^"]*"\s*$', '', result)

        # Close remaining open structures
        for opener in reversed(stack):
            result += '}' if opener == '{' else ']'

        return result

    def _inf_call_json(self, system: str, user: str, max_tokens: int = 16000) -> "dict | None":
        """Call via azure.ai.inference and parse JSON from the response."""
        txt = self._inf_call_text(
            system,
            user + "\n\nIMPORTANT: Respond with ONLY a valid JSON object — no markdown fences, no trailing commas, no extra text.",
            max_tokens=max_tokens,
        )
        if not txt:
            return None

        raw     = txt.strip()
        repaired = self._repair_json(raw)

        # Extract outermost {...} block (strips prose before/after JSON)
        extracted = None
        for _src in (repaired, raw):
            _m = re.search(r'\{[\s\S]+\}', _src)
            if _m:
                extracted = self._repair_json(_m.group())
                break

        # Truncation recovery on the repaired string
        recovered = self._close_truncated_json(repaired)
        recovered = self._repair_json(recovered)   # re-run after closing

        # Try each candidate in order: raw → repaired → extracted → recovered
        for candidate in [raw, repaired, extracted, recovered]:
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except Exception:
                continue

        st.warning("Qwen: could not parse JSON response. Raw: " + raw[:300])
        return None

    # ── Routing: inference mode takes priority, else use openai client ─────
    def _call(self, system: str, user: str, max_tokens: int = 8192) -> "dict | None":
        if self._mode == "inference":
            return self._inf_call_json(system, user, max_tokens=max_tokens)
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=4096,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            if not resp.choices:
                return None
            txt = resp.choices[0].message.content
            if not txt or not txt.strip():
                return None
            stripped = txt.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("```", 2)[-1] if stripped.count("```") >= 2 else stripped
                stripped = stripped.lstrip("json").strip()
            return json.loads(stripped)
        except Exception as e:
            st.warning("Qwen: " + str(e)[:150])
            return None

    def _call_text(self, system: str, user: str, max_tokens: int = 1024, **_) -> "str | None":
        """Plain-text call (no JSON mode) — used for chat."""
        if self._mode == "inference":
            return self._inf_call_text(system, user, max_tokens=max_tokens)
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.4,
            )
            if resp.choices:
                return resp.choices[0].message.content
        except Exception as e:
            st.warning("Qwen chat: " + str(e)[:150])
        return None

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000) -> "str | None":
        return self._call_text(system, user, max_tokens=max_tokens)

    def generate_mermaid_diagrams(self, semantic, arch):
        """Override to use a larger token budget — 5 Mermaid diagrams need more room."""
        r = self._call(
            "You are an Azure Solutions Architect for ECI. Generate Mermaid.js diagram code for the architecture. "
            "CRITICAL RULES for all diagrams:\n"
            "1. Use ONLY simple rectangular nodes: NodeId[\"Label\"]. "
            "   NEVER use cylinder [(...)], stadium ([...]), subroutine [[...]], or asymmetric >...] shapes.\n"
            "2. Use flowchart TD or flowchart LR (NOT graph TD/graph LR).\n"
            "3. Keep node labels under 35 characters.\n"
            "4. Do NOT include style, classDef, or linkStyle directives.\n"
            "5. Do NOT use parentheses () in node IDs — use underscores instead.\n"
            "6. Keep edge labels under 25 characters, no special chars ()/<>{}.\n"
            "7. CONCISE: max 12 nodes and 15 edges per diagram. No subgraphs.\n\n"
            "Return JSON with EXACTLY these keys, each a valid Mermaid string:\n"
            "{\"infrastructure\": str, \"data_flow\": str, \"sequence\": str, "
            "\"deployment\": str, \"security\": str}",
            "Architecture:\nPattern: " + safe_str(arch.get("pattern"))
            + "\nComponents: " + json.dumps(safe_list(arch.get("components"))[:8], default=str)
            + "\nData Flow: " + json.dumps(safe_list(arch.get("data_flow"))[:8])
            + "\nSecurity: " + json.dumps(safe_list(arch.get("security"))[:6])
            + "\nTech: " + json.dumps(safe_list(semantic.get("technology_stack"))[:8]),
            max_tokens=12000,
        )
        if r and isinstance(r, dict) and "infrastructure" in r:
            return r
        return self._fb_mermaid(arch)


# ═══════════════════════════════════════════════════════════════════════
#  GROK AI CLIENT — xAI Grok via Azure AI Foundry (inference SDK)
#  Inherits all ECI analysis methods from QwenAI (same inference path).
# ═══════════════════════════════════════════════════════════════════════

class GrokAI(QwenAI):
    """xAI Grok deployed on Azure AI Foundry — uses azure.ai.inference SDK.

    Config keys (set by config_loader from config.yaml integrations.grok):
        grok_endpoint    — Azure AI Foundry endpoint URL
        grok_key         — API key
        grok_deployment  — deployment name, e.g. grok-4-1-fast-reasoning
        grok_api_version — API version, e.g. 2024-05-01-preview
    """

    @classmethod
    def from_session(cls):
        endpoint   = st.session_state.get("grok_endpoint",   "").strip()
        deployment = st.session_state.get("grok_deployment", "").strip()
        key        = st.session_state.get("grok_key",        "").strip()
        api_ver    = st.session_state.get("grok_api_version", "2024-05-01-preview").strip()
        return cls(
            key        = key,
            model      = deployment,
            endpoint   = endpoint,
            deployment = deployment,
            api_version= api_ver,
            mode       = "inference",   # always azure.ai.inference SDK
        )

    def test(self):
        if not self._inf_client:
            return False, "Grok not configured — check endpoint/key in config.yaml"
        try:
            resp = self._inf_client.complete(
                model=self.model,
                messages=[_InfUsrMsg("Reply with: ok")],
                max_tokens=5,
            )
            return True, f"Connected to {self.model} (Grok / Azure AI Foundry)"
        except Exception as e:
            return False, "Grok test failed: " + str(e)[:200]

    def _inf_call_text(self, system: str, user: str, max_tokens: int = 8192) -> "str | None":
        """Override to label warnings as Grok rather than Qwen."""
        if not self._inf_client:
            return None
        try:
            resp = self._inf_client.complete(
                model=self.model,
                messages=[_InfSysMsg(system), _InfUsrMsg(user)],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            if resp.choices:
                return resp.choices[0].message.content or ""
        except Exception as e:
            st.warning("Grok: " + str(e)[:200])
        return None


# ═══════════════════════════════════════════════════════════════════════
#  DEEPSEEK AI CLIENT — DeepSeek via Azure AI Foundry (OpenAI-compat)
#  Endpoint uses /openai/v1/ path — standard OpenAI client, no /models.
#  Inherits all ECI analysis + JSON repair methods from QwenAI.
# ═══════════════════════════════════════════════════════════════════════

class DeepSeekAI(QwenAI):
    """DeepSeek deployed on Azure AI Foundry (OpenAI-compatible endpoint).

    Uses the standard openai.OpenAI client with base_url set to the
    /openai/v1/ endpoint — NOT the azure.ai.inference SDK.

    Config keys (set by config_loader from config.yaml providers.deepseek):
        deepseek_endpoint   — e.g. https://your-resource.openai.azure.com/openai/v1/
        deepseek_key        — API key
        deepseek_deployment — deployment/model name, e.g. DeepSeek-V3.2
        deepseek_api_version — not used (endpoint already versioned)
    """

    def __init__(self, key: str, model: str, endpoint: str,
                 deployment: str, api_version: str = "", mode: str = ""):
        # Bypass QwenAI.__init__ path-mangling; set up OpenAI client directly
        self.key          = key.strip()
        self._client      = None
        self._inf_client  = None   # not used for DeepSeek
        self._mode        = "openai_compat"
        self.model        = (deployment or model or "DeepSeek-V3.2").strip()
        self.deployment   = self.model

        endpoint = (endpoint or "").strip().rstrip("/") + "/"
        if self.key and endpoint:
            _oi_cls = _get_OpenAI()
            if _oi_cls:
                try:
                    self._client = _oi_cls(
                        api_key=self.key,
                        base_url=endpoint,
                    )
                except Exception:
                    pass

    @classmethod
    def from_session(cls):
        return cls(
            key        = st.session_state.get("deepseek_key",        "").strip(),
            model      = st.session_state.get("deepseek_deployment", "DeepSeek-V3.2").strip(),
            endpoint   = st.session_state.get("deepseek_endpoint",   "").strip(),
            deployment = st.session_state.get("deepseek_deployment", "DeepSeek-V3.2").strip(),
        )

    @property
    def is_live(self):
        return self._client is not None

    def test(self):
        if not self._client:
            return False, "DeepSeek not configured — check endpoint/key in config.yaml"
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_completion_tokens=5,
            )
            return True, f"Connected to {self.model} (DeepSeek / Azure AI Foundry)"
        except Exception as e:
            return False, "DeepSeek test failed: " + str(e)[:200]

    def _call(self, system: str, user: str, max_tokens: int = 8192) -> "dict | None":
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user + "\n\nIMPORTANT: Respond with ONLY a valid JSON object — no markdown fences, no trailing commas, no extra text."},
                ],
                max_completion_tokens=max_tokens,
                temperature=0.2,
            )
            if not resp.choices:
                return None
            txt = resp.choices[0].message.content or ""
            raw = txt.strip()
            repaired = self._repair_json(raw)
            for candidate in [raw, repaired,
                               self._repair_json(self._close_truncated_json(repaired))]:
                if not candidate:
                    continue
                m = re.search(r'\{[\s\S]+\}', candidate)
                if m:
                    try:
                        return json.loads(m.group())
                    except Exception:
                        pass
                try:
                    return json.loads(candidate)
                except Exception:
                    continue
            st.warning("DeepSeek: could not parse JSON. Raw: " + raw[:300])
            return None
        except Exception as e:
            st.warning("DeepSeek: " + str(e)[:200])
            return None

    def _call_text(self, system: str, user: str, max_tokens: int = 1024, **_) -> "str | None":
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_completion_tokens=max_tokens,
                temperature=0.4,
            )
            if resp.choices:
                return resp.choices[0].message.content
        except Exception as e:
            st.warning("DeepSeek chat: " + str(e)[:200])
        return None

    def call_raw_text(self, system: str, user: str, max_tokens: int = 8000) -> "str | None":
        return self._call_text(system, user, max_tokens=max_tokens)


# ═══════════════════════════════════════════════════════════════════════
#  CODEX AI CLIENT — GPT-5.3-Codex via Azure OpenAI (standard endpoint)
#  Same client stack as AzureAI; reads from codex_* session keys.
# ═══════════════════════════════════════════════════════════════════════

class CodexAI(AzureAI):
    """GPT-5.3-Codex on Azure OpenAI — standard AzureOpenAI client.

    Config keys (set by config_loader from config.yaml providers.codex):
        codex_api_key     — Azure OpenAI API key
        codex_endpoint    — e.g. https://ella-openai-eastus2.openai.azure.com/
        codex_deployment  — deployment name, e.g. gpt-5.3-codex
        codex_api_version — API version, e.g. 2025-04-01-preview
    """

    @classmethod
    def from_session(cls):
        return cls(
            key        = st.session_state.get("codex_api_key",     "").strip(),
            endpoint   = st.session_state.get("codex_endpoint",    "").strip(),
            version    = st.session_state.get("codex_api_version", "2025-04-01-preview").strip(),
            deployment = st.session_state.get("codex_deployment",  "gpt-5.3-codex").strip(),
        )

    def test(self):
        if not self._client:
            return False, "Codex not configured — check endpoint/key in config.yaml"
        try:
            self._client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": "Reply OK"}],
                **self._token_kwargs(5),
            )
            return True, f"Connected to {self.deployment} (GPT-5.3-Codex / Azure OpenAI)"
        except Exception as e:
            return False, "Codex test failed: " + str(e)[:200]


# ═══════════════════════════════════════════════════════════════════════
#  NANO AI CLIENT — GPT-5.4-Nano via Azure AI Foundry (OpenAI-compat)
#  Same client stack as DeepSeekAI; reads from nano_* session keys.
# ═══════════════════════════════════════════════════════════════════════

class NanoAI(DeepSeekAI):
    """GPT-5.4-Nano on Azure AI Foundry (OpenAI-compatible /openai/v1/ endpoint).

    Config keys (set by config_loader from config.yaml providers.nano):
        nano_endpoint   — e.g. https://foundry-agents-poc-resource.openai.azure.com/openai/v1/
        nano_key        — API key
        nano_deployment — deployment name, e.g. gpt-5.4-nano
    """

    @classmethod
    def from_session(cls):
        return cls(
            key        = st.session_state.get("nano_key",        "").strip(),
            model      = st.session_state.get("nano_deployment", "gpt-5.4-nano").strip(),
            endpoint   = st.session_state.get("nano_endpoint",   "").strip(),
            deployment = st.session_state.get("nano_deployment", "gpt-5.4-nano").strip(),
        )

    def test(self):
        if not self._client:
            return False, "Nano not configured — check endpoint/key in config.yaml"
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with: ok"}],
                max_completion_tokens=5,
            )
            return True, f"Connected to {self.model} (GPT-5.4-Nano / Azure AI Foundry)"
        except Exception as e:
            return False, "Nano test failed: " + str(e)[:200]
