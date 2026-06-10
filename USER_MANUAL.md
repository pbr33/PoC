# ECI Business Estimation Tool — Complete User Manual

> **Version 2.0** | Last Updated: March 2026 | Powered by Multi-Model AI

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard Overview](#2-dashboard-overview)
3. [AI Model Configuration](#3-ai-model-configuration)
4. [Processing a Proposal — Step by Step](#4-processing-a-proposal--step-by-step)
5. [Results Tabs — Full Guide](#5-results-tabs--full-guide)
   - 5.1 Executive Summary
   - 5.2 Cost Breakdown
   - 5.3 Timeline
   - 5.4 Risk Analysis
   - 5.5 Technical Architecture
   - 5.6 Team Composition
   - 5.7 SOW (Statement of Work)
   - 5.8 Discovery Questions
   - 5.9 Live Azure Pricing
   - 5.10 Scenario Modelling (What-If Analysis)
   - 5.11 3D Architecture Viewer
   - 5.12 Video Narrator
   - 5.13 AI Chat
   - 5.14 Run History
   - 5.15 Live Demo
6. [Exports & Downloads](#6-exports--downloads)
7. [Run Library](#7-run-library)
8. [Admin Panel](#8-admin-panel)
9. [Notifications System](#9-notifications-system)
10. [Command Palette](#10-command-palette)
11. [Integrations Setup](#11-integrations-setup)
    - 11.1 SharePoint
    - 11.2 Email (SMTP)
    - 11.3 Video Narrator (HeyGen / D-ID / ElevenLabs)
12. [AI Model Reference](#12-ai-model-reference)
13. [Training & Continuous Learning](#13-training--continuous-learning)
14. [Troubleshooting](#14-troubleshooting)
15. [Keyboard Shortcuts](#15-keyboard-shortcuts)

---

## 1. Getting Started

### System Requirements
- Python 3.10+
- Modern web browser (Chrome, Edge, Firefox)
- Internet connection (for AI model APIs and live Azure pricing)

### Launching the Application

```bash
cd <project-directory>
pip install -r requirements.txt
streamlit run main.py
```

The app opens at `http://localhost:8501`.

### First Login

The app uses a configurable authentication gate. On first load:

1. Enter your **admin password** (default: set via `ADMIN_PASSWORD` environment variable)
2. Or use **Microsoft SSO** if configured (see Section 11)
3. The session persists for your browser session

### Environment Variables (Optional Pre-configuration)

Set these to pre-populate API keys on startup:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude (Anthropic direct) |
| `AZURE_API_KEY` | Azure OpenAI |
| `AZURE_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_DEPLOYMENT` | Azure OpenAI deployment name |
| `GEMINI_API_KEY` | Google Gemini |
| `QWEN_API_KEY` | Qwen DashScope |
| `QWEN_ENDPOINT` | Qwen Azure AI Foundry endpoint |
| `QWEN_DEPLOYMENT` | Qwen Azure AI Foundry deployment name |
| `QWEN_FOUNDRY_KEY` | Qwen Azure AI Foundry API key |
| `VERTEX_PROJECT_ID` | Google Cloud project for Vertex AI |
| `VERTEX_REGION` | Vertex AI region (e.g., `us-east5`) |
| `ELEVENLABS_API_KEY` | ElevenLabs voice synthesis |
| `HEYGEN_API_KEY` | HeyGen video avatar |
| `DID_API_KEY` | D-ID video avatar |

---

## 2. Dashboard Overview

The interface has three main areas:

### Left Sidebar
- **ECI logo** and branding header
- **AI Model configuration** panels (one per AI provider)
- **Preferred LLM selector** — which model powers all 11 agents
- **Integrations** (SharePoint, Email, Narrator)
- **Navigation hints**

### Top Bar
- **Page title** and version
- **Notification bell** 🔔 — shows unread count badge
- **Breadcrumb** tabs: Presale | Run Library | Admin

### Main Content Area
- Changes based on active tab
- Full-width results display after processing
- Responsive layout with collapsible sections

---

## 3. AI Model Configuration

The tool supports **five AI providers**. Configure whichever you have access to, then select your preferred model.

### 3.1 Claude (Anthropic Direct)

1. Go to **sidebar → Claude section**
2. Paste your **Anthropic API Key** (starts with `sk-ant-...`)
3. Select model from dropdown:
   - `claude-sonnet-4-6` *(recommended — best balance)*
   - `claude-opus-4-6` *(most powerful)*
   - `claude-haiku-4-5` *(fastest, most economical)*
   - Plus older Claude 3.x models
4. Click **Test Claude** — should show ✅ green badge

### 3.2 Azure OpenAI (GPT-4)

1. Go to **sidebar → Azure OpenAI section**
2. Fill in:
   - **API Key** — from Azure Portal → your OpenAI resource → Keys
   - **Endpoint** — e.g., `https://myresource.openai.azure.com`
   - **Deployment Name** — e.g., `gpt-4o`
   - **API Version** — leave as `2024-06-01` unless instructed otherwise
3. Click **Test Azure** — should show ✅

### 3.3 Google Gemini

1. Go to **sidebar → Gemini section**
2. Paste your **Gemini API Key** from Google AI Studio
3. Select model:
   - `gemini-2.0-flash` *(default, fast)*
   - `gemini-1.5-pro` *(more detailed)*
4. Click **Test Gemini**

### 3.4 Qwen (DashScope or Azure AI Foundry)

The Qwen section has a **Source** radio toggle:

#### DashScope Mode
1. Select **DashScope** radio
2. Enter your **DashScope API Key**
3. Select model (qwen-plus, qwen-max, qwen-turbo, etc.)
4. Click **Test Qwen**

#### Azure AI Foundry Mode (Recommended for fine-tuned models)
1. Select **Azure AI Foundry** radio
2. Fill in:
   - **API Endpoint** — e.g., `https://myresource.services.ai.azure.com`
   - **API Key** — from Azure AI Foundry portal
   - **Deployment Name** — e.g., `qwen3-32b-ft-036702e3a53a42189900a542fcab780e`
   - **API Version** — leave as `2024-06-01`
3. Click **Test Qwen** — should show: `Connected to qwen3-32b-ft-... (foundry)`

> **Note:** Azure AI Foundry uses a different API path than Azure OpenAI. The tool handles this automatically.

### 3.5 Vertex AI (Google Cloud — Claude Models)

Use this to access Claude models through Google Cloud without needing a direct Anthropic API key.

**Pre-requisite:** Run `gcloud auth application-default login` on the machine hosting the app. No JSON key file needed.

1. Go to **sidebar → Vertex AI section**
2. Enter your **GCP Project ID** (e.g., `my-project-123`)
3. Enter **Region** (e.g., `us-east5`)
4. Select model from dropdown
5. Click **Test Vertex** — should show ✅

### 3.6 Selecting Your Preferred LLM

At the bottom of the AI configuration section:

1. Find the **Preferred LLM** dropdown
2. Select from: `Azure OpenAI | Claude | Gemini | Qwen | Vertex AI`
3. All 11 pipeline agents + chat will use this model

Status badges show real-time connectivity:
- 🟢 `GPT` — Azure OpenAI connected
- 🟣 `Claude` — Anthropic connected
- 🔵 `Gemini` — Gemini connected
- 🟡 `Qwen` — Qwen connected (DashScope or Foundry)
- ☁️ `Vertex` — Vertex AI connected

---

## 4. Processing a Proposal — Step by Step

### Step 1: Navigate to Presale Tab

Click **Presale** in the top navigation.

### Step 2: Upload Your Scope Document

You can provide the scope document in three ways:

**Option A — File Upload**
- Click **Browse files** or drag-and-drop
- Supported formats: PDF, DOCX, TXT, XLSX, CSV, PNG, JPG
- Multi-file upload supported (all documents merged)

**Option B — Paste Text**
- Click the **Paste text** tab
- Paste your scope, requirements, or RFP directly

**Option C — SharePoint**
- If SharePoint is configured (see Section 11.1)
- Click **Load from SharePoint** and select your document

### Step 3: Fill Project Details

| Field | Description | Example |
|---|---|---|
| **Client / Project Name** | Used in proposal headers | "Contoso Digital Transformation" |
| **Project Type** | AI/ML, Web, Mobile, Cloud, etc. | "AI & Machine Learning" |
| **Industry Vertical** | Client's industry | "Financial Services" |
| **Budget Range** | Client's stated budget | "£150,000 – £250,000" |
| **Target Timeline** | Requested delivery period | "6 months" |
| **Delivery Region** | For pricing calculations | "UK" |

### Step 4: Run the Pipeline

Click the large **Generate Estimation** button.

The 11-agent pipeline runs in parallel where possible. A real-time progress panel shows:

```
🔍 Agent 1: Requirements Analysis ............ ✅ Complete
📊 Agent 2: Cost Estimation .................. ✅ Complete
⏱️  Agent 3: Time Estimation .................. ✅ Complete
⚠️  Agent 4: Risk Analysis .................... ✅ Complete
🏗️  Agent 5: Architecture Design .............. ✅ Complete
👥 Agent 6: Team Composition ................. ✅ Complete
📄 Agent 7: SOW Generation ................... ✅ Complete
❓ Agent 8: Discovery Questions .............. ✅ Complete
💰 Agent 9: Live Azure Pricing ............... ✅ Complete
🔍 Agent 10: Scope Completeness Check ........ ✅ Complete
📝 Agent 11: Proposal Writer ................. ✅ Complete
```

Typical processing time: **45–90 seconds** depending on model and document length.

### Step 5: Scope Completeness Check

Before full results appear, a **Requirements Completeness** panel may show:

- 🟢 Items clearly defined in the document
- 🟡 Items partially covered (need clarification)
- 🔴 Items missing (should be asked before submission)

You can:
- Click **Acknowledge & Continue** to proceed with noted gaps
- Use the checklist to guide your pre-submission discovery call

---

## 5. Results Tabs — Full Guide

After processing completes, results appear across 15 tabs.

---

### 5.1 Executive Summary

**What it shows:**
- One-page professional summary suitable for C-suite presentation
- Project overview, key deliverables, investment summary, recommended approach
- Confidence score and complexity rating

**How to use:**
- Click **Copy** to copy the text for pasting into emails or documents
- This section is included verbatim in the PDF export

---

### 5.2 Cost Breakdown

**What it shows:**
- Detailed cost table by phase (Discovery, Design, Development, Testing, Deployment, Support)
- Team role costs (architect, senior dev, junior dev, QA, PM)
- Contingency, risk buffer, management overhead
- Currency toggle: GBP / USD / EUR
- Visual stacked bar chart by phase and role

**How to use:**
- Hover over chart bars to see exact figures
- Use the **Currency** dropdown to switch display currency
- Costs automatically reflect your team composition inputs
- Included in the 5-sheet Excel export as its own tab

---

### 5.3 Timeline

**What it shows:**
- Phase-by-phase delivery schedule
- Milestone dates with dependencies
- Gantt chart (Mermaid diagram)
- Sprint breakdown (2-week sprints with tasks per sprint)
- Critical path indicators

**How to use:**
- The Gantt chart renders inline — zoom in/out with browser zoom
- Sprint breakdown can be copied directly into project management tools (Jira, Azure DevOps)
- Timeline auto-adjusts when you use Scenario Modelling to add/remove engineers

---

### 5.4 Risk Analysis

**What it shows:**
- Risk register with 10–20 identified risks
- Each risk: Description, Likelihood (1–5), Impact (1–5), Risk Score, Mitigation Strategy
- Heat map visualisation (Plotly interactive)
- Overall project risk rating: Low / Medium / High / Critical
- Risk categories: Technical, Resource, Commercial, Timeline, Dependency

**How to use:**
- Click any risk row to expand the mitigation detail
- The risk radar chart shows balance across risk categories
- High-risk items (score ≥ 15) are highlighted in red
- Risk data feeds into the cost contingency calculation automatically

---

### 5.5 Technical Architecture

**What it shows:**
- Recommended technical stack with justification
- Architecture diagram (auto-generated Mermaid flowchart)
- Azure service recommendations with tier suggestions
- Integration map showing system connections
- Alternative technology options considered

**How to use:**
- The architecture diagram can be copied as text/image
- Click **View in 3D** to open the immersive 3D architecture viewer (Tab 11)
- Architecture feeds the Live Azure Pricing engine (Tab 9) automatically

---

### 5.6 Team Composition

**What it shows:**
- Recommended team structure
- Role descriptions, experience requirements, FTE allocation
- Team org chart
- Rationale for team sizing decisions
- Optional: Named ECI team members (if configured)

**How to use:**
- Team composition feeds into cost calculations automatically
- Modify via Scenario Modelling (Tab 10) to see cost/timeline impact of team changes

---

### 5.7 SOW (Statement of Work)

**What it shows:**
- Professionally formatted Statement of Work document
- Sections: Project Scope, Deliverables, Timeline & Milestones, Payment Terms, Assumptions, Exclusions, Change Management, Acceptance Criteria
- Ready to send to client for review/signature

**How to use:**
- Click **Download SOW (Word)** for an editable `.docx`
- Click **Download SOW (PDF)** for a final version
- All fields are pre-populated from the AI agent outputs
- Payment schedule is milestone-based by default

---

### 5.8 Discovery Questions

**What it shows:**
- Prioritised list of 10–15 discovery questions the presales team should ask
- Organised by category: Technical, Business, Budget, Timeline, Decision Process
- Coverage indicator showing which scope areas each question addresses
- Suggested follow-up probes for each question
- "Discovery Prep Deck" summary

**How to use:**
- Print or export as PDF to use in the first client meeting
- Check off questions as they are answered during the discovery call
- Unanswered questions from the Completeness Check (Section 4, Step 5) appear here highlighted
- Export as **Discovery Prep Deck (PDF)** via the Downloads section

---

### 5.9 Live Azure Pricing

**What it shows:**
- Real-time infrastructure cost estimates fetched from the **Azure Retail Prices API**
- Services: Azure OpenAI, App Service, Azure SQL, Azure Blob Storage, Key Vault, Azure Container Registry, and others detected from the architecture
- Monthly and annual cost estimates
- Comparison against static reference prices
- Region: East US (configurable)

**How to use:**
- Prices refresh automatically on each new estimation run
- Click **Refresh Prices** to re-fetch live data
- If the live API is unavailable, the tool falls back to a curated static pricing catalog (updated 2025)
- All prices are in USD — multiply by your regional exchange rate for client-facing documents
- Included in the Excel export as an "Infrastructure Costs" tab

> **Note:** Prices shown are list prices. Enterprise agreements, reserved instances, and negotiated discounts are not reflected.

---

### 5.10 Scenario Modelling (What-If Analysis)

This is one of the most powerful features — allowing you to model different delivery options and compare them side by side.

**What it shows:**
- Up to 3 scenarios running simultaneously
- Each scenario has independent levers for Scope, Team, and Pricing
- Live recalculation of hours, cost, duration, risk score
- Side-by-side comparison table with colour-coded deltas
- Bar charts and radar chart comparing all scenarios visually

**How to use:**

**Step 1: Add a Scenario**
- Click **+ Add Scenario** (up to 3 scenarios)
- Each scenario starts as a copy of the base estimation

**Step 2: Adjust Levers**

For each scenario, three columns of controls appear:

*Scope Column:*
| Lever | Range | Effect |
|---|---|---|
| Scope Complexity | 0.5× – 2.5× | Scales all hours linearly |
| Phases Included | Slider (1–6) | Adds/removes project phases |
| Include Support Phase | Toggle | Adds post-launch support costs |

*Team Column:*
| Lever | Range | Effect |
|---|---|---|
| Engineers | 1–10 | Brooks' Law applied (diminishing returns) |
| Architects | 0–3 | Reduces rework; adds cost |
| Seniority Mix | Junior/Mixed/Senior | ±35%/0%/–18% on hours |

*Pricing Column:*
| Lever | Options | Effect |
|---|---|---|
| Contract Type | T&M / Hybrid / Fixed | Fixed adds 12% risk premium |
| Discount % | 0–30% | Applied to final cost |
| Region Multiplier | 0.5× – 2.0× | Adjusts for delivery region cost |

**Step 3: Read the Results**

- **KPI Cards** — Hours, Cost, Duration, Risk Score shown with delta vs baseline
- **Comparison Table** — All scenarios side by side, colour-coded (green = better, red = worse)
- **Bar Charts** — Hours & Duration chart, Cost Breakdown stacked bar
- **Radar Chart** — Multi-dimensional profile (Hours, Cost, Duration, Risk, Team Size)

**Step 4: Export**
- Click **Export Scenario Comparison (Excel)** — downloads a 2-sheet workbook:
  - Sheet 1: Parameter comparison table
  - Sheet 2: KPI comparison table

**Common Use Cases:**
- "What if we reduce scope by 30%?" → Set Scope Complexity to 0.7×
- "What if we add 2 more engineers?" → Increase Engineers slider
- "Fixed price vs T&M — what's the cost difference?" → Switch Contract Type
- "Senior-only team vs mixed team?" → Change Seniority Mix
- "Can we hit the deadline with a discount?" → Combine levers + discount

---

### 5.11 3D Architecture Viewer

**What it shows:**
- Immersive 3D fly-through of the recommended technical architecture
- Nodes represent Azure services; edges show data flows
- Interactive: rotate, zoom, pan, click nodes for detail

**How to use:**
- Click and drag to **rotate** the architecture
- Scroll wheel to **zoom**
- Click any node to see **service details** (name, purpose, SKU, estimated cost)
- Click **Auto-Rotate** for a presentation-ready animation
- Press **F** for full-screen mode
- Works best in Chrome/Edge — uses WebGL via Three.js

> **Tip:** Use this view in client presentations to create a visually impressive walkthrough of the proposed solution.

---

### 5.12 Video Narrator

Generate a professional AI video presentation of the proposal summary.

**Supported services:**
- **HeyGen** — realistic AI avatar lip-synced to the proposal script
- **D-ID** — photo-to-video avatar (use a presenter photo)
- **ElevenLabs** — voice-only narration (audio MP3)

**How to use:**

**Step 1: Configure (sidebar)**
- Select **Narrator Mode**: HeyGen / D-ID / Custom (ElevenLabs)
- Enter API key for your chosen service
- For HeyGen: enter Avatar ID and Voice ID
- For D-ID: enter your presenter photo URL or upload

**Step 2: Generate Script**
- Click **Generate Script** — AI writes a 2–3 minute narration based on the executive summary
- Preview and edit the script text if needed

**Step 3: Generate Video**
- Click **Generate Video**
- Processing time: 30–120 seconds depending on service
- Video renders in the tab when complete

**Step 4: Download**
- Click **Download Video (MP4)** to save locally
- Share link available if using HeyGen hosted delivery

> **Test Mode:** Enable **Test Mode** in the sidebar to generate a short clip (saves API credits during testing).

---

### 5.13 AI Chat

**What it shows:**
- A context-aware AI chat interface grounded in your specific proposal results
- The AI knows all the details: scope, costs, risks, architecture, team, timeline

**How to use:**
- Type any question about your proposal and press **Enter** or click **Send**
- Example questions:
  - *"Why is the risk score High?"*
  - *"Explain the Azure service choices in simple terms"*
  - *"What would happen to cost if we moved to a senior-only team?"*
  - *"Draft an email to the client summarising the investment"*
  - *"What are the top 3 things the client needs to decide before we start?"*
- Uses the same model as the pipeline (your selected Preferred LLM)
- Chat history is preserved for the session
- Click **Clear Chat** to start a fresh conversation

---

### 5.14 Run History

**What it shows:**
- Chronological log of all processing events for this run:
  - Agent start/completion timestamps
  - Fallback events (e.g., "Live pricing API unavailable, using static catalog")
  - Warning messages
  - Token usage per agent
- Useful for diagnosing unexpected results or slow processing

**How to use:**
- Expand any log entry to see full details
- Filter by severity: Info / Warning / Error
- Download as JSON for support

---

### 5.15 Live Demo

**What it shows:**
- A pre-built interactive demonstration mode
- Showcases all features using sample data without requiring a real scope document
- Useful for sales demos, onboarding, or testing

**How to use:**
- Click **Load Demo Data** to populate all tabs with realistic sample results
- Walk through each tab to see the full capability of the tool
- Demo data can be used as a reference for formatting expectations

---

## 6. Exports & Downloads

After processing, the **Downloads** section appears at the bottom of the Presale tab.

### Available Export Formats

| Format | Contents | Use Case |
|---|---|---|
| **Excel (5-sheet)** | Summary, Cost Breakdown, Timeline, Risk Register, Infrastructure Costs | Internal review, financial modelling |
| **PDF Proposal** | Full formatted proposal — cover page, all sections | Client delivery, archiving |
| **PowerPoint (PPTX)** | Slide deck — one slide per major section | Presentations |
| **SOW (Word .docx)** | Statement of Work, payment terms, milestones | Contract/legal review |
| **SOW (PDF)** | Final SOW for sending to client | Client signature |
| **Discovery Prep (PDF)** | Discovery questions + coverage map | Sales meetings |
| **Scenario Comparison (Excel)** | What-if analysis comparison table | Commercial negotiations |
| **JSON** | Raw structured data from all agents | API integrations, archiving |
| **ZIP Bundle** | All of the above in one archive | Full handover package |

### Sending by Email

1. Click **Send by Email** in the Downloads section
2. The PDF and Excel are attached automatically
3. Email uses your configured SMTP settings (see Section 11.2)
4. Subject and body are pre-written but editable before sending

### Saving to SharePoint

1. Click **Save to SharePoint**
2. The PDF proposal is uploaded to the configured SharePoint document library
3. A link to the uploaded file is shown for copying

---

## 7. Run Library

The Run Library stores all completed estimation runs persistently in a local SQLite database.

### Accessing the Run Library

Click **Run Library** in the top navigation tabs.

### What's Stored

Each saved run contains:
- Project name, client, date/time processed
- All agent outputs (full JSON)
- Which AI model was used
- Architect review status
- Tags and notes

### Actions on Saved Runs

| Action | How |
|---|---|
| **View** | Click any run row to re-open full results |
| **Download** | Click 📥 to download the Excel/PDF for that run |
| **Mark Reviewed** | Click ✅ — marks the run as architect-reviewed (with timestamp) |
| **Unmark Reviewed** | Click ↩️ — returns run to unreviewed state |
| **Delete** | Click 🗑️ — permanently removes the run (admin only) |
| **Compare** | Select 2 runs → click Compare to see side-by-side diff |
| **Add Note** | Click 📝 to add a comment to the run |

### Filtering & Search

- **Search** by project name or client
- **Filter** by: date range, AI model used, reviewed status, project type
- **Sort** by: date, project name, cost estimate, risk score

### Auto-Save

Runs are automatically saved after processing completes. You do not need to manually save. The notification bell will confirm: *"Run #47 saved."*

---

## 8. Admin Panel

Access the Admin Panel by clicking **Admin** in the top navigation.

> **Access:** Admin password required. Non-admin users see a restricted view.

### 8.1 Model Performance Dashboard

Shows real metrics from your run history:
- Total proposals processed
- Average estimation accuracy (vs recorded actuals)
- Win rate (proposals marked as Won in outcome tracking)
- Cost variance distribution

> If fewer than 5 outcome-recorded runs exist, the dashboard shows *"Not enough data"* rather than misleading numbers.

### 8.2 Accuracy Trend Chart

Rolling 30-day and 90-day accuracy trend. Shows whether estimation quality is improving over time as training data accumulates.

### 8.3 Training Data Management

- View all stored historical projects used to calibrate estimates
- Add new training examples (actual vs estimated hours/cost)
- Remove outliers
- See the correction factors currently applied per technology category

See Section 13 for the full training workflow.

### 8.4 Agent Performance Log

- Which agent had the most fallback events
- Average response time per agent
- Error rate per agent
- Used to identify which agent would benefit most from additional training examples

### 8.5 Database Maintenance

- **Prune old runs** — remove runs older than N days
- **Rebuild indexes** — optimise query performance
- **Export DB backup** — download the SQLite database file
- **Clear notifications** — wipe the notification log

---

## 9. Notifications System

The notification bell 🔔 in the top-right corner shows real-time events.

### Reading Notifications

- Click 🔔 to open the notification popover
- Unread count shown as a badge: 🔔(3)
- Blue dot = unread, no dot = read
- Notifications auto-mark as read when you view them

### Notification Types

| Icon | Event | Triggered By |
|---|---|---|
| 📊 | Run saved | After pipeline completes |
| ✅ | Run reviewed | Architect clicks Mark Reviewed |
| ↩️ | Run unreviewed | Architect reverts review status |
| 🗑️ | Run deleted | Admin deletes a run |
| 🚀 | Pipeline started | User clicks Generate Estimation |
| 🎉 | Pipeline complete | All 11 agents finish |
| 🧠 | Training updated | New training data added |
| 📧 | Email sent | Email successfully dispatched |
| 📥 | Export done | Download package ready |
| ❌ | Error | Any system error |
| ℹ️ | Info | General system messages |

### Managing Notifications

- **Mark all read** — clears all unread badges
- **Clear all** — removes all notifications from the list
- Last 100 notifications are kept; older ones are auto-pruned

---

## 10. Command Palette

The Command Palette provides keyboard-first access to all major actions.

### Opening the Command Palette

Press **Ctrl+K** (Windows/Linux) or **Cmd+K** (Mac)

### Available Commands

| Command | Action |
|---|---|
| `new estimation` | Scroll to / focus the upload area |
| `run library` | Navigate to Run Library tab |
| `admin` | Navigate to Admin tab |
| `download excel` | Trigger Excel download |
| `download pdf` | Trigger PDF download |
| `download zip` | Trigger ZIP bundle download |
| `clear chat` | Clear the AI chat history |
| `test azure` | Run Azure OpenAI connectivity test |
| `test claude` | Run Claude connectivity test |
| `test gemini` | Run Gemini connectivity test |
| `test qwen` | Run Qwen connectivity test |
| `test vertex` | Run Vertex AI connectivity test |

### Searching Commands

Start typing after opening the palette — results filter in real-time. Press **Enter** to execute the highlighted command, **Escape** to close.

---

## 11. Integrations Setup

### 11.1 SharePoint Integration

Enables loading scope documents from SharePoint and saving proposals back.

**Setup:**
1. In sidebar → **SharePoint** section
2. Enter:
   - **Site URL** — e.g., `https://yourcompany.sharepoint.com/sites/Presales`
   - **Client ID** — Azure AD app registration client ID
   - **Client Secret** — Azure AD app registration secret
   - **Tenant ID** — your Azure AD tenant ID
3. Click **Test SharePoint** — should show ✅

**Azure AD App Registration Requirements:**
- API Permissions: `Sites.ReadWrite.All` (SharePoint)
- Authentication: Client credentials flow

**Using SharePoint:**
- **Load document:** Use the SharePoint file picker in the upload section
- **Save proposal:** Click **Save to SharePoint** in the Downloads section

---

### 11.2 Email Integration (SMTP)

Enables sending proposals directly by email.

**Setup:**
1. In sidebar → **Email** section
2. Enter:
   - **SMTP Server** — e.g., `smtp.office365.com`
   - **SMTP Port** — typically `587` (TLS) or `465` (SSL)
   - **Sender Email** — your email address
   - **Password / App Password** — email account password

**Microsoft 365 Settings:**
```
SMTP Server: smtp.office365.com
Port: 587
Security: STARTTLS
```

**Gmail Settings:**
```
SMTP Server: smtp.gmail.com
Port: 587
Use App Password (not account password)
```

---

### 11.3 Video Narrator Setup

#### HeyGen
1. Sign up at heygen.com and obtain an **API Key**
2. Find your **Avatar ID** from the HeyGen dashboard (avatars section)
3. Find your **Voice ID** from the voices section
4. Enter all three in the sidebar → Narrator section
5. Set **Narrator Mode** to "HeyGen"

#### D-ID
1. Obtain a D-ID API key
2. Enter in sidebar → Narrator → D-ID Key
3. Provide a presenter photo URL (publicly accessible HTTPS image)
4. Set Narrator Mode to "D-ID"

#### ElevenLabs (Voice Only)
1. Obtain an ElevenLabs API key
2. Enter in sidebar → Narrator → ElevenLabs Key
3. Set Narrator Mode to "ElevenLabs"
4. Voice output is audio MP3, no video

---

## 12. AI Model Reference

### Model Selection Guide

| Use Case | Recommended Model |
|---|---|
| Best overall quality | Claude Opus 4.6 or GPT-4o |
| Fastest processing | Claude Haiku 4.5 or Gemini 2.0 Flash |
| Cost-sensitive deployments | Qwen Plus (DashScope) or Gemini Flash |
| Fine-tuned domain models | Qwen Azure AI Foundry (your fine-tune) |
| No API key required | Vertex AI (with GCP project + ADC) |

### Fallback Behaviour

If the preferred LLM fails mid-pipeline, agents automatically fall back in this order:
1. Retry same model (1 attempt)
2. Use static template data with placeholder text
3. Log warning in Run History

The pipeline **never crashes** — you always get a complete output, even if some sections use fallback content (clearly marked with ⚠️).

---

## 13. Training & Continuous Learning

The tool improves its estimates over time by learning from actual project outcomes.

### Recording Actuals

After a project completes:
1. Go to **Run Library**
2. Find the original estimation run
3. Click **Record Outcome**
4. Enter:
   - Actual hours delivered
   - Actual cost
   - Project outcome: Won / Lost / Delivered
   - Variance notes (optional)

### How Learning Works

The system calculates correction factors per:
- Technology category (e.g., "Azure OpenAI integrations run 15% over estimate")
- Project type (AI/ML, Web, Mobile, Cloud)
- Team seniority mix

These correction factors are automatically applied to future estimates.

### Viewing Learning Progress

In the **Admin Panel → Model Performance Dashboard**:
- Accuracy trend over time
- Correction factor table by category
- Runs where variance > 20% (highlighted for review)
- Overall accuracy rating (vs naive baseline)

### Adding Manual Training Data

You can also add historical project data without having run it through the tool:

1. Admin Panel → **Training Data**
2. Click **Add Training Example**
3. Fill in: project type, tech stack, team size, estimated hours, actual hours, date
4. Click **Save** — correction factors update immediately

---

## 14. Troubleshooting

### "API key invalid" Error

- Verify the key is correctly copied (no leading/trailing spaces)
- For Azure: ensure the deployment name exactly matches what's in Azure Portal
- For Qwen Foundry: confirm you're using the **Foundry key** (not DashScope key) and the Source radio is set to **Azure AI Foundry**
- Click **Test [Model]** to see the exact error message

### Pipeline Takes Too Long / Times Out

- Try switching to a faster model (Haiku, Gemini Flash)
- Check your document size — very large documents (>50 pages) may time out; consider summarising first
- Check your network connection to the API endpoint

### Live Azure Pricing Shows $0 or Fails

- The Azure Retail Prices API requires internet access
- If behind a corporate proxy, ensure `prices.azure.com` is whitelisted
- The tool falls back to static 2025 catalog prices automatically — check the tab for a ⚠️ "using cached prices" indicator

### Scenario Modelling Shows Unexpected Results

- Very high scope complexity (2.5×) combined with a large team can produce counter-intuitive results due to Brooks' Law — this is expected behaviour
- Reset to defaults with the **Reset** button to start fresh

### SharePoint "401 Unauthorized"

- Check that the Azure AD app has `Sites.ReadWrite.All` permission
- Ensure the app registration's client secret has not expired
- Verify the Tenant ID matches the SharePoint tenant

### 3D View Not Loading

- Requires WebGL — check browser compatibility
- Try Chrome or Edge (Firefox may have WebGL disabled)
- In corporate environments, WebGL may be blocked by group policy

### Video Generation Fails

- HeyGen: verify Avatar ID and Voice ID are correct (case-sensitive)
- D-ID: image URL must be HTTPS and publicly accessible
- Test Mode generates a shorter clip (cheaper) — enable for testing

---

## 15. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+K` / `Cmd+K` | Open Command Palette |
| `Escape` | Close Command Palette / popover |
| `Enter` | Execute selected command in palette |
| `↑` / `↓` | Navigate command list |
| `Tab` | Move focus between form fields |

---

*ECI Business Estimation Tool — User Manual v2.0*
*For support, contact your ECI platform administrator.*

---
