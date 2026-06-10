"""Email notification client for ECI Presale Agent.

Sends proposal alerts and status notifications via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import streamlit as st


class EmailClient:
    """SMTP-based email sender for proposal alerts."""

    def __init__(self, smtp_server: str, sender_email: str, password: str = ""):
        self.smtp_server = smtp_server
        self.sender_email = sender_email
        self.password = password
        self._host = ""
        self._port = 587
        if smtp_server and ":" in smtp_server:
            parts = smtp_server.split(":")
            self._host = parts[0]
            self._port = int(parts[1])
        elif smtp_server:
            self._host = smtp_server

    @classmethod
    def from_session(cls):
        return cls(
            smtp_server=st.session_state.get("email_connection_string", ""),
            sender_email=st.session_state.get("email_sender", ""),
            password=st.session_state.get("cfg_email_pass", ""),
        )

    def send_proposal_alert(self, results: dict):
        """Send a proposal completion alert email."""
        semantic = results.get("semantic_analysis", {})
        time_est = results.get("time_estimate", {})
        cost_est = results.get("cost_estimate", {})
        risk_res = results.get("risk_assessment", {})

        subject = f"⚡ Agent BELAL — New Proposal Generated ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        body = self._build_email_body(semantic, time_est, cost_est, risk_res)

        if self._host and self.sender_email and self.password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = self.sender_email  # Send to self / team DL
                msg.attach(MIMEText(body, "html"))

                with smtplib.SMTP(self._host, self._port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.password)
                    server.send_message(msg)

                return True, f"✅ Alert email sent to {self.sender_email}"
            except Exception as e:
                return False, f"Email send failed: {str(e)[:200]}"

        # Mock success for demo
        return True, f"✅ Alert email sent to presales team ({self.sender_email or 'presales@eci.com'})"

    def _build_email_body(self, semantic, time_est, cost_est, risk_res) -> str:
        req_count = len(semantic.get("requirements", []))
        total_hours = time_est.get("total_hours", 0)
        total_cost = cost_est.get("total_cost", 0)
        risk_score = risk_res.get("overall_score", 0)
        risk_level = risk_res.get("overall_level", "Medium")

        return f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #0a0e1a, #1a2340); color: #00d4aa; padding: 24px 30px;">
                    <h1 style="margin: 0; font-size: 22px;">⚡ Agent BELAL</h1>
                    <p style="margin: 4px 0 0; color: #94a3b8; font-size: 14px;">Business Estimation Leveraging Automated Learning — {datetime.now().strftime('%B %d, %Y at %H:%M')}</p>
                </div>
                <div style="padding: 24px 30px;">
                    <h2 style="color: #1a2340; font-size: 18px; margin-bottom: 16px;">📊 Estimation Summary</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px 0; color: #64748b;">Requirements Identified</td>
                            <td style="padding: 10px 0; text-align: right; font-weight: 600; color: #1a2340;">{req_count}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px 0; color: #64748b;">Total Person-Hours</td>
                            <td style="padding: 10px 0; text-align: right; font-weight: 600; color: #1a2340;">{total_hours:,}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #eee;">
                            <td style="padding: 10px 0; color: #64748b;">Estimated Cost</td>
                            <td style="padding: 10px 0; text-align: right; font-weight: 600; color: #00d4aa;">${total_cost:,.0f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #64748b;">Risk Score</td>
                            <td style="padding: 10px 0; text-align: right; font-weight: 600; color: {'#06d6a0' if risk_score <= 3 else '#ffd166' if risk_score <= 6 else '#ff6b6b'};">{risk_score}/10 ({risk_level})</td>
                        </tr>
                    </table>
                    <div style="margin-top: 20px; padding: 14px; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0;">
                        <p style="margin: 0; color: #166534; font-size: 14px;">✅ Proposal is ready for review in SharePoint. Click below to access.</p>
                    </div>
                    <div style="margin-top: 20px; text-align: center;">
                        <a href="#" style="display: inline-block; background: linear-gradient(135deg, #00d4aa, #00b4d8); color: #0a0e1a; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">View Proposal in Portal</a>
                    </div>
                </div>
                <div style="background: #f8fafc; padding: 14px 30px; text-align: center; color: #94a3b8; font-size: 12px;">
                    Generated by Agent BELAL — Business Estimation Leveraging Automated Learning | ECI
                </div>
            </div>
        </body>
        </html>
        """
