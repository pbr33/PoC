# ═══════════════════════════════════════════════════════════════════════
#  EXTERNAL SERVICES — SharePoint, Email, ArchitectNarrator
# ═══════════════════════════════════════════════════════════════════════
import json
import time
import base64
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict
from .ai_clients import AnthropicAI, AzureAI

try:
    import msal
except ImportError:
    msal = None

try:
    import requests as _requests
except ImportError:
    _requests = None


# ═══════════════════════════════════════════════════════════════════════
#  SHAREPOINT
# ═══════════════════════════════════════════════════════════════════════

class SP:
    def __init__(self, url, cid, cs, tid):
        self.url = url
        self.cid = cid
        self.cs = cs
        self.tid = tid

    @classmethod
    def from_session(cls):
        return cls(st.session_state.get("sp_url", ""), st.session_state.get("sp_cid", ""), st.session_state.get("sp_cs", ""), st.session_state.get("sp_tid", ""))

    def _auth(self):
        if not all([self.cid, self.cs, self.tid, msal]):
            return None
        try:
            app = msal.ConfidentialClientApplication(self.cid, authority="https://login.microsoftonline.com/" + self.tid, client_credential=self.cs)
            r = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            return r.get("access_token")
        except Exception:
            return None

    def test(self):
        tok = self._auth()
        if not tok:
            return False, "Missing credentials or auth failed."
        try:
            r = _requests.get("https://graph.microsoft.com/v1.0/sites/root", headers={"Authorization": "Bearer " + tok}, timeout=10)
            return (True, "SharePoint connected!") if r.status_code == 200 else (False, "Status " + str(r.status_code))
        except Exception as e:
            return False, str(e)[:200]

    def list_folder(self, path):
        tok = self._auth()
        if tok and _requests:
            try:
                sn = self.url.rstrip("/").split("/")[-1]
                r = _requests.get("https://graph.microsoft.com/v1.0/sites/root:/sites/" + sn + ":/drive/root:" + path + ":/children", headers={"Authorization": "Bearer " + tok}, timeout=15)
                if r.status_code == 200:
                    return [i["name"] for i in r.json().get("value", []) if "name" in i]
            except Exception:
                pass
        return []

    def upload(self, results):
        fn = "BELAL_Proposal_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        tok = self._auth()
        if tok and _requests:
            try:
                sn = self.url.rstrip("/").split("/")[-1]
                r = _requests.put("https://graph.microsoft.com/v1.0/sites/root:/sites/" + sn + ":/drive/root:/Proposals/" + fn + ":/content", headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"}, data=json.dumps(results, indent=2, default=str), timeout=30)
                if r.status_code in (200, 201):
                    return True, "Uploaded: /Proposals/" + fn
                return False, "Status " + str(r.status_code)
            except Exception as e:
                return False, str(e)[:200]
        return False, "SharePoint not configured."


# ═══════════════════════════════════════════════════════════════════════
#  EMAIL
# ═══════════════════════════════════════════════════════════════════════

class Mailer:
    def __init__(self, smtp, sender, pw):
        self.smtp = smtp
        self.sender = sender
        self.pw = pw

    @classmethod
    def from_session(cls):
        return cls(st.session_state.get("email_smtp", ""), st.session_state.get("email_sender", ""), st.session_state.get("cfg_email_pass", ""))

    def send(self, results):
        te = safe_dict(results.get("time_estimate"))
        ce = safe_dict(results.get("cost_estimate"))
        ri = safe_dict(results.get("risk_assessment"))
        subj = "Agent BELAL Proposal " + datetime.now().strftime("%Y-%m-%d %H:%M")
        body = "<h2>Agent BELAL</h2><p>Hours: " + str(te.get("total_hours", 0)) + " | Infra Cost: $" + str(ce.get("total_monthly_cost", 0)) + "/mo | Risk: " + safe_str(ri.get("overall_level")) + "</p>"
        if self.smtp and self.sender and self.pw:
            try:
                parts = (self.smtp + ":587").split(":")
                host = parts[0]
                port = int(parts[1])
                msg = MIMEMultipart()
                msg["Subject"] = subj
                msg["From"] = self.sender
                msg["To"] = self.sender
                msg.attach(MIMEText(body, "html"))
                with smtplib.SMTP(host, port) as s:
                    s.starttls()
                    s.login(self.sender, self.pw)
                    s.send_message(msg)
                return True, "Email sent to " + self.sender
            except Exception as e:
                return False, str(e)[:200]
        return False, "Email not configured."


# ═══════════════════════════════════════════════════════════════════════
#  ARCHITECT NARRATOR — ElevenLabs + HeyGen video pipeline
# ═══════════════════════════════════════════════════════════════════════

class ArchitectNarrator:
    """Turns a BELAL proposal into a personalised architect-presenter video.

    Pipeline
    --------
    1. generate_script()   — AzureAI summarises the proposal into a ~200-word
                             conversational pitch (≈ 90 s video).
    2. synthesize_voice()  — ElevenLabs TTS converts the script to an MP3.
                             The audio is embedded in the Streamlit UI AND
                             passed (base64) to HeyGen as the lip-sync source.
    3. generate_video()    — HeyGen v2 Video Generate endpoint creates an
                             avatar video using the supplied audio.
    4. poll_video()        — HeyGen video generation is asynchronous; this
                             polls every 5 s until status == "completed".
    """

    # ------------------------------------------------------------------ #
    #  Construction                                                        #
    # ------------------------------------------------------------------ #
    def __init__(self, el_key: str, hg_key: str, avatar_id: str, voice_id: str,
                 did_key: str = ""):
        self.el_key    = el_key.strip()
        self.hg_key    = hg_key.strip()
        self.avatar_id = avatar_id.strip()
        self.voice_id  = voice_id.strip()
        self.did_key   = did_key.strip()

    @classmethod
    def from_session(cls):
        return cls(
            st.session_state.get("elevenlabs_api_key", ""),
            st.session_state.get("heygen_api_key", ""),
            st.session_state.get("heygen_avatar_id", ""),
            st.session_state.get("heygen_voice_id", ""),
            st.session_state.get("did_api_key", ""),
        )

    @property
    def did_ready(self):
        return bool(self.did_key)

    @property
    def el_ready(self):
        return bool(self.el_key)

    @property
    def hg_ready(self):
        # Only the API key is needed; avatar is chosen inside the UI.
        return bool(self.hg_key)

    def check_credits(self) -> tuple:
        """Return (remaining_quota, plan_credit, error_str) from HeyGen v2 API."""
        import urllib.request, urllib.error
        req = urllib.request.Request(
            "https://api.heygen.com/v2/user/remaining_quota",
            headers={"X-Api-Key": self.hg_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                d = data.get("data") or {}
                remaining = d.get("remaining_quota", -1)
                plan_total = (d.get("details") or {}).get("plan_credit", 0)
                return remaining, plan_total, None
        except urllib.error.HTTPError as e:
            return -1, 0, f"HTTP {e.code}"
        except Exception as e:
            return -1, 0, str(e)[:100]

    # ------------------------------------------------------------------ #
    #  D-ID  — Free talking-head video (free trial available at d-id.com) #
    # ------------------------------------------------------------------ #

    def did_upload_image(self, image_bytes: bytes, content_type: str = "image/jpeg") -> tuple:
        """Upload an image to D-ID and return (image_url, error_str).

        D-ID requires a public URL for the source image.  Their asset upload
        endpoint accepts multipart/form-data and returns a CDN URL.
        """
        if not self.did_key:
            return None, "D-ID API key not configured."
        import urllib.request, urllib.error

        # Build a minimal multipart/form-data body
        boundary = "ECI_BOUNDARY_X1Y2Z3"
        filename = "avatar.jpg" if "jpeg" in content_type else "avatar.png"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        auth_b64 = base64.b64encode(f"{self.did_key}:".encode()).decode()
        req = urllib.request.Request(
            "https://api.d-id.com/images",
            data=body,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type":  f"multipart/form-data; boundary={boundary}",
                "Accept":        "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                url = data.get("url", "")
                if url:
                    return url, None
                return None, "D-ID image upload: no URL returned — " + json.dumps(data)[:200]
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", errors="ignore")[:400]
            return None, f"D-ID image upload error {e.code}: {body_txt}"
        except Exception as e:
            return None, f"D-ID image upload failed: {str(e)[:200]}"

    def generate_did_video(self, script: str, mp3_bytes: bytes | None,
                           source_image_url: str) -> tuple:
        """Submit a D-ID /talks job and return (talk_id, error_str).

        D-ID Talks API: https://docs.d-id.com/reference/talks
        • Free trial: sign up at d-id.com → ~5 free videos/month.
        • Auth: Basic base64(api_key:)   ← note the trailing colon
        • source_image_url: public HTTPS image URL (JPG/PNG)
        • Voice: ElevenLabs provider when el_key set, else Microsoft Neural TTS
        """
        if not self.did_key:
            return None, "D-ID API key not configured."
        if not source_image_url:
            return None, "No source image URL — please upload a photo first."

        import urllib.request, urllib.error

        # ── Script / voice block ──
        if mp3_bytes:
            # Upload the audio to D-ID's audio asset endpoint first
            audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
            script_block = {
                "type":  "audio",
                "audio_base64": "data:audio/mpeg;base64," + audio_b64,
            }
        elif self.el_key:
            # Use ElevenLabs as voice provider within D-ID
            script_block = {
                "type":     "text",
                "subtitles": False,
                "provider": {
                    "type":     "elevenlabs",
                    "voice_id": self.voice_id or "pNInz6obpgDQGcFmaJgB",  # Adam
                    "api_key":  self.el_key,
                },
                "input": script,
            }
        else:
            # Default: Microsoft Neural TTS (no extra key needed)
            script_block = {
                "type":     "text",
                "subtitles": False,
                "provider": {
                    "type":     "microsoft",
                    "voice_id": "en-US-GuyNeural",
                },
                "input": script,
            }

        payload = json.dumps({
            "source_url": source_image_url,
            "script":     script_block,
            "config": {
                "fluent":    True,
                "pad_audio": 0.0,
                "stitch":    True,
            },
        }).encode("utf-8")

        auth_b64 = base64.b64encode(f"{self.did_key}:".encode()).decode()
        req = urllib.request.Request(
            "https://api.d-id.com/talks",
            data=payload,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                talk_id = data.get("id", "")
                if talk_id:
                    return talk_id, None
                return None, "D-ID returned no talk id: " + json.dumps(data)[:300]
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", errors="ignore")[:500]
            try:
                err = json.loads(body_txt)
                msg = err.get("message") or err.get("description") or body_txt[:200]
                if "trial" in msg.lower() or "credit" in msg.lower() or "quota" in msg.lower():
                    return None, (
                        "D-ID free trial exhausted. "
                        "Sign up or top-up credits at https://studio.d-id.com/account/billing."
                    )
                return None, f"D-ID error {e.code}: {msg}"
            except Exception:
                return None, f"D-ID error {e.code}: {body_txt[:300]}"
        except Exception as e:
            return None, f"D-ID request failed: {str(e)[:200]}"

    def poll_did_video(self, talk_id: str) -> tuple:
        """Return (video_url, status, error_str) for a D-ID talk."""
        if not self.did_key:
            return None, "error", "D-ID API key not configured."
        import urllib.request, urllib.error
        auth_b64 = base64.b64encode(f"{self.did_key}:".encode()).decode()
        req = urllib.request.Request(
            f"https://api.d-id.com/talks/{talk_id}",
            headers={"Authorization": f"Basic {auth_b64}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                status = data.get("status", "")        # created / started / done / error
                url    = data.get("result_url", "")
                err    = data.get("error", {}) or {}
                err_msg = err.get("message") or err.get("description") or safe_str(err)[:200]
                return url, status, err_msg if status == "error" else None
        except urllib.error.HTTPError as e:
            return None, "error", f"D-ID poll error {e.code}"
        except Exception as e:
            return None, "error", str(e)[:200]

    def did_list_presenters(self) -> tuple:
        """Return (list_of_presenters, error_str) — D-ID built-in presenter avatars.

        D-ID provides a set of stock presenters that can be used without
        uploading a custom photo, ideal for getting started with zero setup.
        """
        if not self.did_key:
            return [], "D-ID API key not configured."
        import urllib.request, urllib.error
        auth_b64 = base64.b64encode(f"{self.did_key}:".encode()).decode()
        req = urllib.request.Request(
            "https://api.d-id.com/presenters",
            headers={"Authorization": f"Basic {auth_b64}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                presenters = data.get("presenters") or data.get("data") or []
                result = [
                    {
                        "id":          p.get("presenter_id") or p.get("id", ""),
                        "name":        p.get("name", ""),
                        "image_url":   p.get("thumbnail_url") or p.get("preview_url", ""),
                        "gender":      p.get("gender", ""),
                    }
                    for p in presenters
                ]
                return result, None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            return [], f"D-ID presenters error {e.code}: {body}"
        except Exception as e:
            return [], f"D-ID presenters request failed: {str(e)[:200]}"

    # ------------------------------------------------------------------ #
    #  Step 1 — Script generation                                         #
    # ------------------------------------------------------------------ #
    def generate_script(self, results: dict) -> str:
        """Use AzureAI to write a conversational 200-word pitch from results."""
        se = safe_dict(results.get("semantic_analysis"))
        te = safe_dict(results.get("time_estimate"))
        ce = safe_dict(results.get("cost_estimate"))
        ri = safe_dict(results.get("risk_assessment"))
        ar = safe_dict(results.get("architecture"))

        project_type   = safe_str(se.get("project_type", "enterprise cloud solution"))
        total_hours    = safe_int(te.get("total_hours", 0))
        monthly_cost   = safe_int(ce.get("total_monthly_cost", 0))
        risk_level     = safe_str(ri.get("overall_level", "Medium"))
        pattern        = safe_str(ar.get("pattern", "cloud-native"))
        obj_list       = [safe_str(o) for o in safe_list(se.get("business_objectives", []))[:3]]
        objectives_txt = "; ".join(obj_list) if obj_list else "digital transformation and operational efficiency"
        components     = safe_list(ar.get("components"))
        num_comps      = len(components)

        # Build summary context for the LLM
        context = (
            f"Project type: {project_type}\n"
            f"Architecture pattern: {pattern}\n"
            f"Business objectives: {objectives_txt}\n"
            f"Estimated effort: {total_hours:,} person-hours\n"
            f"Monthly infrastructure cost: ${monthly_cost:,}/month\n"
            f"Overall risk level: {risk_level}\n"
            f"Number of architecture components designed: {num_comps}\n"
        )

        _sys_prompt = (
            "You are the lead architect at ECI (Enterprise Cloud & Integration). "
            "Write a warm, confident, first-person video script (≈200 words, ≈90 seconds when spoken). "
            "The script will be read by an AI avatar of the architect. "
            "Tone: professional yet personable, like a senior expert briefing a client. "
            "Structure: greet warmly → summarise the solution in 2–3 sentences → highlight the key cost/timeline → "
            "mention risk posture → invite the client to the Live War Room to refine details → close confidently. "
            "Do NOT use bullet points or markdown — plain prose only. "
            "Return JSON: {\"script\": \"<the full script text>\"}"
        )
        _user_prompt = "Proposal context:\n" + context

        # Try Anthropic/Claude first (preferred), then Azure OpenAI
        claude = AnthropicAI.from_session()
        if claude.is_live:
            try:
                resp = claude._call(_sys_prompt, _user_prompt)
                if resp and isinstance(resp, dict) and resp.get("script"):
                    return safe_str(resp["script"])
            except Exception as e:
                st.warning(f"Claude script generation failed: {str(e)[:120]}. Falling back to Azure.")

        # Try Azure OpenAI
        ai = AzureAI.from_session()
        if ai.is_live:
            try:
                resp = ai._call(_sys_prompt, _user_prompt)
                if resp and isinstance(resp, dict) and resp.get("script"):
                    return safe_str(resp["script"])
            except Exception as e:
                st.warning(f"Azure script generation failed: {str(e)[:120]}. Using template script.")

        # Fallback: template-generated script
        cost_txt  = f"${monthly_cost:,} per month" if monthly_cost else "within your agreed budget"
        hours_txt = f"{total_hours:,} person-hours" if total_hours else "an optimised timeline"
        return (
            f"Hello! I'm your lead architect at ECI, and I've just finished analysing your scope document. "
            f"Based on our historical delivery data and your specific requirements for a {project_type}, "
            f"I've designed a {pattern} architecture made up of {num_comps} integrated Azure services — "
            f"all built around your core objectives: {objectives_txt}. "
            f"The total estimated effort comes in at {hours_txt}, "
            f"with an infrastructure running cost of {cost_txt}. "
            f"I've reviewed the risk landscape and the overall posture is {risk_level}, "
            f"which is well within industry norms for a project of this complexity — "
            f"and I've already embedded mitigations into the architecture design. "
            f"The complete technical blueprint, the time and cost breakdown, and the interactive 3D architecture fly-through "
            f"have all been uploaded to our SharePoint. "
            f"If you'd like to jump into our Live War Room to walk through the numbers together, "
            f"just drop me a message and I'll have a session ready within the hour. "
            f"Looking forward to bringing this solution to life with your team!"
        )

    # ------------------------------------------------------------------ #
    #  Step 2 — Voice synthesis (ElevenLabs)                              #
    # ------------------------------------------------------------------ #
    def synthesize_voice(self, script: str) -> tuple:
        """Call ElevenLabs TTS and return (mp3_bytes, error_str).

        Uses the multilingual-v2 model with the configured voice ID,
        falling back to the ECI default "Liam" voice if none is set.
        """
        if not self.el_ready:
            return None, "ElevenLabs API key not configured."

        import urllib.request, urllib.error

        voice = self.voice_id or "TX3LPaxmHKxFdv7VOQHJ"   # "Liam" — warm male narrator
        url   = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        payload = json.dumps({
            "text": script,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "style": 0.15,
                "use_speaker_boost": True,
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": self.el_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    return resp.read(), None
                return None, f"ElevenLabs HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            return None, f"ElevenLabs error {e.code}: {body}"
        except Exception as e:
            return None, f"ElevenLabs request failed: {str(e)[:200]}"

    # ------------------------------------------------------------------ #
    #  Step 3 — Video generation (HeyGen)                                 #
    # ------------------------------------------------------------------ #
    def generate_video(self, script: str, mp3_bytes: bytes | None,
                       talking_photo_id: str = "",
                       test_mode: bool = False) -> tuple:
        """Submit a HeyGen v2 video generation job and return (video_id, error).

        Character modes
        ---------------
        talking_photo_id set → type="talking_photo" (free to create)
        talking_photo_id empty → type="avatar" with self.avatar_id
            (works for both free stock avatars and custom Avatar 3 IDs)

        test_mode=True → adds "test": true to the HeyGen payload.
            HeyGen renders the video for FREE using Avatar 3 quality but
            adds a small watermark.  Perfect for review/approval before
            spending production credits.

        Voice: base64 ElevenLabs MP3 for lip-sync, or HeyGen built-in TTS.
        """
        if not self.hg_ready:
            return None, "HeyGen API key or Avatar ID not configured."

        import urllib.request, urllib.error

        # ---- Voice block ----
        if mp3_bytes:
            audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
            voice_block = {"type": "audio", "audio_base64": audio_b64}
        else:
            voice_block = {
                "type": "text", "input_text": script,
                "voice_id": self.voice_id or "2d5b0e6cf36f460aa7fc47e3eee4ba54",
            }

        # ---- Character block ----
        if talking_photo_id.strip():
            char_block = {
                "type": "talking_photo",
                "talking_photo_id": talking_photo_id.strip(),
                "talking_photo_style": "square",
            }
        else:
            char_block = {
                "type": "avatar",
                "avatar_id": self.avatar_id,
                "avatar_style": "normal",
            }

        payload = json.dumps({
            "test": test_mode,          # True = free render (Avatar 3, watermarked)
            "caption": False,
            "video_inputs": [{
                "character": char_block,
                "voice": voice_block,
                "background": {"type": "color", "value": "#0a0e1a"},
            }],
            "dimension": {"width": 1280, "height": 720},
            "aspect_ratio": "16:9",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.heygen.com/v2/video/generate",
            data=payload,
            headers={
                "X-Api-Key": self.hg_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                vid_id = (data.get("data") or {}).get("video_id")
                if vid_id:
                    return vid_id, None
                return None, "HeyGen returned no video_id: " + json.dumps(data)[:300]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:500]
            try:
                err_data = json.loads(body)
                code = (err_data.get("data") or err_data.get("error") or {})
                if isinstance(code, dict):
                    code = code.get("code", "")
                if "INSUFFICIENT_CREDIT" in str(code) or "credit" in body.lower():
                    return None, (
                        "INSUFFICIENT_CREDIT — Your HeyGen account has 0 remaining credits. "
                        "Add credits at heygen.com/pricing or wait for your monthly quota reset."
                    )
            except Exception:
                pass
            return None, f"HeyGen error {e.code}: {body[:300]}"
        except Exception as e:
            return None, f"HeyGen request failed: {str(e)[:200]}"

    # ------------------------------------------------------------------ #
    #  Utility — list free public stock avatars from HeyGen               #
    # ------------------------------------------------------------------ #
    def list_free_avatars(self) -> tuple:
        """Call GET /v2/avatars and return deduplicated accessible avatars.

        Returns (list_of_dicts, error_str).
        Each dict has keys: avatar_id, avatar_name, preview_image_url, gender.

        Note: The HeyGen v2 API returns a 'premium' boolean (False = accessible
        on the current plan) and a 'type' field (None for most avatars).  We
        deduplicate by avatar_id and include all non-premium entries.
        """
        import urllib.request, urllib.error
        req = urllib.request.Request(
            "https://api.heygen.com/v2/avatars",
            headers={"X-Api-Key": self.hg_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                all_avs = (data.get("data") or {}).get("avatars", [])

                # Deduplicate by avatar_id; keep first occurrence.
                seen = set()
                unique = []
                for a in all_avs:
                    aid = a.get("avatar_id", "")
                    if aid and aid not in seen:
                        seen.add(aid)
                        unique.append(a)

                # Keep only avatars accessible on this plan (premium == False).
                # If the API never sets premium=True, all are shown (expected).
                accessible = [
                    {
                        "avatar_id":         a.get("avatar_id", ""),
                        "avatar_name":       a.get("avatar_name") or a.get("avatar_id", ""),
                        "preview_image_url": a.get("preview_image_url", ""),
                        "preview_video_url": a.get("preview_video_url", ""),
                        "gender":            a.get("gender", ""),
                        "default_voice_id":  a.get("default_voice_id", ""),
                    }
                    for a in unique
                    if not a.get("premium", False)
                ]
                if not accessible:
                    return [], "No accessible avatars found for this HeyGen account."
                return accessible, None
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            return [], f"HeyGen avatars list error {e.code}: {body}"
        except Exception as e:
            return [], f"HeyGen avatars list failed: {str(e)[:200]}"

    # ------------------------------------------------------------------ #
    #  Utility — upload a photo to HeyGen asset store (for Talking Photo) #
    # ------------------------------------------------------------------ #
    def upload_talking_photo(self, image_bytes: bytes, content_type: str = "image/jpeg") -> tuple:
        """Upload an image to HeyGen's asset endpoint and register it as a
        Talking Photo so HeyGen can animate it for free (no custom-avatar
        credit consumed).

        Returns (talking_photo_id, error_str).
        """
        import urllib.request, urllib.error

        # Step 1: upload the raw image bytes to get an asset URL
        upload_req = urllib.request.Request(
            "https://upload.heygen.com/v1/asset",
            data=image_bytes,
            headers={
                "X-Api-Key": self.hg_key,
                "Content-Type": content_type,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(upload_req, timeout=30) as resp:
                up_data = json.loads(resp.read().decode("utf-8"))
                asset_url = (up_data.get("data") or {}).get("url", "")
                if not asset_url:
                    return None, "Asset upload returned no URL: " + json.dumps(up_data)[:200]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            return None, f"Photo upload error {e.code}: {body}"
        except Exception as e:
            return None, f"Photo upload failed: {str(e)[:200]}"

        # Step 2: register the uploaded asset as a Talking Photo avatar
        reg_payload = json.dumps({"image_url": asset_url}).encode("utf-8")
        reg_req = urllib.request.Request(
            "https://api.heygen.com/v1/talking_photo",
            data=reg_payload,
            headers={
                "X-Api-Key": self.hg_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(reg_req, timeout=20) as resp:
                reg_data = json.loads(resp.read().decode("utf-8"))
                tp_id = (reg_data.get("data") or {}).get("talking_photo_id", "")
                if tp_id:
                    return tp_id, None
                return None, "Talking Photo register returned no ID: " + json.dumps(reg_data)[:200]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:300]
            return None, f"Talking Photo register error {e.code}: {body}"
        except Exception as e:
            return None, f"Talking Photo register failed: {str(e)[:200]}"

    # ------------------------------------------------------------------ #
    #  Step 4 — Poll video status                                         #
    # ------------------------------------------------------------------ #
    def poll_video(self, video_id: str, max_wait: int = 300) -> tuple:
        """Poll HeyGen until video is ready or timeout.

        Returns (video_url, error_str). video_url is None on error/timeout.
        """
        import urllib.request, urllib.error

        url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
        req = urllib.request.Request(
            url,
            headers={"X-Api-Key": self.hg_key, "Accept": "application/json"},
            method="GET",
        )
        waited = 0
        interval = 5
        while waited < max_wait:
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    status = (data.get("data") or {}).get("status", "")
                    if status == "completed":
                        video_url = (data.get("data") or {}).get("video_url", "")
                        return video_url or None, None if video_url else "Completed but no URL"
                    if status in ("failed", "error"):
                        err_msg = (data.get("data") or {}).get("error", "Unknown HeyGen error")
                        return None, f"HeyGen generation failed: {err_msg}"
            except Exception as e:
                return None, f"Polling error: {str(e)[:200]}"
            time.sleep(interval)
            waited += interval
        return None, f"HeyGen video not ready after {max_wait} s. Check HeyGen dashboard."
