# ECI PRESALE AI — STAKEHOLDER DEMO SCRIPT
### Full Feature Walkthrough — Read Aloud During Live Demo
#### Version 1.0 · May 2026 · INTERNAL USE ONLY

---

> **HOW TO USE THIS DOCUMENT**
> This is your speaking script. Every section maps to something visible on screen.
> Read the sections in order as you click through the tool.
> Words in *italics* are what you say. Words in **[brackets]** are your actions.
> Take a breath between sections. Pause after a key number — let it land.

---

---

# OPENING — BEFORE YOU CLICK ANYTHING

---

*"What I'm going to show you today is not another AI tool that helps you write faster. What I'm going to show you is a system that replaces the most expensive, most inconsistent, and most soul-destroying part of our presales process entirely.*

*Right now, when a client sends us a scope document, one of our best consultants disappears for two days. They come back with a proposal. That proposal is brilliant — but it is one person's interpretation, one person's mental model, one person's risk appetite. And if that person is having a bad week, or is under-caffeinated, the estimate reflects that.*

*What if we could have eleven senior specialists review every scope document, simultaneously, every time, with zero fatigue? That is exactly what this platform does. Let me show you."*

---

---

# FEATURE 1 — DOCUMENT INGESTION
### Screen: Tab 1 — Presale Agent · Upload Section

---

*"The first thing you see when you open the tool is the upload zone. This is where it all begins.*

*You can drop in any document format a client might send us — PDF, Word, Excel, PowerPoint, plain text, CSV. All of them. You don't need to convert anything, you don't need to copy-paste content, you don't need to pre-process the file.*

*[Upload the sample scope document]*

*The moment the file lands, the system reads it. It uses OCR for scanned documents, structural parsing for Excel files, and semantic chunking for long Word documents. It doesn't just read words — it reads the meaning of those words in context.*

*Why does this matter? Because the number one failure mode in presales is someone missing a requirement buried on page fourteen of a badly formatted PDF. This system reads every line, every footnote, every table. Nothing gets missed.*

*In a typical presales workflow, document preparation and extraction alone takes thirty to sixty minutes of a senior consultant's time. We have just done that in about three seconds."*

---

---

# FEATURE 2 — REQUIREMENTS COMPLETENESS CHECKER
### Screen: Completeness checker section (appears after file upload)

---

*"Before we even run the main analysis, the tool does something that I think is one of the most valuable features here — it checks whether the scope document you just uploaded is actually complete.*

*[Point to the completeness checker output]*

*It runs through the document and categorises every requirement it finds into three buckets. Green — clearly defined, no questions needed. Amber — partially described, we need clarification before we price it. Red — critical gap, something that must be answered before we submit.*

*Let me give you a real example of why this matters. Three months ago, a team submitted a detailed, impressive proposal for a data migration project. The scope doc never mentioned the existing data quality. They priced it based on a clean migration. The actual data was a disaster. The project ran forty percent over budget.*

*The completeness checker would have flagged data quality assessment as a critical gap before that proposal ever went out.*

*This is your quality gate. It runs automatically, before anything else, every single time."*

---

---

# FEATURE 3 — MULTIMODAL DISCOVERY EXTRACTION
### Screen: Discovery Extraction section — transcript upload

---

*"Now, not every engagement starts with a formal scope document. A lot of times, the first thing we have is a recording of a discovery call. Someone exports the Teams transcript. Someone has meeting notes in a Word doc. Someone recorded a voice memo on their phone.*

*[Point to the transcript upload area]*

*This section handles all of that. You can upload Teams or Zoom transcripts — the raw VTT or SRT subtitle files, JSON exports, meeting minutes as Word documents, or just plain text notes.*

*[Upload a sample transcript]*

*[Click Analyze Transcripts]*

*Watch what happens. The system reads the conversation. It is not just doing keyword search — it is understanding the dialogue. It identifies who is speaking, what they are asking for, what they are complaining about, and what they are afraid of.*

*The output you see here — the Pain Points, the Requirements list, the Stakeholder map, the WBS — this is identical in quality to what you would get from running a full scope document through the main pipeline. Because from the system's perspective, a transcript of a client saying 'we need real-time inventory visibility across all warehouses' is a requirement. It doesn't matter whether that came from a Word doc or a conversation.*

*And here — [point to the Run Full Analysis button] — with one click, you can push everything the system just learned from the transcript straight into the full eleven-agent pipeline. No copy-paste. No reformatting. The transcript becomes the scope document."*

---

---

# FEATURE 4 — THE 11-AGENT PIPELINE
### Screen: Run button — then pipeline progress

---

*"This is the moment. Let me show you what happens when you press this button.*

*[Click: PROCESS & GENERATE ESTIMATES]*

*Eleven agents are now running simultaneously. I want to walk you through what each of them is doing right now, because understanding this is what makes this tool different from every other AI tool in the market.*

**Agent 1 — Requirements Analyst**
*This agent reads the entire document and extracts every functional requirement, non-functional requirement, integration point, compliance constraint, and assumption. It categorises them, prioritises them, and gives each one a complexity score. By the end, we have a structured requirements register that would normally take a business analyst half a day to produce.*

**Agent 2 — Time Estimator**
*This agent applies our three-point estimation methodology — Optimistic, Most Likely, Pessimistic — to every component of the project. It calculates weighted averages with a risk buffer. It breaks the timeline into phases: Discovery, Design, Development, Deployment, Support. It knows which tasks can run in parallel and which are sequential. It produces a Gantt-compatible timeline.*

**Agent 3 — Cost Estimator**
*This agent turns hours into money. It maps every role to our rate card, applies location-based rates for India and UK teams, adds infrastructure costs, factors in contingency, and produces a phase-by-phase cost breakdown. Not a guess — a structured model.*

**Agent 4 — Risk Analyst**
*This agent identifies and scores every risk in five categories: Technical, Schedule, Resource, Budget, and External. For each risk it generates a likelihood score, an impact score, a composite risk rating, and a mitigation strategy. It produces a full risk register that a delivery team can use from day one.*

**Agent 5 — Architecture Designer**
*This agent recommends the technical solution. It follows the Azure Well-Architected Framework. It specifies which Azure services to use, why, and in what configuration. It is not generic — it reads the requirements and designs for this specific project.*

**Agent 6 — Infrastructure Pricer**
*This agent takes the architecture from Agent 5 and fetches live prices from the Azure Retail Prices API. Not estimates from a price list we updated six months ago — actual prices from Microsoft's live API, pulled at the moment of this run. Every recommended service gets a real monthly and annual cost.*

**Agent 7 — Scope & Assumptions Agent**
*This agent defines the exact boundary of the work. What is in scope. What is explicitly out of scope. What assumptions we are pricing on. This is the section that protects us legally and commercially if a client comes back six months later saying 'but we assumed you'd include that.'*

**Agent 8 — SOW Generator**
*This agent produces a Statement of Work — structured with milestones, deliverables, acceptance criteria, and payment triggers. This goes straight to legal review. It saves our contracts team two to three hours per engagement.*

**Agent 9 — Discovery Engine**
*This agent reads every gap and ambiguity in the scope document and generates a prioritised list of questions we should ask the client before we commit to a price. Organised by category. Phrased professionally. Ready to put in front of the client.*

**Agent 10 — Completeness Checker**
*This agent does a final cross-check — are all requirements covered by the proposed solution? Are there any contradictions? Any implicit assumptions that were never stated explicitly?*

**Agent 11 — Proposal Writer**
*This agent takes everything all the other agents produced and turns it into a client-ready narrative. An executive summary. A problem statement. A proposed solution. A team overview. Investment justification. This is the document that goes in front of the CTO or the CFO.*

*[Pipeline completes]*

*Eleven specialists. Every time. In ninety seconds. This is what consistency looks like."*

---

---

# FEATURE 5 — ESTIMATION RESULTS
### Screen: Results — Time Estimation & Cost Breakdown

---

*"Let me show you what we just produced.*

*[Scroll to the Time Estimation section]*

*Three-point estimates for every component. Optimistic, Most Likely, Pessimistic. Weighted averages. A buffer. A total. Phase breakdown. And a timeline — when does each phase start, when does it end, what are the dependencies.*

*[Scroll to the Cost section]*

*Phase-by-phase cost breakdown. Role by role. Hours by role. Internal cost. Billed cost. Infrastructure. Total. This is defensible. When a client asks 'why does Phase 2 cost this much?' we can answer that question line by line.*

*[Point to Excel download]*

*And all of this exports to Excel in one click. Five sheets: Cost Breakdown, Timeline, Risk Register, Infrastructure Costs, Summary Dashboard. The format our finance teams already know.*

*Why does this matter? Because consistency. The estimate for this project is the same whether I run it or whether our most junior presales analyst runs it. It is the same on a Monday morning and on a Friday afternoon. The human contribution is reviewing and refining — not producing from scratch."*

---

---

# FEATURE 6 — RISK REGISTER
### Screen: Risk section in results

---

*"The risk register. Every project has risks. Most proposals acknowledge that risks exist. This one tells you exactly what they are.*

*[Point to the risk cards]*

*Each risk has a category — Technical, Schedule, Resource, Budget, External. A likelihood rating. An impact rating. A composite score that tells us whether this is a monitor, a manage, or a stop-and-resolve issue. And a mitigation strategy.*

*The reason this matters commercially is simple. When we go into a commercial negotiation and the client says 'your price is too high,' we can open the risk register and say 'here are the twelve risks on this project. We have priced for them. Here is what we are doing to mitigate each one. If you want to reduce the price, here is which risks you are choosing to accept.'*

*That is a very different conversation than 'well, we added a contingency.'*

*This register is also the starting point for the delivery team's RAID log. We are not throwing this away after the deal is won — we are handing it over as a project artefact."*

---

---

# FEATURE 7 — ARCHITECTURE & AI VISION
### Screen: Architecture tab

---

*"The architecture section. Two views — the Mermaid diagram and the AI Vision.*

*[Click the Architecture tab]*

*The Mermaid diagram shows you the technical architecture as a flow diagram. Services, connections, data flows. Clean, professional, client-presentable.*

*But let me show you the AI Vision view. [Click AI Vision Architecture]*

*This is our premium architecture output. The AI doesn't just name Azure services — it designs the actual solution topology. Here you can see the component layers: the presentation layer, the API layer, the data layer, the AI services layer, the security perimeter. Every service is labelled with its purpose and its estimated monthly cost.*

*Why does this matter for presales? Because the number one reason technical proposals fail to convince non-technical stakeholders is that the architecture is explained in words. You say 'we'll use a microservices architecture with Azure Container Apps and Azure SQL' and the CFO's eyes glaze over.*

*This diagram says the same thing visually. They see it, they understand it, they trust it.*

*And the 3D viewer — [point to 3D flythrough option] — takes that one step further. Interactive. Rotatable. Every node is a service. Every edge is a data flow. In a boardroom presentation, this is a genuine showstopper. I have seen CFOs lean forward in their chairs when they see this for the first time."*

---

---

# FEATURE 8 — PROPOSAL DOCUMENT
### Screen: Proposal Document tab

---

*"Now the proposal itself. [Click the Proposal Document tab]*

*This is a full, client-ready proposal document. Executive summary. About ECI. Understanding of your requirements. Our proposed solution. Team structure. Timeline. Investment summary. Next steps.*

*This is not a template with our company name inserted. The AI wrote this specifically for this scope, this client, this project. Read the executive summary — it references specific requirements from the document we uploaded.*

*[Scroll through the sections]*

*Each section is independent. You can edit any section without touching the others. [Click Edit on a section]*

*The text area is live — type your changes, click Save, the section updates. If you don't like your edit, Reset puts it back to the AI original.*

*But the most powerful tool here is AI Studio. [Click AI Studio on a section]*

*This opens a rewrite interface. You type an instruction — 'make this more concise,' 'add emphasis on ROI,' 'rewrite this for a technical audience,' 'strengthen the risk section' — and the AI rewrites that section according to your instruction. Streaming, in real time, you see it appear word by word.*

*You are not replacing the AI with human writing. You are directing the AI like a senior editor directs a writer. Your expertise tells it what to do. It does the work.*

*The preview — [point to the HTML preview] — shows you exactly what the client will see. What you are editing is what they receive."*

---

---

# FEATURE 9 — PROPOSAL PERSONALISATION
### Screen: Personalisation bar above proposal

---

*"Before we export, there are personalisation controls above the proposal.*

*[Point to the personalisation bar]*

*Client name. Our name. Tagline. Tone of voice — consultative, technical, executive, bold. Colour scheme — matched to the client's brand if we want.*

*These flow through the entire document. Change the client name here and it updates everywhere. Change the tone and the AI rewrites all section headers and transitions to match that register.*

*Why does this matter? Because the difference between a proposal that wins and a proposal that doesn't is often not the price — it is whether the client felt that we understood them. A proposal that uses their language, their name, their colour palette says 'we thought about you specifically.' This feature makes that effortless."*

---

---

# FEATURE 10 — PRESENTATION (PPTX)
### Screen: Presentation tab

---

*"[Click the Presentation tab]*

*The same content, automatically formatted as a PowerPoint deck. Ten slides. Cover page. Executive Summary. Problem Statement. Proposed Solution. Architecture. Team. Timeline. Commercials. Risk Summary. Next Steps.*

*[Click Download PPTX]*

*This is a file you can open in PowerPoint right now. Your account manager can walk into a client meeting with this. It is not a design masterpiece — it is a solid, professional, branded deck that communicates the proposal clearly.*

*The alternative is a junior consultant spending four hours in PowerPoint. That is what we have just replaced."*

---

---

# FEATURE 11 — STATEMENT OF WORK
### Screen: SOW tab

---

*"[Click the Statement of Work tab]*

*Legal-structured SOW. Parties. Background. Scope of Services. Deliverables. Milestones with payment triggers. Acceptance criteria. Change management process. Limitations of liability. Governing law.*

*[Point to the download button]*

*This goes to our contracts team as a first draft. They review, they adjust the legal language, they send. What used to be a two-hour job for a senior contracts manager is now a thirty-minute review.*

*The milestone and payment schedule is generated directly from the timeline — so the commercial terms align with what we actually committed to deliver. This sounds obvious, but it is shockingly rare in manually produced proposals."*

---

---

# FEATURE 12 — DISCOVERY QUESTIONS
### Screen: Discovery tab in results

---

*"[Navigate to the Discovery Questions section]*

*Before every client meeting, our presales team should be walking in with a prepared list of questions. Not ad hoc questions — structured, prioritised, categorised questions that fill the gaps in the scope document.*

*This section generates exactly that. Grouped by category. For each question: why we're asking it, what the risk is if we don't get an answer, and what a good answer looks like.*

*[Point to download button]*

*Download this as a PDF. Give it to the account manager the night before the meeting. They walk in prepared. They ask better questions. They come out with better information. That information makes the next iteration of the proposal more accurate.*

*This is the intelligence preparation step that most presales teams skip because they don't have time. We just made it automatic."*

---

---

# FEATURE 13 — SCENARIO MODELLING
### Screen: Scenario Builder tab

---

*"[Click the Scenario Builder tab]*

*This is the feature that changes your commercial conversations.*

*Right now, when a client says 'what if we reduce scope by thirty percent?' your answer is 'let me come back to you with a revised estimate.' You go away, spend four hours rebuilding the spreadsheet, send an email, wait for a response. You've lost momentum.*

*With the Scenario Builder, you answer that question in the room.*

*[Adjust the scope lever]*

*Watch the numbers change. Total hours. Total cost. Timeline. Margin. All recalculating live as I move this slider.*

*[Adjust the team lever]*

*Add engineers. Change the seniority mix. Notice that adding more people doesn't just proportionally reduce time — the system applies Brooks' Law. It knows that a team of ten cannot do the same work as five people in half the time. There is coordination overhead. It models that.*

*[Create a second scenario]*

*Now I have two scenarios side by side. Option A: Full scope, twelve months, this price. Option B: Reduced scope, eight months, twenty percent less. Option C: Accelerated timeline with a larger team, premium cost.*

*[Point to the radar chart]*

*The radar chart shows all three scenarios on six dimensions simultaneously — cost, time, team size, risk, complexity, coverage. Your client sees the trade-offs visually. They are not comparing rows in a spreadsheet. They are making a decision.*

*[Export comparison]*

*One click — export this comparison as a professional Excel document. Hand it to the client. Let them take it back to their finance team.*

*I have spoken to presales directors who say this single feature changed how they handle negotiations. They used to dread 'what if' questions. Now they welcome them. Every 'what if' is a chance to show how prepared they are."*

---

---

# FEATURE 14 — LIVE AZURE PRICING
### Screen: Infrastructure cost section

---

*"[Scroll to the Infrastructure Costs section]*

*Every Azure service recommended by the architecture agent gets a real price. Not a number from a price list we last updated six months ago. Live prices pulled from the Azure Retail Prices API at the moment this analysis ran.*

*[Point to the per-service breakdown]*

*Azure App Service — this price. Azure SQL Database — this price. Azure OpenAI — this price, based on estimated token consumption. Every service. Every month. Every year.*

*When the client's CFO asks 'how did you arrive at that infrastructure cost?' — we have a defensible, line-item answer. This is exactly what Microsoft charges for exactly these services at exactly this scale.*

*The system also has a static fallback catalog for the rare case where the Azure API is unavailable — so a network issue never derails your meeting."*

---

---

# FEATURE 15 — AI CHAT
### Screen: AI Chat tab (within proposal or as standalone)

---

*"[Open the AI Chat]*

*After the analysis runs, you can have a conversation with the proposal. Ask it anything.*

*[Type: 'Why is the risk score high for this project?']*

*The AI answers with specific references to this proposal — not a generic response about project risk. It tells you which specific technical risks drove the high score and what the mitigation strategies are.*

*[Type: 'Explain the architecture to a non-technical client']*

*Now it reframes the same technical content for someone who is not an engineer. No acronyms. Simple analogies.*

*[Type: 'What are the top three questions the client will ask and how do we answer them?']*

*It anticipates objections. It prepares your account manager for the conversation they're about to have.*

*[Type: 'Draft a follow-up email for after the proposal meeting']*

*There is your email. Personalised to this client, this project, this proposal.*

*This is what having a senior advisor available around the clock looks like. You don't need to know what to ask for — you just ask."*

---

---

# FEATURE 16 — TEAMS & ROLES (DEAL COST CALCULATOR)
### Screen: Teams & Roles tab

---

*"[Click the Teams & Roles tab]*

*This is the deal cost calculator. Built on our AKO Phase 2 rate card. This is where presales managers and account directors build the actual commercial model for a deal.*

*[Show the Project Name field]*

*Name the deal at the top. Then start building your team.*

*[Click Add Team Member]*

*Select location — India or Bangalore. Select practice — Backend, Data Services, DevOps, QA, Front-end, Project Management, Consultant. Select the specific role. The system loads the rate card rates automatically — internal cost and bill rate, both pre-filled.*

*The hours field is pre-filled from the estimate agent. If our time estimator said this role needs two hundred and forty hours on this project, that number comes in automatically. You review it, adjust it if needed, and add the person.*

*[Add a few members]*

*Watch the KPIs at the top update in real time. Total hours. People cost — that is internal only, never shown to the client. Revenue — what we bill. Gross margin before overhead. Net margin after SG&A.*

*[Point to the margin gauge on the right]*

*The deal health indicator. Green means healthy. Amber means caution. Red means we need management approval before this goes out.*

*[Show the P&L waterfall chart]*

*Revenue. Minus people cost. Minus SG&A at twenty percent. Net margin. Visual, clear, defensible.*

*Why does this feature matter? Because this is the bridge between the AI estimate and the commercial offer. The AI told us how many hours the project needs. This tool tells us what that costs us internally and what we should charge. The account director can build multiple team configurations and see the margin impact of each one before the conversation with the client.*

*[Point to Import from Estimate button]*

*And if you want to skip the manual build — Import from Estimate pulls the roles directly from what the AI just produced. Match, import, done. Your commercial model is ready in seconds.*

*[Point to Save Scenario]*

*Save it as a scenario. Come back to it. Compare it with other configurations. Export to Excel for the deal review."*

---

---

# FEATURE 17 — RUN LIBRARY
### Screen: Run Library tab

---

*"[Click the Run Library tab]*

*Every estimation run is saved automatically. Every one.*

*[Point to the list of runs]*

*Here is the full history. Search by client name. Filter by date. Filter by outcome — won, lost, pending. Every run has a timestamp, a source document name, a summary of the key numbers.*

*[Click on a past run]*

*Re-open it. Every output format is still here. Re-download the Excel. Re-download the PDF. Re-generate the PowerPoint.*

*[Point to the review gate]*

*The architect review gate. Before any proposal goes to a client, a senior architect can mark it as reviewed here. The run is flagged. The account manager knows it has been quality-checked.*

*[Point to outcome tracking]*

*When the deal closes — won or lost — you record the outcome here. That feeds into the continuous learning loop. We will come back to this.*

*Why does this matter? Because institutional knowledge lives here. 'What did we estimate for a similar Azure data platform project last year?' Three clicks. You have it. Consistent, searchable, never lost."*

---

---

# FEATURE 18 — VIDEO NARRATOR
### Screen: Narrator section

---

*"[Point to the narrator section]*

*Your proposal now comes with its own presenter.*

*Integrate with HeyGen or ElevenLabs. The system generates a narration script from the executive summary. An AI avatar delivers it on camera. You download it as an MP4.*

*Send it to the client before the meeting. By the time you get on the call, they have already seen your proposal presented. They arrive pre-sold on the concept.*

*This is particularly powerful for deals where the decision-maker is not in the room for your presentation. The CFO who can't make the call still sees the proposal delivered professionally. They watch it on their own time. You don't need to rely on someone else to explain your work.*

*Voice-only option with ElevenLabs for teams that prefer audio-first delivery."*

---

---

# FEATURE 19 — CONTINUOUS LEARNING (ADMIN DASHBOARD)
### Screen: Admin tab — Dashboard & Loop

---

*"[Click the Admin tab]*

*[Click the Dashboard sub-tab]*

*This is the learning layer. Every proposal we generate, every outcome we record, every project we deliver — this is where the system gets smarter.*

*[Point to the accuracy trend chart]*

*This line is going up. Estimate accuracy over the last six months. It improves because we feed it real data.*

*[Point to the agent accuracy bar chart]*

*Each agent has its own accuracy metric. Time estimation is currently at eighty-five percent. Cost is at seventy-nine percent. Architecture at eighty-eight percent. We know exactly which agents to focus on improving.*

*[Click the Loop sub-tab]*

*The continuous learning loop. We record actual project hours after delivery. The system calculates variance — how far off were we? It derives correction factors. If AI projects with Azure OpenAI are consistently running fifteen percent over our estimates, the system learns that and applies it to future estimates automatically.*

*This is not a marketing claim. It is a feedback loop. Over time, your estimates get more accurate. Your win rates improve with them. The institutional knowledge of every project your company has ever delivered is captured here and applied to every new estimate.*

*[Click the Templates sub-tab]*

*Template library. Common project patterns saved as starting points. Enterprise data migration. Cloud-native web application. AI chatbot integration. SharePoint modernisation. When we get a familiar type of project, we start with a template that already has reasonable estimates and a proven structure. We customise from there. Not from a blank page."*

---

---

# FEATURE 20 — AI MODEL FLEXIBILITY
### Screen: Settings / config panel

---

*"One more thing before I wrap up, and this is important for our enterprise conversations.*

*[Point to the model routing config]*

*This platform runs on any AI model. Not just one. Not locked to one vendor.*

*Azure OpenAI with GPT-4o — if your client has an Azure agreement, we use their infrastructure. Their data never leaves their Azure tenant.*

*Anthropic Claude — Sonnet or Opus — if a client has a Claude agreement.*

*Google Gemini — if your team prefers Google's stack.*

*Qwen — including fine-tuned deployments. If a client has trained their own model on their industry data, this platform can use that model.*

*Vertex AI — Google Cloud, Claude models via Application Default Credentials.*

*Each feature routes to the most appropriate model. Requirements extraction might use Azure OpenAI. Proposal writing might use Claude. Architecture design might use a fine-tuned Qwen. You configure this in one file.*

*Why does this matter? Because every enterprise client we talk to has an existing AI contract with someone. We don't come in and say 'you need to buy a new AI subscription.' We say 'we work with what you already have.' That is a commercial conversation that almost never gets blocked."*

---

---

# CLOSING — SUMMARY

---

*"Let me pull back and tell you what you just saw.*

*A scope document went in. Ninety seconds later, here is what came out:*

*A complete requirements register. A three-point time estimate. A phase-by-phase cost model. A risk register with mitigation strategies. An architecture design with live Azure pricing. A scope and assumptions document. A statement of work. A discovery questions brief. A narrative proposal. A PowerPoint deck. An Excel workbook with five sheets. A JSON export for any system that wants the raw data. A ZIP bundle with everything.*

*All of that — produced by eleven specialist agents, simultaneously, with complete consistency, for under one pound in API costs.*

*The question I want to leave you with is this: what is the cost of not having this?*

*Every proposal your team produces manually is an opportunity for inconsistency. For a missed requirement. For an undercooked risk register. For a margin that looked healthy until delivery.*

*This platform doesn't replace your consultants. It removes the administrative burden so your consultants can spend their time on what actually requires human expertise — understanding the client, building the relationship, making the strategic decisions that no AI can make.*

*Thank you. I'm ready for questions."*

---

---

# OBJECTION HANDLING — HAVE THESE READY

---

**"Can we trust AI to produce the estimates?"**

*"The AI produces the first draft. Your senior consultant reviews it, adjusts it, approves it. The architect review gate in the Run Library is a mandatory checkpoint before anything goes to the client. Think of this as having the best first draft in the room before the expert reviews it — not replacing the expert."*

---

**"What if the scope doc is vague?"**

*"That is exactly why the completeness checker exists. Before the analysis runs, it identifies every gap in the scope document. It tells you what to ask before you price. A vague scope doc produces an amber or red completeness score, which tells your team: do not submit this estimate without getting answers to these questions first."*

---

**"What about data security?"**

*"The document you upload is processed by the AI API you have configured — Azure OpenAI, Claude, or Gemini. If you use Azure OpenAI with your own Azure tenant, the data never leaves your environment. The run library is local SQLite — it stays on your server. No usage data goes to any third party. For enterprise deployments with Azure Key Vault and Azure Container Apps, all credentials are injected at runtime and never stored in the application."*

---

**"How accurate is it?"**

*"Current accuracy is around eighty percent and improving with every project we record outcomes for. But accuracy is the wrong frame. The question is: how accurate are your manual estimates? Across consultants, across days of the week, across levels of fatigue? The AI is consistently at eighty percent. Your manual process has high variance. We are replacing variance with consistency — and then improving that consistent baseline over time."*

---

**"What is the implementation effort?"**

*"For a local deployment: install Python, run one command, open the browser. It takes ten minutes. For a production Azure Container Apps deployment: the Bicep template is ready. Your DevOps team can have it deployed in a day. The AI model connections require API keys — if you have existing Azure OpenAI access, you are ready immediately."*

---

**"Does it learn our specific way of working?"**

*"Yes. That is the Templates library and the Continuous Learning loop. You upload historical projects. You record outcomes. The system derives correction factors for your specific delivery methodology, your team's velocity, your typical risk profile. Over six to twelve months, the estimates reflect your organisation's specific performance data — not generic industry averages."*

---

---

# QUICK REFERENCE — KEY NUMBERS

| What | Number |
|---|---|
| Time to full estimation package | Under 90 seconds |
| Number of AI agents | 11 |
| Output formats per run | 9+ |
| Supported AI providers | 5 (Azure, Claude, Gemini, Qwen, Vertex) |
| Estimate accuracy (current) | ~80% and improving |
| API cost per full run | Under £1 |
| Manual proposal cost (senior consultant) | £800–£3,000 |
| Presales effort reduction | Up to 70% |
| Consistency improvement | Estimates within ±8% across consultants |

---

---

# TAB-BY-TAB NAVIGATION GUIDE

*Use this to find your way around quickly during the demo.*

| What to show | Where it is |
|---|---|
| Document upload | Tab 1 → top of page |
| Completeness checker | Tab 1 → appears after file upload |
| Transcript / discovery | Tab 1 → scroll down to Multimodal Discovery |
| Run pipeline button | Tab 1 → below completeness checker |
| Requirements & Time estimate | Tab 1 → results section |
| Cost breakdown | Tab 1 → results section |
| Risk register | Tab 1 → results section |
| Architecture diagram | Tab 1 → Architecture tab in results |
| Discovery questions | Tab 1 → Discovery tab in results |
| Proposal document | Tab 1 → Proposal tab → Document sub-tab |
| PowerPoint export | Tab 1 → Proposal tab → Presentation sub-tab |
| Statement of Work | Tab 1 → Proposal tab → SOW sub-tab |
| AI Chat | Tab 1 → Proposal Chat section |
| Scenario Modelling | Tab 1 → Scenario Builder tab |
| Teams & Roles | Tab 1 → Teams & Roles tab |
| Admin / Learning | Tab 2 → Admin |
| Run Library | Tab 3 → Run Library |

---

*© ECI — Internal Use Only · Demo Script v1.0 · May 2026*
