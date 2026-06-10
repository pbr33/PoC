# ECI Presale Agent ⚡

## AI-Powered Multi-Agent Presales Automation Engine

A production-ready Streamlit application implementing the full ECI Presale Agent architecture with 6 specialized AI agents working in parallel to generate comprehensive presales deliverables.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
streamlit run app.py
```

The app opens at `http://localhost:8501`

---

## 📋 Architecture

### Tab 1 — Presale Agent
- **Document Ingestion** — Upload PDF, DOCX, XLSX, PPTX, TXT, CSV scope documents
- **SharePoint Auto-Trigger** — Monitor a SharePoint folder for new documents
- **10-Step Processing Pipeline:**
  1. Document Ingestion (multi-format extraction)
  2. Document Intelligence (OCR, structure analysis)
  3. GPT-4 Semantic Analysis (requirement extraction)
  4. Historical Data Retrieval (RAG)
  5. Time Estimator Agent (ECI three-point estimation)
  6. Cost Calculator Agent (resource allocation + Azure costs)
  7. Risk Analyzer Agent (5-category risk assessment)
  8. Architecture Designer Agent (Azure Well-Architected)
  9. Scope & Assumptions Agent (clear boundaries)
  10. Proposal Writer Agent (professional document generation)
- **Delivery** — Upload to SharePoint + send alert email

### Tab 2 — Admin & Training
- **Performance Dashboard** — Accuracy trends, agent metrics, model health
- **Training Data** — Upload historical projects, manual entry
- **Fine-Tune Model** — ECI methodology configuration (phases, estimation method, team structure, pricing, risk framework)
- **SharePoint Sync** — Pull historical data from SharePoint libraries
- **Continuous Learning Loop** — Record outcomes, enrich data, retrain, validate, deploy

---

## ⚙️ Configuration (Sidebar)

### Azure OpenAI
- API Key, Endpoint URL, API Version, Deployment Name
- Connects to your Azure OpenAI instance for GPT-4 powered analysis
- **Works without API key** — falls back to intelligent mock data for demo

### SharePoint
- Site URL, Client ID, Client Secret, Tenant ID
- Uses Microsoft Graph API via MSAL for document management

### Email (SMTP)
- SMTP Server, Sender Email, Password
- Sends professional HTML email alerts when proposals are generated

---

## 🧠 ECI Methodology Integration

The system is trained on ECI-specific processes:
- **Project Phases**: Discovery → Design → Development → Deployment → Support
- **Team Structure**: Architect, Lead Dev, Developers, QA, DevOps, PM
- **Estimation**: Three-point (Optimistic, Most Likely, Pessimistic) with weighted averages + buffer
- **Pricing**: Fixed Price, Time & Materials, Retainer
- **Risk Framework**: Technical, Schedule, Resource, Budget, External
- **Quality Gates**: Code Review, Security Scan, Performance Testing, UAT
- **Architecture**: Azure Well-Architected Framework patterns
- **Delivery**: Agile sprints with Scrum ceremonies

---

## 📁 Project Structure

```
eci-presale-agent/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── agents/
│   ├── __init__.py
│   ├── document_processor.py       # Document ingestion & OCR
│   ├── time_estimator.py           # Time estimation agent
│   ├── cost_calculator.py          # Cost calculation agent
│   ├── risk_analyzer.py            # Risk assessment agent
│   ├── architecture_designer.py    # Architecture design agent
│   ├── proposal_writer.py          # Proposal generation agent
│   └── scope_agent.py              # Scope & assumptions agent
└── utils/
    ├── __init__.py
    ├── azure_client.py             # Azure OpenAI API client
    ├── sharepoint_client.py        # SharePoint Graph API client
    ├── email_client.py             # SMTP email client
    ├── styles.py                   # Custom CSS theme
    └── training_manager.py         # ML training pipeline manager
```
