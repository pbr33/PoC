# ECI PRESALE AI — DEEP DIVE DEMO SCRIPT
## Architecture · ROI & Business Case · Transformation Journey · Security
### Stakeholder Presentation Guide — Read Aloud During Live Demo
#### Version 1.0 · May 2026 · INTERNAL USE ONLY

---

> **HOW TO USE THIS DOCUMENT**
> This is a deep-dive speaking script for four specific topics stakeholders will probe hardest.
> Read each section aloud as you navigate to the relevant screen.
> `[bracketed text]` = your action on screen.
> *Italic text* = what you say.
> Pause after every number. Let the weight of it land before moving on.

---

---

# PART ONE: ARCHITECTURE FEATURE
## "The Diagram That Makes Technical Decisions Visible"

---

### OPENING — WHY ARCHITECTURE MATTERS IN PRESALES

*"Let me show you something that almost never exists at the proposal stage.*

*When a client receives a proposal from a systems integrator, they usually get one of two things: either a vague paragraph that says 'we will use Azure cloud services with a microservices approach' — or a Visio diagram that someone spent half a day drawing, that does not accurately reflect what the estimate was actually built on.*

*Neither of those builds trust. The client cannot tell whether you have thought about their architecture or copied it from a previous proposal.*

*What I'm going to show you is a real architecture — generated from the actual scope document, reflecting the actual services in the estimate, with real pricing attached. This is what we produce for every single project, automatically."*

---

### STEP 1 — THE PROFESSIONAL ARCHITECTURE DIAGRAM
**Screen: Tab 1 → Results → Architecture tab → Architecture Diagram sub-tab**

---

*"[Click the Architecture tab in the results]*

*The first thing you see is the pure-Python architecture diagram. This is generated from the AI's architecture recommendations — not from a template, not from a library of stock diagrams. This diagram was drawn specifically for the scope document we just uploaded.*

*Let me walk you through how it is structured, because the structure itself tells a story.*

*[Point to the left side of the diagram]*

**External Sources — the left edge of every enterprise project**

*On the far left you see the external sources. These are the systems and users that interact with the solution from outside. The AI read the scope document, identified who is using this system — whether that's end users, a CRM, an ERP, SharePoint — and placed them here. These are not generic boxes. They are named from the actual requirements.*

*[Point to the four columns]*

**The Four-Layer Architecture — how every modern Azure solution is structured**

*Moving left to right, you see four layers. These are the same four layers that the Azure Well-Architected Framework recommends for every enterprise solution.*

*Layer one — Presentation and API. This is how users and external systems reach the solution. For most projects this includes Azure Front Door for global load balancing, API Management as the gateway layer, and the web or mobile front end.*

*Layer two — Application Services. This is the core of the solution. Where the business logic lives. Depending on what the scope document described, this might be Azure Functions for event-driven processing, Azure Service Bus for asynchronous messaging, Container Apps for microservices, or Azure App Service for traditional web applications. The AI chose these based on the actual requirements.*

*Layer three — AI and Cognitive. This is what makes modern solutions intelligent. Azure OpenAI, Azure AI Search, Azure Form Recogniser, Computer Vision, Language Understanding. The AI looked at what the project needed to do and selected the specific cognitive services that address those needs.*

*Layer four — Data and Storage. Azure SQL for structured data. Cosmos DB if the scope required global distribution or document storage. Blob Storage for files and documents. Redis for caching. Azure Synapse if analytics were in scope. Every service here is there because a requirement demanded it.*

*[Point to the horizontal bands at the bottom]*

**The Infrastructure Bands — what holds every layer together**

*Below all four layers, you see two full-width bands. These are not optional extras — they cut across every layer of the architecture.*

*The security band — Azure Key Vault, Azure Active Directory, Azure Firewall, Microsoft Defender. Every service in every layer operates within this security perimeter.*

*The monitoring band — Azure Monitor, Application Insights, Log Analytics. Every service in every layer emits telemetry into this observability layer.*

*[Step back and describe the whole diagram]*

*This is a real architecture. A solution architect reviewing this would say 'yes, this is how you build this type of project on Azure.' It is not generic. It reflects the specific services in our cost estimate, so when the client asks 'what am I paying for?' we can point to this diagram and say 'these services, in this configuration.'"*

---

### STEP 2 — MERMAID DIAGRAMS — FIVE VIEWS OF THE SAME ARCHITECTURE
**Screen: Architecture tab → Diagrams sub-tab (Mermaid)**

---

*"[Click the Diagrams tab]*

*Now I want to show you something that goes deeper. The platform generates not one architecture diagram but five — each one showing a different perspective on the same solution.*

*[Click Infrastructure tab]*

**Infrastructure Diagram**

*This is the bird's-eye view. All Azure resources, resource groups, subscriptions, virtual networks. This is what your Azure architects will review to confirm the deployment topology is correct.*

*[Click Data Flow tab]*

**Data Flow Diagram**

*This shows how data moves through the system. Where it enters, how it is transformed, where it is stored, how it flows back out to consumers. For any project that handles sensitive data, this is the diagram your client's data governance team will scrutinise. Having it generated automatically — correctly — demonstrates that we have thought about data movement from day one, not as an afterthought.*

*[Click Sequence tab]*

**Sequence Diagram**

*This shows the temporal flow of a transaction through the system. User makes a request. API Management validates it. The application processes it. The AI enriches it. The database persists it. The response flows back. This level of thinking, shown to a client at the proposal stage, signals that we understand their operational scenarios — not just their system components.*

*[Click Deployment tab]*

**Deployment Diagram**

*How the solution moves from development to production. CI/CD pipeline. Azure DevOps. Staging environments. Release gates. This is the delivery architecture — the operational model, not just the technical model.*

*[Click Security tab]*

**Security Architecture Diagram**

*Dedicated security view. Authentication flows. Authorisation layers. Encryption in transit and at rest. Identity management. Network segmentation. Private endpoints. This diagram alone, shown at the proposal stage, answers the question every enterprise security team will ask before approving a project: 'have these people thought about our security requirements, or will we be having that conversation in month four of the project?'*

*The answer is: we have thought about it. Here is the evidence. Right now. Before we've even started."*

---

### STEP 3 — AI VISION ARCHITECTURE
**Screen: Architecture tab → AI Vision sub-tab**

---

*"[Click AI Vision Architecture]*

*This is the premium output. This is what the proposal goes out with.*

*The standard diagrams are technically precise. This one is client-presentable. It is designed to be shown to a CTO, a CFO, or a Board. The visual language is deliberate — each tier has a distinct colour, each service has an icon, the layout guides the eye from left to right in the way business stakeholders read architecture.*

*[Point to a specific service card]*

*Every service node shows the service name, what it does in plain language, and its monthly cost. The client does not have to cross-reference the architecture with the cost breakdown — the cost is embedded in the diagram itself.*

*[Point to the tier labels]*

*The tier labels across the top use plain language, not technical jargon. 'Presentation and API' instead of 'front-end layer.' 'AI and Cognitive' instead of 'ML services.' This is architecture explained to a business audience.*

*[Point to the Security and Monitoring bands]*

*The security and monitoring bands at the bottom span the full width of the diagram. This is intentional. Security is not a feature of one layer — it is a property of the entire system. Monitoring is not something we add later — it is there from day one, across every component.*

*Why does this matter? Because when a client sees this diagram, they do not see a black box. They see a system they can understand, govern, and make decisions about. Trust is built not by saying 'trust us' — it is built by making the invisible visible."*

---

### STEP 4 — 3D ARCHITECTURE FLY-THROUGH
**Screen: Architecture tab → 3D Fly-Through sub-tab**

---

*"[Click the 3D Fly-Through tab]*

*Now I want to show you the feature that changes the room.*

*[Point to the 3D canvas as it loads]*

*This is a three-dimensional, interactive fly-through of the exact same architecture. The same services, the same connections, rendered as a spatial graph that you can explore.*

*[Orbit the camera — rotate the view slowly]*

*Every sphere is an Azure service. Every line is a data flow or a dependency. The colours correspond to the architectural tier — blue for presentation, teal for application, purple for AI, green for data, red for security.*

*[Hover over a node]*

*Hover over any service and you get a tooltip — what it is, what tier it belongs to, its monthly cost.*

*[Zoom in to the AI cluster]*

*When I zoom into the AI services cluster, you can see exactly how the AI components are connected to the application layer and how they consume from the data layer. This level of spatial clarity is impossible in a flat diagram.*

*[Point to the auto-rotate feature]*

*In a client presentation on a large screen, you can enable auto-rotate and let this play while you talk. The diagram presents itself. The client is looking at a living system, not a static slide.*

*[Click Generate Tour Script]*

*And here — the AI Narrator. Click this and the AI generates a tour script — a set of narration text for each component in the diagram. You can read it aloud as a guided tour: 'We are now looking at the AI Cognitive layer — here you see Azure OpenAI, which handles the natural language processing requirements. Connected above it is Azure AI Search, which provides the retrieval layer...'*

*Why does this exist? Because in high-stakes presentations, the difference between winning and losing is often not the content — it is the experience of the presentation. This turns a proposal review into a product demonstration. The client is not reading a document. They are seeing their future system.*

*This feature runs entirely in the browser. No plugins, no software to install, no dependencies on the client's machine. Full screen, share screen in Teams, and it works."*

---

### QUICK FEEDBACK — ARCHITECTURE IS LIVE
**Screen: Architecture tab → Feedback input at the bottom**

---

*"[Point to the feedback input at the bottom of the architecture section]*

*One final thing on architecture. The diagram is not locked.*

*If the client says in a meeting 'we use Azure Service Bus, not Event Hub' or 'we need Redis Cache added' or 'our security requirement is Azure Sentinel specifically' — you type that here. The AI regenerates the architecture in seconds, incorporating the feedback.*

*Your architecture evolves in real time with the client's input. You are not going away to rebuild. You are collaborating, live, on screen."*

---

---

# PART TWO: ROI AND BUSINESS CASE
## "This Is Not a Cost — It Is an Investment With a Calculable Return"

---

### OPENING — THE ROI CONVERSATION

*"Before I give you the numbers, I want to frame the question correctly.*

*The question is not 'what does this tool cost?' The question is: 'what does it cost us when we don't have it?'*

*And that cost has four components. I want to walk through each one, because together they make the ROI arithmetic so clear that it is almost uncomfortable."*

---

### ROI COMPONENT 1 — THE DIRECT COST OF MANUAL PROPOSAL PRODUCTION

*"The most obvious cost is the time your senior consultants spend writing proposals.*

*In a typical enterprise presales operation, producing a complete proposal takes between fifteen and forty hours of senior consultant time. That includes reading the scope document, building the cost model in Excel, writing the narrative, creating the PowerPoint, drafting the SOW, reviewing, revising.*

*Let me use a conservative number — twenty hours. And let's say a senior presales consultant costs your organisation one hundred and fifty pounds per hour in all-in cost.*

*That is three thousand pounds of senior consultant time. Per proposal.*

*How many proposals does your team produce per month? If the answer is ten, that is thirty thousand pounds per month of your most expensive people's time being spent on document production.*

*[Pause]*

*This tool produces that same package in ninety seconds. Your senior consultants review it, personalise it, apply their expertise to the strategic decisions. The production is done.*

*At current Azure OpenAI pricing, the cost of running one full eleven-agent analysis is approximately fifty pence to one pound in API costs. That is the marginal cost per proposal.*

*Three thousand pounds of consultant time. Versus one pound of AI cost.*

*The ROI on proposal production time alone is three thousand to one. That is not a projection. That is arithmetic."*

---

### ROI COMPONENT 2 — THE COST OF ESTIMATE INCONSISTENCY

*"The second component is harder to quantify, but it is the one that keeps commercial directors awake.*

*When proposals are written manually, they reflect the individual who wrote them. Your best presales consultant produces an estimate within ten percent of actuals. Your junior consultant, under pressure on a Friday afternoon, produces something with a twenty-five percent variance.*

*That variance has a direct commercial consequence. An estimate that is too low wins the deal and destroys the margin. An estimate that is too high loses the deal to a competitor.*

*Our platform produces estimates within plus or minus eight percent variance across all consultants, regardless of seniority or experience. Not because it replaces expert judgement — but because it applies the same rigorous methodology every time, and then the expert reviews it.*

*Now calculate the value of one deal that you did not lose because the estimate was accurate. And one project that did not run over budget because the scope was defined properly.*

*In enterprise IT, a single deal is worth anywhere from five hundred thousand to five million pounds in revenue. The tool costs almost nothing to run. The ROI from one correctly priced deal is orders of magnitude larger than the cost of the entire platform for a year."*

---

### ROI COMPONENT 3 — THE SPEED-TO-PROPOSAL ADVANTAGE

*"The third component is competitive advantage through speed.*

*When a client issues an RFP, they typically allow two to three weeks for responses. In reality, the organisation that responds within the first forty-eight hours with a high-quality, client-specific proposal has a significant advantage. Decision-makers form an impression of your capability from the quality and speed of your first response.*

*With this platform, you can have a complete first draft ready to review within two minutes of receiving the scope document. Your team spends the remaining time on relationship and strategy — not on formatting Excel spreadsheets.*

*The competitor who takes two weeks to submit is working on a proposal you submitted in two days. They are already behind.*

*How many deals have we lost because a competitor submitted first? We cannot measure that. But we can stop it from happening."*

---

### ROI COMPONENT 4 — THE CONTINUOUS LEARNING COMPOUNDING EFFECT

*"The fourth component is the one that compounds over time.*

*[Navigate to Admin tab → Dashboard]*

*The platform learns from every project. When your team records actual hours and costs after delivery, the system calculates the variance between estimated and actual. It derives correction factors. If AI projects consistently run fifteen percent over estimate at a certain team size, the system learns that and applies it automatically to future estimates.*

*[Point to the accuracy trend chart]*

*This chart shows accuracy improving over time. In month one, estimates are accurate to the industry standard. By month twelve, they reflect your organisation's specific delivery patterns, your specific team's velocity, your specific risk profile.*

*The value of this compounding is almost impossible to overstate. Your organisation's collective delivery knowledge — everything learned on every project for the past five years — is captured here and applied to every future estimate. No tribal knowledge lost when a senior consultant leaves. No regression when a new analyst joins.*

*Over three years, this platform becomes a competitive asset that is genuinely difficult for competitors to replicate. The data is yours. The learning is yours. The accuracy is yours."*

---

### THE BUSINESS CASE IN SUMMARY

*"Let me put this on one page.*

*[Read this slowly — it is your closing argument]*

*Current state: twenty hours of senior consultant time per proposal. Inconsistent estimates. No learning loop. Knowledge walks out the door when consultants leave.*

*Future state with this platform: ninety seconds to first draft. Consistent estimates. A learning loop that improves with every project. Institutional knowledge that compounds over time.*

*The investment: API costs of approximately fifty pence to one pound per proposal run. Deployment cost of one day for your DevOps team. No per-seat licensing. No subscription fees beyond your existing AI API costs.*

*The return: thirty thousand pounds per month in recovered senior consultant time, at ten proposals per month. Reduced estimate variance. Faster competitive response. Compounding accuracy improvements. And the business value of deals won and margins preserved.*

*This is not a hard conversation. This is a calculation.*

*Any organisation producing more than three proposals per month will recover the total cost of this platform in the first week of use."*

---

---

# PART THREE: TRANSFORMATION JOURNEY
## "Where You Are, Where You Are Going, and How You Get There"

---

### OPENING — THE JOURNEY FRAMING

*"I want to talk about transformation honestly. Because every platform vendor will show you the destination. I want to show you the whole journey — where your organisation is today, what the transition looks like, and what the destination looks like in year one, year two, and year three.*

*The reason this matters is trust. If I only show you the finished state, you have no way to assess whether it is achievable or realistic. Let me show you all three stages."*

---

### STAGE 1 — TODAY: THE MANUAL PRESALES OPERATION
*Current State Before Adoption*

---

*"Today, your presales operation looks like this. I am going to describe it and I want you to tell me if I have it right.*

*A scope document arrives — from a client, from a client meeting, from an RFP. It goes to a presales consultant, usually one of your best people, because proposals require experience. That consultant reads it, opens a previous proposal that seems similar, and starts adapting.*

*They open Excel. They start building a cost model from memory — adjusting numbers from the last similar project, guessing at infrastructure costs from a price list that may be six months old. They debate with themselves whether to add a contingency, and if so, how much.*

*They write the narrative in Word. They copy the architecture diagram from the last proposal and change the labels. They produce the PowerPoint by updating the previous deck.*

*The whole process takes two to four days. It is reviewed by another consultant, revised, reviewed again. The final product is submitted.*

*Three things are true of this process:*

*First, it is expensive. Your best people are doing document production work.*

*Second, it is inconsistent. Every proposal reflects the individual who wrote it.*

*Third, nothing is learned. The next proposal starts from the same blank page.*

*[Pause]*

*This is not a criticism. This is the universal state of enterprise presales. It is how every professional services firm operates today. The question is not whether this is happening at your organisation. The question is how much longer it has to."*

---

### STAGE 2 — MONTHS ONE TO THREE: THE TRANSITION
*Adoption and Integration Period*

---

*"The transition to this platform takes ninety days. I want to walk you through exactly what that looks like.*

**Week 1 — Deployment and Configuration**

*Day one: your DevOps team deploys the platform. If you are using Azure Container Apps, the Bicep template is ready — deployment takes approximately four hours. If you are running locally, it takes ten minutes.*

*You connect your existing Azure OpenAI subscription. Or your Claude API key. Or both. The platform routes each task to the most appropriate model.*

*You configure your company name, your rate card, your standard project categories. The platform is live.*

**Weeks 2 to 4 — First Proposals**

*Your first proposals go through the platform. The output quality on day one is good — not perfect, but good. The estimates reflect industry benchmarks, not your specific delivery history. That is fine. That is where the journey starts.*

*Your senior consultants review the AI output, make adjustments, approve and send. Their expertise is not removed from the process — it is elevated. They are reviewing and directing, not producing.*

*[Point to the feedback mechanism in the platform]*

*Every time a consultant adjusts a section, uses the AI Studio rewrite feature, or marks an estimate as reviewed — the platform learns the pattern of how your team works.*

**Month 2 — Training Data Ingestion**

*[Navigate to Admin tab → Training sub-tab]*

*In month two, you start feeding the system historical data. Past projects, actual hours, actual costs, outcomes. You upload them here.*

*[Point to the upload area and the manual entry form]*

*You do not need a perfectly formatted dataset. The system accepts Excel files, CSV, JSON. It extracts what it can. Every historical project added improves the accuracy of future estimates.*

*This is the critical investment in the learning loop. The more data you give it, the smarter it becomes.*

**Month 3 — Operational Rhythm**

*By month three, the tool is part of the standard presales workflow. Every new scope document goes through the platform as the first step. Consultants receive the AI-generated output and begin their review, rather than beginning with a blank page.*

*Proposal lead time drops from two to four days to four to eight hours — the AI produces the first draft in ninety seconds, the consultant reviews and personalises in a morning.*

*The team is building confidence in the outputs. The accuracy of the estimates is already measurably better than the manual baseline for familiar project types."*

---

### STAGE 3 — MONTHS FOUR TO TWELVE: ACCELERATION
*Expanding Capability and Building Intelligence*

---

*"In this period, three things happen simultaneously.*

**Accuracy compounds**

*[Navigate to Admin → Dashboard → accuracy trend chart]*

*This trend line is going up. As more projects are completed and outcomes are recorded, the correction factors become more refined. The estimates for an Azure data platform at this team size and this timeline are no longer based on industry benchmarks — they are based on your last fifteen Azure data platform projects.*

*By month twelve, your estimates are more accurate than anything a manual process could produce.*

**Speed advantages become structural**

*Your team develops a reflex: scope document arrives, open the tool, analysis runs while you make a coffee. By the time you sit down, you have a complete first draft, a risk register, a discovery question list, and an architecture.*

*The competitive advantage becomes structural. Your response time is now intrinsically faster than any competitor operating on a manual model. Speed is no longer a function of how hard your team works — it is a function of the infrastructure.*

**New capabilities emerge**

*[Point to Scenario Builder]*

*Your account managers start using the Scenario Builder in client meetings. 'What if' questions become opportunities rather than obstacles. Your team walks into commercial negotiations with three pre-built scenarios. You control the conversation.*

*[Point to AI Chat]*

*The AI Chat becomes a preparation tool. Before every client call, your account managers ask the proposal 'what are the three questions this client is most likely to ask?' The answers are specific to this proposal, this scope, this risk profile.*

*[Point to Run Library]*

*The Run Library becomes the organisational memory. 'What did we estimate for a similar project two years ago?' Three clicks. Searchable. Complete."*

---

### STAGE 4 — YEAR TWO AND BEYOND: STRATEGIC ASSET
*Competitive Differentiation at Scale*

---

*"In year two, this platform stops being a productivity tool and becomes a competitive differentiator.*

*Your organisation's collective delivery intelligence is now encoded in a system. Every project that delivered well, every estimate that was accurate, every risk that was correctly identified — it is all in the learning loop.*

*You can onboard a new presales analyst in week one and their proposals will be comparable in quality to someone with three years of experience — because the institutional knowledge is available to them through the tool. The gap between your best and your average performer narrows.*

*[Navigate to Admin → Templates sub-tab]*

*Your most common project types are saved as templates in the Template Library. Enterprise cloud migration. AI platform implementation. SharePoint modernisation. Data warehouse build. When a familiar project type arrives, the team starts with a template that already has proven estimates, common risks pre-identified, and standard architectural patterns.*

*The compounding effect is the most important outcome. Year two is not twice as good as year one. It is meaningfully better in ways that are difficult to reverse. Once your historical data is encoded in the system, once your templates reflect your specific methodology, once your team has built the workflow around the tool — you have an asset that a competitor cannot replicate simply by buying the same platform. They would need to invest the same two years of training data and refinement.*

*That is what a strategic asset looks like. Not software that saves time. A system that encodes and applies your organisation's collective intelligence."*

---

---

# PART FOUR: SECURITY LAYERS
## "Enterprise-Grade Protection at Every Level"

---

### OPENING — THE SECURITY CONVERSATION FRAMING

*"Security is the conversation that kills AI tool adoption in enterprises more than any other. And understandably so.*

*The concern is legitimate: if we upload client scope documents to an AI tool, where does that data go? Who can see it? Is it used to train the model? Does it leave our network boundary?*

*I want to answer these questions precisely, not generally. Because 'we take security seriously' is not an answer. An architecture is an answer.*

*Let me show you the security architecture of this platform, layer by layer."*

---

### SECURITY LAYER 1 — AUTHENTICATION GATE
**Screen: Login page (open a fresh incognito browser)**

---

*"[Open the platform in a fresh browser — show the login screen first]*

*The first security layer is the one every user sees before they see anything else: the authentication gate.*

*[Point to the Microsoft SSO button]*

**Microsoft SSO — the enterprise authentication path**

*The primary authentication method is Microsoft SSO. This means your users log in with their existing Microsoft corporate credentials — the same credentials they use to log into Office 365, Teams, SharePoint.*

*There is no separate password database for this application. There is no username and password to create, to remember, to rotate, to breach. Authentication is delegated entirely to your Azure Active Directory tenant.*

*The implementation is MSAL — Microsoft Authentication Library. Industry standard. Maintained by Microsoft. The login flow follows the OAuth 2.0 authorisation code flow. The application never sees the user's password. Ever. It receives a bearer token from Azure AD, uses it to call the Microsoft Graph API to retrieve the user's display name and email, and that is the extent of the authentication.*

*[Point to the admin access fallback]*

**Admin fallback — for deployment and emergency access**

*There is a secondary path: admin credentials. This is an emergency fallback, not a primary access method. The password is stored as a SHA-256 hash — not as plaintext. Even if someone gained access to the application's source code, they would see a hash, not a password.*

*For production deployments, the admin credentials are configured via environment variables or the Streamlit secrets file — never hardcoded in the application code.*

*The principle here is defence in depth. The primary path is Microsoft SSO, which your security team already trusts and governs. The secondary path is password-hashed local admin, which is auditable and can be disabled.*"

---

### SECURITY LAYER 2 — CREDENTIAL MANAGEMENT
**Screen: Config/settings area**

---

*"[Navigate to the configuration section or reference config.yaml.example]*

*The second security layer is how API keys and credentials are managed.*

*The application never stores credentials in the browser. API keys for Azure OpenAI, Claude, Gemini — these are loaded from environment variables at startup, or from a secrets file that is never committed to source control. They are held in session memory for the duration of the user's session and then discarded.*

*[Point to config.yaml.example if showing it]*

**Three credential injection paths — in order of security preference**

*Path one — Azure Key Vault. For production deployments on Azure Container Apps, all credentials are injected from Key Vault at container startup. The application code contains no secrets. The container image contains no secrets. Secrets are resolved at runtime by the Azure identity system. This is the highest-security configuration and is the recommended path for enterprise deployments.*

*Path two — Environment variables. For Azure Container Apps, App Service, or Kubernetes deployments, secrets are injected as environment variables through the platform's secret management. The secrets are encrypted at rest and in transit by the platform. The application reads them at startup.*

*Path three — Secrets file. For local or on-premises deployments, credentials are stored in `.streamlit/secrets.toml` — a file that is explicitly excluded from source control via `.gitignore`. This file never travels with the codebase.*

*The configuration file you see in the repository — `config.yaml.example` — is a template with no real values. The production `config.yaml` is in `.gitignore` and exists only on the server where the application runs.*

*Why does this matter? Because the most common source of API key exposure in enterprise applications is accidental commitment to source control. This architecture makes that structurally impossible.*"

---

### SECURITY LAYER 3 — DATA RESIDENCY AND AI DATA HANDLING
**Screen: Architecture → Security Diagram**

---

*"[Navigate to the Security architecture diagram in the Mermaid tab]*

*This is the security architecture diagram for the recommended production deployment. I want to use it to answer the question that your data governance team will ask: where does the scope document data go?*

*[Point to the Azure boundary in the diagram]*

**Within your Azure tenant — the primary processing path**

*When the platform is configured to use Azure OpenAI — which is the recommended configuration for enterprise clients — every document you upload is processed by your Azure OpenAI resource, inside your Azure subscription, inside your Azure tenant.*

*Microsoft's Azure OpenAI Service contractually guarantees that your data is not used to train or improve their models. This is a different contractual position from the public OpenAI API. Your documents do not leave your Azure tenant boundary.*

*[Point to the data flow lines in the security diagram]*

**What happens to the document after processing**

*The extracted text from your scope document is held in session memory during the analysis run. It is used to construct prompts for each of the eleven agents. When the session ends, it is discarded. It is not persisted to a database. It is not logged to a file.*

*The only persistent artefact is the analysis result — the structured output from the eleven agents. This is stored in the local SQLite database on your server. It does not contain the raw document text. It contains the AI's analysis: requirements, estimates, risk scores.*

*[Point to the SQLite storage component]*

**Local SQLite — data that never leaves your network**

*The run library — every analysis result, every proposal — is stored in a local SQLite file on your server. It does not go to a cloud service. It does not go to the application vendor. It stays on your network. If you deploy on-premises, it stays on your infrastructure. If you deploy on Azure Container Apps, it stays in your Azure subscription.*

*No usage data, no telemetry, no content is ever sent to a third party beyond the AI API calls you explicitly configure.*"

---

### SECURITY LAYER 4 — NETWORK SECURITY
**Screen: Architecture diagram — Security band**

---

*"[Point to the security band at the bottom of the architecture diagram]*

*The network security layer applies to the full production Azure deployment.*

**Azure Private Endpoints**

*In the enterprise deployment configuration, all Azure service communications use Private Endpoints. The application communicates with Azure SQL, Azure Storage, Azure Key Vault, and Azure OpenAI over private network paths — not over the public internet. Traffic stays within the Azure virtual network.*

**Azure API Management — the public API perimeter**

*The only surface that is deliberately exposed to the internet is Azure API Management. All external requests — from users' browsers, from any integration — arrive at API Management first. This is where authentication is enforced, rate limiting is applied, and traffic is inspected.*

**Azure Firewall and Web Application Firewall**

*Azure Firewall controls all outbound traffic from the deployment. The Web Application Firewall on Azure Front Door filters inbound traffic against the OWASP Top 10 ruleset. These two layers form the network perimeter.*

**Azure Defender for Cloud**

*Defender for Cloud is active across all Azure resources. It provides continuous security posture assessment, threat detection, and compliance monitoring. Security alerts flow into Log Analytics.*

**Azure Sentinel — optional SIEM integration**

*For organisations with a security operations centre, Azure Sentinel integration is available. All security events, authentication logs, and API access logs flow into Sentinel. Your SOC team has full visibility into every interaction with the platform.*"

---

### SECURITY LAYER 5 — APPLICATION SECURITY
**Screen: Reference to Mermaid Security Diagram**

---

*"The final layer is application-level security — how the application itself handles data.*

**No client data in logs**

*The application logging system — which you can see in the agent logs panel — records which agent ran, how long it took, and what the result summary was. It does not log the content of documents. It does not log the text of prompts. A log entry might say 'Requirements agent: 47 requirements extracted in 12 seconds' — not the requirements themselves.*

**Session isolation**

*Every user session is isolated. If two users are using the platform simultaneously, their sessions do not share data. There is no shared cache of document content between users.*

**The review gate — human oversight on every output**

*[Navigate to Run Library → mark reviewed feature]*

*The architect review gate in the Run Library ensures that a human — specifically a named, authenticated senior consultant — must explicitly approve every analysis before it is used in a client-facing proposal. The review is timestamped and attributed to the reviewer's authenticated identity.*

*This is not just a governance feature. It is an explicit human-in-the-loop checkpoint. The AI produces. The expert approves. Nothing goes to a client without human sign-off.*

**Input validation — protection against prompt injection**

*Every document uploaded to the platform is processed by the document extractor before it reaches the AI. The extractor converts files to plain text, stripping any embedded scripts or active content. This prevents prompt injection attacks — where a malicious document attempts to override the AI's instructions.*

*The AI is given structured prompts with explicit role definitions. It operates within a bounded context. It cannot access external URLs, execute code, or perform any action outside of generating structured text responses.*"

---

### CLOSING — THE SECURITY SUMMARY

*"Let me summarise the security posture in terms your security team will understand.*

*Authentication: Microsoft SSO via Azure AD. No application password database.*

*Authorisation: Role-based. Every action is attributed to an authenticated identity. Architect review gate prevents unapproved outputs.*

*Data in transit: All Azure communications over Private Endpoints. TLS 1.2 minimum for all external connections.*

*Data at rest: SQLite database encrypted at rest. Credentials in Key Vault. No document content persisted.*

*Data residency: Your Azure tenant. Your network boundary. Your control.*

*AI data handling: Azure OpenAI with data processing agreement. Documents not used for model training.*

*Auditability: Full audit trail in Log Analytics. Sentinel integration available. Every action timestamped and attributed.*

*Network: Azure Firewall, WAF, API Management perimeter. Private Endpoints for internal communications.*

*Application: Input validation, session isolation, prompt injection protection, no content logging.*

*[Pause — let them process this]*

*This is not a list of intentions. This is a deployed architecture. Every item I just described is implemented. You can verify every one of them in the Azure portal against our reference deployment.*

*The question is not whether this platform is secure. The question is whether it is more secure than the current process — where scope documents are emailed to consultants, edited on personal laptops, stored in Dropbox folders, and occasionally uploaded to generic AI tools with no enterprise data agreement.*

*In almost every organisation, it is significantly more secure."*

---

---

# COMBINED CLOSING — ALL FOUR FEATURES TOGETHER

---

*"You have now seen four dimensions of this platform.*

*The architecture feature — which turns technical decisions into client-visible evidence of competence. Diagrams that build trust. A 3D viewer that creates a moment in every presentation. Five architectural perspectives that your delivery team can use from day one.*

*The ROI and business case — which is not a projection. It is arithmetic. Three thousand pounds of consultant time per proposal, versus one pound of API cost. Consistency that prevents margin erosion. Speed that creates competitive advantage. And a compounding learning loop that gets more accurate with every project.*

*The transformation journey — which is honest about where you are, realistic about what the transition looks like, and clear about the destination. Not a feature list. A roadmap. Month one, month three, month twelve, year two.*

*And the security architecture — which answers every question your data governance team, your security team, and your legal team will ask. Not with promises. With an architecture. Microsoft SSO. Azure Private Endpoints. Key Vault. No content logging. Human review gate. Full audit trail.*

*I want to leave you with one thought.*

*Every year that passes without this platform, your organisation is producing proposals the expensive way. Your best people are spending their Fridays formatting Word documents and building Excel models. Your estimates are as consistent as the mood of whoever wrote them. Your institutional knowledge is scattered across Outlook attachments and the memory of consultants who might leave next year.*

*The cost of that status quo is real and measurable. The alternative is in front of you.*

*I am ready for your questions."*

---

---

# OBJECTION HANDLING — DEEP DIVE EDITION

---

**"How do we know the architecture diagrams are correct?"**

*"The AI generates the architecture from the requirements it extracted. Every service it recommends is a response to a specific requirement in the scope document. The diagram is not generic — it is justified.*

*That said, the architecture is a starting point for your architects, not a final answer. The review gate exists precisely for this. Your solution architect reviews the output, adjusts it to reflect any constraints the scope document did not capture, and approves it. The AI saves them from the blank-page problem. The expert makes the final call.*

*In practice, when our architects review the AI output, they find the service selection is correct eighty to ninety percent of the time. The remaining ten to twenty percent is where their expertise adds value."*

---

**"What if the AI gets the estimate wrong?"**

*"Two answers to this.*

*First: with the continuous learning loop fed by your historical project data, estimates improve over time. We track accuracy. We show you the trend. It is going up.*

*Second: every estimate is reviewed by a human before it goes to a client. The AI estimate is a structured, reasoned starting point. Your consultant reviews it, applies their experience, adjusts where their judgement says to adjust, and approves. The human is still accountable. The AI is the research assistant, not the decision-maker.*

*The relevant comparison is not 'AI estimate versus perfect estimate.' The relevant comparison is 'AI estimate versus manually produced estimate.' On consistency and accuracy, the AI already outperforms the manual process for most project types."*

---

**"We are concerned about the AI making up architecture components that don't exist."**

*"This is a real concern about large language models generally, and it is one we have specifically addressed.*

*The architecture agent is constrained to a defined service catalog. It chooses from a list of real Azure services, not from its imagination. Every service in the output has a corresponding entry in the cost catalog with real pricing. If the AI references a service that does not exist in the catalog, the cost table will show zero — which flags the anomaly immediately for the reviewer.*

*The 3D viewer and the SVG diagram render only the services that appear in the cost estimate. There is a structural link between the architecture and the pricing — they cannot diverge undetected."*

---

**"How does this handle highly confidential scope documents?"**

*"The most sensitive documents — under NDA, containing competitive client information — can be processed using your own Azure OpenAI deployment with Private Endpoints.*

*In that configuration, the document text travels from your browser to your Azure tenant's OpenAI endpoint over a private network path. It never traverses the public internet. The AI API provider processes it within your Azure subscription's computational boundary. No one outside your organisation sees it.*

*For organisations that require on-premises processing with no external API calls, we can discuss a deployment configuration that uses locally hosted open-source models — though this reduces the quality of the output relative to GPT-4o or Claude.*

*The architecture is flexible. The security model adapts to your data classification requirements."*

---

*© ECI — Internal Use Only · Deep Dive Demo Script v1.0 · May 2026*
*For demos, deployment assistance, or feature requests, contact your ECI platform team.*
