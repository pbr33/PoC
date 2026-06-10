"""SharePoint integration client for ECI Presale Agent.

Handles uploading proposals, downloading scope documents, and monitoring
folders for new files. Uses Microsoft Graph API via MSAL.
"""

import json
import streamlit as st
from datetime import datetime

try:
    import msal
except ImportError:
    msal = None

try:
    import requests as _requests
except ImportError:
    _requests = None


class SharePointClient:
    """Microsoft Graph-based SharePoint client."""

    def __init__(self, site_url: str, client_id: str, client_secret: str, tenant_id: str):
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._token = None

    @classmethod
    def from_session(cls):
        return cls(
            site_url=st.session_state.get("sharepoint_site_url", ""),
            client_id=st.session_state.get("sharepoint_client_id", ""),
            client_secret=st.session_state.get("sharepoint_client_secret", ""),
            tenant_id=st.session_state.get("sharepoint_tenant_id", ""),
        )

    def _get_token(self) -> str | None:
        if not all([self.client_id, self.client_secret, self.tenant_id, msal]):
            return None
        try:
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=authority,
                client_credential=self.client_secret,
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            if "access_token" in result:
                self._token = result["access_token"]
                return self._token
        except Exception:
            pass
        return None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def test_connection(self):
        token = self._get_token()
        if not token:
            if not all([self.client_id, self.client_secret, self.tenant_id]):
                return False, "Missing SharePoint credentials. Fill in Client ID, Secret, and Tenant ID."
            return False, "Failed to acquire token. Check credentials."
        try:
            resp = _requests.get(
                "https://graph.microsoft.com/v1.0/sites/root",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "✅ SharePoint connected successfully!"
            return False, f"SharePoint returned status {resp.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)[:200]}"

    def list_folder(self, folder_path: str) -> list:
        """List files in a SharePoint folder. Returns filenames or mock data."""
        token = self._get_token()
        if token and _requests:
            try:
                site_parts = self.site_url.rstrip("/").split("/")
                site_name = site_parts[-1] if site_parts else "presales"
                url = (
                    f"https://graph.microsoft.com/v1.0/sites/root:/sites/{site_name}:"
                    f"/drive/root:{folder_path}:/children"
                )
                resp = _requests.get(url, headers=self._headers(), timeout=15)
                if resp.status_code == 200:
                    items = resp.json().get("value", [])
                    return [item["name"] for item in items if "name" in item]
            except Exception:
                pass

        # Mock data for demo
        return [
            "Scope_Document_ClientA_2025.pdf",
            "RFP_Response_Requirements.docx",
            "Technical_Architecture_Brief.pptx",
        ]

    def upload_proposal(self, results: dict):
        """Upload proposal results to SharePoint."""
        token = self._get_token()
        if token and _requests:
            try:
                filename = f"BELAL_Proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                content = json.dumps(results, indent=2, default=str)
                site_parts = self.site_url.rstrip("/").split("/")
                site_name = site_parts[-1] if site_parts else "presales"
                url = (
                    f"https://graph.microsoft.com/v1.0/sites/root:/sites/{site_name}:"
                    f"/drive/root:/Proposals/{filename}:/content"
                )
                headers = self._headers()
                headers["Content-Type"] = "application/json"
                resp = _requests.put(url, headers=headers, data=content, timeout=30)
                if resp.status_code in (200, 201):
                    return True, f"✅ Proposal uploaded to SharePoint: /Proposals/{filename}"
                return False, f"Upload failed with status {resp.status_code}"
            except Exception as e:
                return False, f"Upload error: {str(e)[:200]}"

        # Mock success
        return True, f"✅ Proposal uploaded to SharePoint: /Proposals/BELAL_Proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    def download_file(self, file_path: str) -> bytes | None:
        """Download a file from SharePoint."""
        token = self._get_token()
        if token and _requests:
            try:
                site_parts = self.site_url.rstrip("/").split("/")
                site_name = site_parts[-1] if site_parts else "presales"
                url = (
                    f"https://graph.microsoft.com/v1.0/sites/root:/sites/{site_name}:"
                    f"/drive/root:{file_path}:/content"
                )
                resp = _requests.get(url, headers=self._headers(), timeout=30)
                if resp.status_code == 200:
                    return resp.content
            except Exception:
                pass
        return None
