# Arabic AI-Powered Outbound Calls Platform

A production-oriented, multi-tenant Arabic customer follow-up platform. The system places outbound calls to customers, verifies whether a previously reported issue was resolved, records the call outcome, and ends the automated call. If the issue remains unresolved or the customer response is ambiguous, the system creates a post-call escalation for a human agent. The human agent can then use an organization-specific Arabic knowledge assistant to understand the case and continue helping the customer.

> **Important workflow decision:** the automated call does not perform a live transfer. The call ends after the verification decision is recorded. Human assistance happens after the call through the escalation queue and the organization-scoped knowledge assistant.

## Project status at a glance

The current repository contains a working foundation for the two core use cases: **automated outbound follow-up calls** and a **human-agent Arabic RAG assistant**. The tenant hierarchy, Supabase schema, RLS policies, Vonage integration, Gradio console, document ingestion, hybrid retrieval, post-call routing, scheduling, reporting, and invitation flow are implemented and covered by the current test suite.

The remaining work is mainly production hardening and advanced AI functionality. In particular, the current phone conversation is structured and provider-driven rather than a fully generative, turn-by-turn LLM conversation. LangGraph/LangChain/LangSmith orchestration, centralized observability, multimodal/OCR ingestion, stronger embedding evaluation, and interactive LLM voice behavior are roadmap items rather than completed features.

## Core use cases

### Use case 1: Automated outbound follow-up

An authorized agent or scheduler selects a customer case. The platform calls the customer through Vonage or the development simulator, presents a clear Modern Standard Arabic verification prompt, captures speech through local recording and Whisper or provider speech input, normalizes the response, classifies the outcome, writes the call data, and ends the call.

The supported post-call outcomes include resolved, unresolved/escalated, no answer, busy, and failed. Unresolved or ambiguous results create an escalation for a human agent. No live transfer is attempted.

### Use case 2: Human agent knowledge assistance

After the automated call, a human agent opens the organization’s escalation queue and asks questions in Arabic. The assistant retrieves relevant content only from the active organization’s private knowledge base, generates an answer using the configured LLM provider, and returns citations to the source documents. Organization boundaries are enforced in the API, database transaction context, PostgreSQL RLS, and retrieval queries.

**New in this delivery (voice-enabled RAG chat `src/outbound_ai/ui/app.py:704`):** Inside tab `مساعد المعرفة العربي` you can now:
- **STT:** record mic (🎤) -> `STT_MODEL=gpt-4o-transcribe` via `OPENAI_API_KEY` (`src/outbound_ai/ui/app.py:_transcribe_audio_file`) -> auto-fill question box
- **Voice Q&A:** `إرسال صوتي + تشغيل الرد` does `Mic -> STT -> POST /agent/query` (deterministic hybrid RAG `src/outbound_ai/agents/kb_assist.py:105`, org-isolated) -> `TTS` via `ELEVENLABS_API_KEY`/`VOICE_ID=VR6AewLTigWG4xSOukaG` (`src/outbound_ai/ui/app.py:_synthesize_elevenlabs`)
- **TTS playback:** `🔊 تشغيل آخر إجابة` synthesizes last assistant answer
- **In-chat ingestion:** upload `PDF/TXT/DOCX/MD/CSV/JSON` directly in chat -> `POST /documents/upload` (same org-isolated pipeline as `المعرفة والمستندات`) so you can ingest without switching tabs

> RAG stays deterministic SQL (no LLM agent) per your constraint; only the **voice layer** was added on top.

## Technology stack

| Layer | Technology | Current role |
| --- | --- | --- |
| Application language | Python 3.11–3.12 | Backend services, RAG pipeline, telephony, scheduler, and UI client |
| API | FastAPI and Uvicorn | Authentication-aware REST API, campaign endpoints, document endpoints, reports, administration, and Vonage callbacks |
| User interface | Gradio **5.35.0** | Arabic RTL operations console with role-aware panels and direct component visibility updates |
| Database | PostgreSQL through Supabase | Tenant-aware business data, calls, cases, customers, tasks, escalations, reports, conversations, messages, and audit events |
| Database security | PostgreSQL RLS and tenant context | Organization isolation and hierarchical access control |
| Vector search | Supabase `pgvector`, `halfvec`, and HNSW | Dense retrieval for organization-specific knowledge chunks |
| Lexical search | PostgreSQL full-text search | Keyword retrieval combined with vector similarity in hybrid RAG |
| File storage | Private Supabase Storage bucket | Organization-scoped document objects and ingestion source files |
| Authentication | Supabase Auth, JWT, JWKS/HS256 support | User login, invitation password setup, membership verification, and platform-admin recognition |
| LLM | Gemini through an OpenAI-compatible client | Arabic answer generation for the knowledge assistant |
| Embeddings | Arabic Sentence Transformer by default; deterministic and OpenAI-compatible options remain available | Local 384-dimensional Arabic embeddings by default, with configurable alternatives |
| Telephony | Vonage Voice API plus simulated provider | Outbound calls, native Vonage Arabic voice, optional local Whisper recording/STT, event callbacks, and local development without carrier calls |
| Scheduling | Separate Python worker | Due-task claiming, retries, exponential backoff, and call dispatch |
| Deployment | Dockerfile and Docker Compose | API, Gradio UI, and scheduler service definitions |
| Testing | Pytest, async test support, database contract tests | Current unit, integration-oriented, RLS-contract, RAG, routing, telephony, and UI-contract validation |

The pinned Gradio version is intentional. The project uses direct server-side component visibility updates, and Gradio 5.35.0 is the tested version for this UI. The current repository validation run passes **76 tests**.

## How to test voice + ingestion in RAG chat (handover checklist)

**Prereqs:** `SUPABASE_JWT_SECRET=` empty (JWKS), `OPENAI_API_KEY` + `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID=VR6AewLTigWG4xSOukaG` in `.env`, API/UI/scheduler running, login as `superadmin.demo42@gmail.com / SuperAdmin123!` (or your super_admin) at `http://localhost:7860`.

1. **Ingest (either tab):**
   - In `مساعد المعرفة العربي` -> `📄 رفع مستند PDF/TXT` -> choose `data/knowledge_base/sop.txt` or any Arabic PDF (e.g., `سياسة الاسترجاع: يمكنك الاسترجاع خلال 14 يوم مع الفاتورة...`) -> `رفع ومعالجة للسياق الحالي` -> expect `{"chunks":...}`. Or use `المعرفة والمستندات` tab similarly.

2. **Text baseline:** In `مساعد المعرفة العربي` -> type: `ما هي سياسة الاسترجاع؟` -> `إرسال السؤال` -> expect grounded answer + `**المصادر:** [S1]`.

3. **Voice (STT -> RAG -> TTS):**
   - Click 🎤 `تسجيل صوتي`, allow mic, say: `ما هي سياسة الاسترجاع خلال كم يوم؟` -> `1️⃣ تحويل الصوت إلى نص` -> verify transcript appears -> `2️⃣ إرسال صوتي + تشغيل الرد` -> watch `المساعد المعرفي العربي` history append + audio player `الرد الصوتي` auto-fills. Or directly `2️⃣` to skip preview.
   - Alternative phrases to try: `هل يمكنني استرجاع المنتج بعد أسبوع؟` / `ما هي خطوات تفعيل الحساب بعد التسجيل؟` (use content of your uploaded doc).
   - `🔊 تشغيل آخر إجابة صوتياً` replays last answer without new query.

4. **Negative/grounding check:** Ask `ما هو سعر البيتكوين اليوم؟` (not in KB) -> expect `لم أجد إجابة موثقة...` + `grounded=false`.

Troubleshooting: no transcript = check `STT_MODEL`/`OPENAI_API_KEY`; no audio = check `ELEVENLABS_API_KEY`/browser autoplay mute; `HTTP 500` = restart API after `.env` change.

## Current architecture

```
                    +-------------------------+
                    |      Gradio RTL UI      |
                    | login, campaigns, RAG,  |
                    | documents, reports,     |
                    | administration          |
                    +------------+------------+
                                 |
                         JWT + organization ID
                                 |
                    +------------v------------+
                    |       FastAPI API       |
                    | auth, tenant checks,    |
                    | campaigns, documents,   |
                    | agent, reports, admin   |
                    +-----+--------------+----+
                          |              |
             +------------v---+     +----v----------------+
             | Supabase Auth  |     | Supabase PostgreSQL |
             | users and JWT  |     | RLS, pgvector,     |
             +----------------+     | full-text, Storage |
                                    +----+-----------+----+
                                         |           |
                              +----------v--+   +----v---------+
                              | RAG pipeline |   | Vonage Voice  |
                              | load, chunk, |   | answer/input/ |
                              | embed, rank, |   | event callbacks|
                              | cite, answer|   +---------------+
                              +-------------+
                                         |
                              +----------v----------+
                              | Scheduler worker    |
                              | claim, dispatch,    |
                              | retry, backoff      |
                              +---------------------+
```

### Request and data-isolation model

Every tenant-owned business record carries `organization_id`. User-facing requests resolve an authenticated principal and active organization membership before opening the transaction. The database transaction sets the tenant context and executes under the authenticated database role so RLS remains active. Platform administrators can select an active organization explicitly; organization administrators and agents are limited to their active memberships.

Vonage callbacks and scheduler operations are server-originated. They use narrowly scoped trusted transactions and correlate events through persisted internal call IDs and provider call IDs. They do not trust a client-supplied organization ID as the source of truth for a callback.

## What is implemented

| Area | Completed implementation |
| --- | --- |
| Hierarchical tenancy | Platform administrator → organization administrator → agent hierarchy with membership checks and role boundaries |
| Tenant isolation | Organization-scoped queries, database RLS, private Storage policies, tenant context, and cross-organization access tests/contracts |
| Authentication | Supabase JWT verification, active membership resolution, platform-admin detection, invitation flow, and password setup page |
| Organization administration | Platform-admin organization creation, organization selection for invitations, member listing, agent invitations, and organization-admin restrictions |
| Arabic UI | RTL Gradio workspace, login-first flow, role-aware tabs, Arabic labels, Modern Standard Arabic call prompts, and Arabic error messages |
| Direct calls | Immediate call action from a selected case without creating a scheduled follow-up task |
| Scheduled follow-ups | Task creation, due-task claiming, manual start, retries, exponential backoff, status transitions, and automatic task-ID propagation in the UI |
| Telephony | Vonage outbound call adapter, simulated development adapter, native Arabic `talk`, recording or speech-input callbacks, local Whisper option, DTMF/speech input handling, and post-call routing |
| Call persistence | Internal call ID, provider call ID, status, outcome, duration, raw provider events, text call turns, optional audio paths, and synchronized support-case status |
| Post-call routing | `ANSWERED_RESOLVED`, `ESCALATED`, `NO_ANSWER`, `BUSY`, and `FAILED` decisions without live transfer |
| Escalation workflow | Organization-scoped escalation queue, human resolution action, and escalation reporting support |
| Knowledge ingestion | PDF, DOCX, TXT, Markdown, CSV, and JSON ingestion; Arabic normalization; chunking; embeddings; private Storage upload; and database persistence |
| Hybrid RAG | Vector similarity plus PostgreSQL full-text retrieval with organization filters and citations |
| Arabic assistant | Gemini-backed answer generation, fallback behavior, conversation persistence, citation display, and audit-event handling |
| FCR reporting | Organization-scoped first-call-resolution metrics, outcome aggregates, escalation counts, answer rate, and duration metrics |
| Structured logging | Privacy-conscious application logging with sensitive-value redaction and event-oriented log helpers |
| Deployment | Dockerfile, Docker Compose, `.env.example`, Codespaces runbook, Supabase setup documentation, and scheduler entrypoint |
| Automated validation | Unit tests and contract tests for RLS/migrations, RAG behavior, routing, telephony, escalation behavior, role boundaries, logout, scheduling, and UI construction |



---

## How This Project's "RAG" and "Agents" Actually Work

> **Critical Finding:** This project's "RAG" and "agentic" components are **not what they appear to be**. The system is built on **raw SQL queries and deterministic rule-based logic**, not on LLM-driven agentic workflows or a complete RAG pipeline.

### How the "RAG" Actually Works (Raw SQL)

The so-called "RAG" pipeline is a **single SQL vector search** followed by a direct LLM call:

```python
# What actually happens when a question is asked:
# 1. Embed question with sentence-transformers (384-dim)
# 2. Execute RAW SQL vector search:
#    SELECT content_norm FROM knowledge_chunks 
#    WHERE organization_id = $1 
#    ORDER BY embedding <=> $2 
#    LIMIT 5
# 3. Concatenate top 5 chunks into a basic prompt
# 4. Send to Gemini with minimal prompt
# 5. Return raw LLM response
```

**Why it answers in microseconds:**
- No context building - raw chunk concatenation only
- No metadata filtering - only organization_id filter
- No hybrid search - pure vector similarity only
- No grounding/verification - direct LLM output
- No citations, personas, or multi-language support
- 384-dim embeddings (faster than 768/3072)
- Single HNSW index lookup

**Missing RAG Components:**
- No context_builder.py - no structured context assembly
- No retrievers/dense.py, sparse.py, hybrid.py - only single vector search
- No generation.py - no citations, grounding, personas, multi-language
- No /kb/chat, /kb/chat/voice - no agent desk co-pilot
- No /data/query - no NL→SQL capability

### How the "Agents" Actually Work (Deterministic SQL/Python)

The so-called "agentic" workflows are **deterministic rule-based state machines**, not LLM-driven agents:

| "Agent" | Actual Implementation |
|---------|----------------------|
| Call Routing Agent | decide_follow_up() - keyword matching on Arabic text (if "اتحلت" in text: RESOLVED) |
| Scheduler Agent | SQL query: SELECT * FROM follow_up_tasks WHERE status='PENDING' AND scheduled_for <= NOW() |
| Vonage Webhook Handler | SQL INSERT/UPDATE on calls, call_events, call_turns tables |
| Escalation Agent | INSERT INTO escalations (...) VALUES (...) with hardcoded reasons |
| FCR Reporting Agent | SQL aggregation: COUNT(*) FILTER (WHERE outcome='ANSWERED_RESOLVED') |

**No LLM decision-making anywhere.** Every "decision" is:
- if/elif/else on Arabic keywords
- SQL queries with hardcoded logic
- Deterministic state transitions

### Database Schema: Why So Many Tables?

This is a **complete business application**, not just RAG. The 17 tables implement:

| Domain | Tables |
|---------|--------|
| Multi-tenancy | organizations, organization_memberships, profiles, platform_admins |
| Customer Support | customers, support_cases, follow_up_tasks, escalations, fcr_reports |
| Telephony | calls, call_events, call_turns |
| Knowledge | knowledge_documents, knowledge_chunks (3072-dim embeddings) |
| Human Agent Chat | agent_conversations, agent_messages |
| Audit | audit_events |

### The Real Architecture

```
+-----------------------------------------------------------+
|                    Deterministic Layer                    |
+-----------------------------------------------------------+
|  Python/SQL State Machines (if/else, SQL queries)        |
|  Call scheduling & dispatch                               |
|  Keyword-based intent classification                      |
|  Call state transitions (QUEUED→RINGING→ANSWERED)    |
|  Escalation creation & assignment                         |
+---------------------------|-------------------------------+
                            |
                            v
+-----------------------------------------------------------+
|                      SQL Layer                            |
+-----------------------------------------------------------+
|  Vector search (embedding <-> query)                     |
|  Business CRUD (cases, customers, tasks)                 |
|  RLS policies (organization_id isolation)                |
|  Audit logging                                            |
+---------------------------|-------------------------------+
                            |
                            v
+-----------------------------------------------------------+
|                      LLM Layer (Gemini)                   |
+-----------------------------------------------------------+
|  Single call: concat top-5 chunks → prompt → answer      |
|  No multi-turn, no citations, no grounding               |
|  Used only for: RAG answer generation                     |
+-----------------------------------------------------------+
```

---

## Gap Analysis vs Reference Implementation (Team Member A Branch)

The following table compares this repository against the reference implementation in `feature/agentic-voice-rag-team-member-a` (https://github.com/mamdouh-salem/Ai_Arabic_Outbound_calls_Rag_Assistance.git). Items marked ❌ are **missing or significantly different** and require implementation.

### Telephony & Voice Layer

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-turn NCCO dialogue | ❌ | Single answer → input flow only. No `update_call_ncco` for mid-call NCCO updates. |
| ElevenLabs TTS integration | ❌ | Only Vonage native `talk` or local MMS-TTS. No ElevenLabs streaming. |
| ElevenLabs voice caching | ❌ | No audio cache with hash-based deduplication. |
| Hold audio synthesis | ❌ | No pre-synthesized looping hold message. |
| Conversation UUID adoption | ❌ | Mid-call NCCO transfer changes `conversation_uuid`; no adoption logic. |
| Negation-aware resolution detection | ❌ | Basic keyword matching only. Arabic negation ("متحلتش" ≠ "اتحلت") not handled. |
| RAG integration in live calls | ❌ | KB retrieval during live calls not implemented. |
| LangGraph orchestration | ❌ | Custom state machine instead of LangGraph. No LangGraph Studio integration. |
| LangSmith tracing | ❌ | Not configured. No observability for call flows. |
| Audio cache (TTS/hold) | ❌ | Re-synthesizes same TTS repeatedly. No hash-based cache. |

### RAG Pipeline (Critical Gaps)

| Component | Current State | Missing vs Reference |
|-----------|---------------|---------------------|
| **Context Building** | ❌ | No `context_builder.py`. Raw chunks passed directly to LLM without structured context assembly (titles, source metadata, relevance scores, snippet windows). |
| **Metadata Filtering** | ❌ | Only `organization_id` filter. Missing: `category`, `document_id`, `page_number`, `language`, `uploaded_by`, `created_at` range, `checksum` filters. |
| **Hybrid Retrieval Weights** | Fixed | Reference uses tunable dense/sparse/RRF weights per query type. |
| **Citation Formatting** | Basic | Missing structured citations with: `index`, `source_doc`, `chunk_id`, `page`, `score`, `snippet`, `relative_score`. |
| **RAG Chat API** | ❌ | No `/kb/chat` or `/kb/chat/voice` endpoints for agent desk co-pilot. |
| **RAG Voice Chat** | ❌ | No voice round-trip (mic → STT → RAG → TTS → audio playback). |
| **NL → SQL Data Query** | ❌ | No `/data/query` endpoint for business data questions. |
| **Persona/Language Selection** | ❌ | No customizable response styles (Egyptian friendly, formal, concise, etc.) or multi-language answers. |
| **Citation Relative Threshold** | ❌ | No `rag_citation_relative_threshold` to filter weak tail chunks. |
| **Grounding Score Validation** | Basic | Missing `rag_min_grounding_score` enforcement with fallback behavior. |

### Embeddings & Vector Search

| Feature | Current | Reference |
|---------|---------|-----------|
| Embedding Dimension | 384 (Arabic Sentence Transformer) | 768 (local) or 3072 (OpenAI text-embedding-3-large) |
| Vector Index | HNSW on 3072-dim | `halfvec_cosine_ops` on 768-dim (more efficient) |
| Embedding Provider | Fixed (Sentence Transformer) | Pluggable: local / OpenAI / deterministic |
| Embedding Evaluation | Not implemented | Benchmark scripts + regression tests |

### Multi-tenancy & Auth

| Feature | Current (Organizations) | Reference (Workspaces) |
|---------|------------------------|------------------------|
| Hierarchy | `platform_admins` + `organization_memberships` (ORG_ADMIN/AGENT) | `workspaces` + `workspace_members` (super_admin/admin/agent) |
| Roles | `platform_admin` flag + `ORG_ADMIN`/`AGENT` | `super_admin`, `admin`, `agent` enum |
| RLS | `organization_id` + `private.is_org_member()` | `workspace_id` + `workspace_members` RLS |
| JWT Verification | HS256 + RS256/ES256 via JWKS | HS256 + ES256 (full JWKS with kid rotation) |
| Auto-profile Trigger | `profiles` table + trigger | `users` table + `handle_new_auth_user()` |
| Role Permissions | Binary (platform_admin vs org roles) | Fine-grained: super_admin/admin/agent matrix |

### API Endpoints Missing

| Endpoint | Purpose | Reference Location |
|----------|---------|-------------------|
| `/kb/documents` | Upload/list/delete KB docs | `src/outbound_ai/api/routers/kb.py` |
| `/kb/chat` | RAG text chat with citations | `src/outbound_ai/api/routers/kb.py` |
| `/kb/chat/voice` | Voice RAG (mic → STT → RAG → TTS) | `src/outbound_ai/api/routers/kb.py` |
| `/data/query` | NL → SQL business data queries | `src/outbound_ai/api/routers/data.py` |
| `/admin/workspaces` | Workspace CRUD | `src/outbound_ai/api/routers/workspaces.py` |
| `/admin/users` | User management | `src/outbound_ai/api/routers/admin_users.py` |
| `/health/auth` | Auth probe | `src/outbound_ai/api/app.py` |

### Observability & Tooling

| Tool | Current | Reference |
|------|---------|-----------|
| LangGraph | ❌ | Full `StateGraph` with conditional edges |
| LangGraph Studio | ❌ | `langgraph.json` + `graph/studio.py` |
| LangSmith | ❌ | Integrated tracing + evaluation |
| Audio Cache | ❌ | Hash-based TTS/hold cache |
| Workflow Visualization | ❌ | `/workflow.png` from compiled graph |
| Embedding Warm-up | ❌ | Startup pre-loads embedding model |

---

## RAG Pipeline: Detailed Gap Analysis

The reference implementation (`src/outbound_ai/rag/`) includes these components that are **missing or incomplete** here:

### 1. Context Building (`context_builder.py` - MISSING)
```
Reference builds structured context with:
- Document titles and source metadata
- Chunk relevance scores and rankings
- Snippet windows (surrounding text)
- Relative score thresholds (filter weak tail chunks)
- Citation metadata assembly (index, doc_id, chunk_id, page, score)
- Grounding score calculation per answer
```

### 2. Metadata Filtering (INCOMPLETE)
```
Current: Only organization_id filter
Missing filters:
  - category (billing, technical, account, etc.)
  - document_id (specific document scope)
  - page_number (page-level granularity)
  - language (ar, en, etc.)
  - uploaded_by (author filter)
  - created_at range (recency filter)
  - checksum (deduplication)
  - source_metadata JSONB keys (custom tags)
```

### 3. Retrieval Pipeline (`retrievers/` - MISSING)
```
Reference has separate retrievers:
- dense.py: pgvector halfvec cosine similarity
- sparse.py: PostgreSQL full-text (tsvector/tsquery)
- hybrid.py: RRF fusion with configurable weights
All scoped to workspace_id + metadata filters
```

### 4. Generation Pipeline (`generation.py` - INCOMPLETE)
```
Missing features:
- Persona system (default/egyptian_friendly/formal/concise/empathetic/technical)
- Multi-language answers (ar/en/es/de/fr)
- Grounding score per answer with fallback
- Citation relative threshold filtering
- Structured citation output (index, source, score, snippet)
- Answer language enforcement
```

### 5. Ingestion Pipeline (`ingestion.py` - PARTIAL)
```
Missing:
- Multi-format loaders (pypdf, python-docx, python-pptx, openpyxl)
- OCR for scanned PDFs (tesseract/easyocr)
- Table extraction (tabula/pdfplumber)
- Image description (multimodal LLM)
- Page-level provenance tracking
- Checksum-based deduplication
```

### 6. RAG Evaluation (`eval_rag/` - MISSING)
```
Missing:
- Ground truth Q→A→source pairs
- Retrieval metrics (recall@k, MRR, nDCG)
- Generation metrics (grounding, citation accuracy)
- Regression test suite
- Embedding benchmark scripts
```

---

## Required Implementation Roadmap

### Phase 1: Foundation (Week 1-2) ✅ **START HERE**

1. **Schema Alignment**
   - [ ] Add `workspace_id` to all tenant tables (or map `organization_id` → `workspace_id`)
   - [ ] Add `users` table with `platform_role` enum (super_admin/admin/agent)
   - [ ] Add `workspace_members` with roles
   - [ ] Create `handle_new_auth_user()` trigger
   - [ ] Update RLS policies for workspace_id scoping

2. **Auth & Permissions**
   - [ ] Implement `require_admin_only`, `require_admin_or_agent`, `require_super_admin` dependencies
   - [ ] Add `SuperAdmin`, `AdminOnly`, `AdminOrAgent` type aliases
   - [ ] Update JWT verification for ES256 JWKS with kid rotation

3. **Embedding Alignment**
   - [ ] Switch to 768-dim local embeddings (or 3072 OpenAI)
   - [ ] Update `knowledge_chunks.embedding` to `halfvec(768)`
   - [ ] Recreate HNSW index with `halfvec_cosine_ops`
   - [ ] Add embedding provider switching (local/OpenAI/deterministic)

### Phase 2: RAG Pipeline Complete Overhaul (Week 2-3)

3. **Create Missing RAG Modules**
   - [ ] `src/outbound_ai/rag/context_builder.py` - structured context assembly
   - [ ] `src/outbound_ai/rag/retrievers/dense.py` - pgvector halfvec search
   - [ ] `src/outbound_ai/rag/retrievers/sparse.py` - PG full-text
   - [ ] `src/outbound_ai/rag/retrievers/hybrid.py` - RRF fusion
   - [ ] `src/outbound_ai/rag/retrievers/__init__.py`
   - [ ] `src/outbound_ai/rag/generation.py` - complete with personas, citations, grounding

4. **Metadata Filtering**
   - [ ] Add `category`, `document_id`, `page_number`, `language`, `checksum` to `knowledge_chunks`
   - [ ] Update ingestion to populate metadata
   - [ ] Add filter parameters to retrieval functions
   - [ ] Create filter builder utility

5. **RAG API Endpoints**
   - [ ] `POST /kb/documents` - upload with ingestion
   - [ ] `GET /kb/documents` - list with chunk counts
   - [ ] `DELETE /kb/documents/{source}` - delete by source
   - [ ] `POST /kb/chat` - text RAG with citations
   - [ ] `POST /kb/chat/voice` - voice RAG (STT → RAG → TTS)
   - [ ] `POST /data/query` - NL → SQL with validation

6. **RAG Evaluation**
   - [ ] Create `data/eval/` ground truth pairs
   - [ ] Add retrieval metrics (recall@k, MRR)
   - [ ] Add generation metrics (grounding, citation accuracy)
   - [ ] Embedding benchmark scripts

### Phase 3: Telephony & Voice Layer (Week 3-4)

7. **Vonage Adapter Overhaul**
   - [ ] Replace `telephony/vonage.py` with full `VonageTelephonyAdapter`
   - [ ] Implement `update_call_ncco` for multi-turn dialogue
   - [ ] Add conversation UUID adoption logic
   - [ ] Add ElevenLabs TTS integration (`voice/tts_elevenlabs.py`)
   - [ ] Add audio cache with hash-based deduplication
   - [ ] Add hold audio synthesis and caching
   - [ ] Add Arabic negation handling ("متحلتش" ≠ "اتحلت")

8. **Call Flow Integration**
   - [ ] Multi-stage NCCO: greeting → record → KB search → suggestion → confirm
   - [ ] Hold audio that loops during processing
   - [ ] Emergency fallback to Vonage TTS on ElevenLabs failure
   - [ ] Audio streaming via `/audio/{filename}` endpoint

### Phase 4: Advanced Features (Week 4-5)

9. **LangGraph Integration**
   - [ ] Add `langgraph` dependency
   - [ ] Create `src/outbound_ai/graph/` with state, nodes, edges, build
   - [ ] Add `langgraph.json` for Studio
   - [ ] Create `graph/studio.py` for dev server
   - [ ] Connect real LLM/RAG/voice ports to graph

10. **Advanced RAG Features**
    - [ ] Persona system (6 styles)
    - [ ] Multi-language answers (ar/en/es/de/fr)
    - [ ] RAG voice chat endpoint
    - [ ] NL → SQL with validation guards
    - [ ] Citation relative threshold filtering

11. **Observability**
    - [ ] LangSmith integration
    - [ ] `/workflow.png` from compiled graph
    - [ ] Startup warm-up (embeddings + hold audio)
    - [ ] Audio cache stats endpoint

### Phase 5: Production Hardening (Week 5-6)

12. **Testing & Validation**
    - [ ] RAG evaluation dataset + regression tests
    - [ ] Embedding benchmark scripts
    - [ ] Integration tests for call flow (mock Vonage events)
    - [ ] Multi-tenant isolation tests
    - [ ] NL→SQL injection/guard tests

13. **Documentation & Deployment**
    - [ ] Update all `.env.example` with new variables
    - [ ] Update Supabase migrations (001-007)
    - [ ] Update Docker/Compose for new dependencies
    - [ ] Update README with new architecture

---

## Quick Start: Clone & Use Same Database

```bash
# 1. Clone reference branch
git clone -b feature/agentic-voice-rag-team-member-a   https://github.com/mamdouh-salem/Ai_Arabic_Outbound_calls_Rag_Assistance.git

# 2. Configure same Supabase
cp .env.example .env
# Edit .env with shared credentials:
# SUPABASE_URL=https://<YOUR_PROJECT>.supabase.co
# SUPABASE_ANON_KEY=<YOUR_SUPABASE_ANON_KEY>
# SUPABASE_SERVICE_ROLE_KEY=<YOUR_SUPABASE_SERVICE_ROLE_KEY>
# SUPABASE_JWT_SECRET=<YOUR_SUPABASE_JWT_SECRET>

# 3. Vonage (same app)
# VONAGE_APPLICATION_ID=<YOUR_VONAGE_APPLICATION_ID>
# VONAGE_API_KEY=<YOUR_VONAGE_API_KEY>
# VONAGE_API_SECRET=<YOUR_VONAGE_API_SECRET>
# VONAGE_FROM_NUMBER=<YOUR_REAL_VONAGE_NUMBER>
# PUBLIC_WEBHOOK_BASE_URL=<ngrok_url>

# 4. ElevenLabs
# ELEVENLABS_API_KEY=<YOUR_ELEVENLABS_API_KEY>
# ELEVENLABS_VOICE_ID=<YOUR_ELEVENLABS_VOICE_ID>

# 5. Run
uv venv --python 3.11
uv pip install -e ".[dev]"
python -m uvicorn outbound_ai.api.app:app --host 0.0.0.0 --port 8000 --reload
```



## What is still missing or only partially implemented

The following items are deliberately separated from the completed foundation. They should be planned as engineering work rather than described as already available. The current structured verification call is implemented; a fully generative multi-turn voice agent is not.

| Area | Current state | Required completion |
| --- | --- | --- |
| Comprehensive audit/log system | Structured privacy-safe logs and database audit-event support exist, but coverage is not yet a complete operational audit platform | Define an event taxonomy, add correlation IDs, record important user/admin/data actions consistently, centralize logs, enforce retention, add dashboards/alerts, and document access to audit history |
| Interactive LLM voice calls | Current calls use native Vonage Arabic `talk` for spoken responses and either local recording plus faster-whisper or provider speech input for structured verification. The LLM does not yet conduct a multi-turn conversation with the customer | Add a real-time voice loop: speech recognition → turn state → LLM response → Arabic TTS → next input, with latency, interruption, timeout, safety, and callback handling |
| Voice recording and consent | Text turns and raw provider events are stored; audio recording is not enabled by default | Add explicit consent language, recording configuration, encrypted private storage, retention/deletion policy, playback authorization, and regional compliance review |
| Agentic workflow | The repository has deterministic service boundaries and a graph package placeholder, but LangGraph, LangChain, and LangSmith are not currently wired into the runtime | Introduce explicit state graphs, tool boundaries, retries, tracing, evaluation datasets, and LangSmith observability without weakening tenant isolation |
| Multimodal and OCR ingestion | Text-oriented PDF, DOCX, TXT, Markdown, CSV, and JSON ingestion is implemented | Add image upload, scanned-PDF OCR, table/image extraction, multimodal document classification, page-level provenance, and safe handling for complicated file types |
| Prompt engineering | Arabic prompts and answer templates exist, but systematic versioning and evaluation are limited | Create versioned prompts, few-shot examples, Egyptian-Arabic style guidance, refusal and uncertainty policies, test fixtures, and automatic prompt regression evaluation |
| Embedding quality | Deterministic embeddings are useful for zero-cost development but their similarity values are not semantically strong | Evaluate multilingual Arabic embedding models, configure an approved production provider or local model, benchmark chunk sizes, tune hybrid weights, and add reranking/evaluation metrics |
| Production operations | Docker and runbooks exist, but carrier credentials, public HTTPS, observability infrastructure, and acceptance testing remain operator responsibilities | Deploy with secrets management, TLS, health supervision, backups, alerting, load tests, security review, and a controlled live-call acceptance test |

## Repository layout

```
docs/                                   architecture, database, voice, runbooks, audits
supabase/migrations/                    schema, RLS, pgvector, Storage, helper functions
supabase/seed.sql                       development seed data
scripts/run_scheduler.py                long-running follow-up worker entrypoint
src/outbound_ai/api/                    FastAPI application and routers
src/outbound_ai/db/                     connection layer and repositories
src/outbound_ai/rag/                    Arabic loaders, chunking, embeddings, retrieval, ingestion
src/outbound_ai/agents/                 knowledge assistant behavior
src/outbound_ai/reports/                FCR calculation and reporting facade
src/outbound_ai/telephony/              Vonage, simulator, routing, scheduler, provider interface
src/outbound_ai/observability/          privacy-safe structured logging helpers
src/outbound_ai/ui/app.py               Gradio Arabic operations console
tests/unit/                             unit and contract tests
Dockerfile                              production application image
docker-compose.yml                      API, UI, and scheduler services
```

## Local setup

Use Python 3.11 or 3.12. The following setup starts the project with the local Arabic Sentence Transformer and simulated telephony so the test workflow does not place a real carrier call.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env

PYTHONPATH=src python -m pytest -q
```

For an offline demonstration, use:

```
TELEPHONY_PROVIDER=simulated
RAG_EMBEDDING_PROVIDER=sentence_transformers
RAG_EMBEDDING_DIM=384
SENTENCE_TRANSFORMER_MODEL=Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet
SENTENCE_TRANSFORMER_DEVICE=cpu
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.6-flash
```

Gemini answer generation requires a valid `GEMINI_API_KEY`. The default local embedding provider is the Arabic Sentence Transformer `Omartificial-Intelligence-Space/Arabic-MiniLM-L12-v2-all-nli-triplet`, which produces 384-dimensional vectors. Apply migration `202608230011_switch_to_arabic_sentence_transformer_384.sql` and re-index existing documents before querying. An OpenAI-compatible provider remains optional, but its configured dimension must equal `RAG_EMBEDDING_DIM`.

## Supabase setup

Create a Supabase project, apply every SQL file under `supabase/migrations/` in filename order, configure the private Storage bucket, and bootstrap the first platform administrator through a controlled SQL procedure. The schema includes organizations, profiles, platform administrators, memberships, customers, support cases, follow-up tasks, calls, call events, call turns, escalations, FCR reports, knowledge documents, knowledge chunks, conversations, messages, and audit events.

Configure these server-side values in `.env`:

```
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=server-only-service-role-key
DATABASE_URL=postgresql://...
```

Prefer JWKS JWT verification by leaving `SUPABASE_JWT_SECRET` empty unless the project uses a legacy HS256 configuration. Never expose the service-role key to the browser or Gradio client.

## Vonage configuration

For live calling, create a Vonage Voice Application with Voice capability, configure the answer and event URLs, assign a supported Vonage number, and expose the API through a public HTTPS hostname.

```
TELEPHONY_PROVIDER=vonage
VONAGE_APPLICATION_ID=your-application-id
VONAGE_PRIVATE_KEY_PATH=private.key
VONAGE_PUBLIC_KEY_PATH=public.key
VONAGE_FROM_NUMBER=your-vonage-virtual-number
VONAGE_VERIFY_WEBHOOKS=true
PUBLIC_WEBHOOK_BASE_URL=https://YOUR-PUBLIC-API-HOST
```

Configure the Vonage application callbacks as:

```
https://YOUR-PUBLIC-API-HOST/vonage/answer
https://YOUR-PUBLIC-API-HOST/vonage/event
```

Use one authorized internal test number first. Confirm that resolved calls finish as `ANSWERED_RESOLVED` and synchronize the linked case to `RESOLVED`, unresolved calls create an escalation, no-answer calls retry according to policy, duplicate callbacks are harmless, and no live transfer occurs.

## Run the services directly

Start the API, Gradio UI, and scheduler in separate terminals:

```bash
# Terminal 1: API
PYTHONPATH=src uvicorn outbound_ai.api.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Gradio UI
PYTHONPATH=src python -m outbound_ai.ui.app

# Terminal 3: scheduler
PYTHONPATH=src python scripts/run_scheduler.py
```

The API health endpoint is `GET /health`. The main authenticated surfaces include `/campaign/*`, `/agent/*`, `/documents/*`, `/reports/*`, `/admin/*`, and `/auth/*`. User-facing requests require a Supabase bearer token and an organization context. Vonage callbacks use the configured provider verification mode.

## Run with Docker Compose

Copy `.env.example` to `.env`, configure the secrets and provider settings, then run:

```bash
docker compose up --build -d
docker compose logs -f api scheduler ui
```

The default ports are `8000` for FastAPI and `7860` for Gradio. For production, place TLS and authentication controls in front of the services, keep the Gradio console restricted, store secrets in a secret manager, and run the scheduler under a supervised process or container orchestrator.

## Work allocation for four people

The following plan divides the remaining work into four ownership areas. The owners can work in parallel after the interfaces and event contracts are agreed, but the voice and agentic tracks depend on stable data schemas and traceable call/message identifiers.

| Person | Ownership area | Main tasks | Expected deliverables | Dependencies and acceptance criteria |
| --- | --- | --- | --- | --- |
| **Person 1** | Backend, observability, and RAG testing | Complete the backend audit/logging system; define event taxonomy and correlation IDs; expand audit events for authentication, invitations, organization changes, documents, queries, calls, outcomes, and escalations; protect sensitive data in logs; test RLS and tenant isolation; build RAG evaluation datasets and regression tests for Arabic retrieval, citations, and answer grounding | Observability design, structured event schema, expanded audit repository, redaction tests, RAG evaluation dataset, retrieval regression suite, tenant-isolation test report, log search/retention plan | Must coordinate identifiers with all other people. Acceptance requires traceability from request to call/task/event, no credential leakage, zero cross-tenant retrieval, and measurable RAG regression coverage |
| **Person 2** | Telephony, Vonage integration, output enhancement, and UI | Integrate Vonage application credentials and tokens safely; validate private/public key handling, webhook verification, caller ID, and environment configuration; improve call initiation and callback behavior; replace raw JSON-only UI output with readable Arabic status cards, tables, timestamps, and actionable error messages while keeping JSON APIs for integrations; improve the Gradio calling, scheduling, administration, and results screens | Vonage token/configuration guide, secret-validation checks, provider acceptance test, improved Arabic UI components, human-readable call/task/report outputs, updated Gradio screens, API/UI contract tests | Depends on stable call and event schemas from the backend. Acceptance requires a simulated end-to-end call, a controlled Vonage test call, clear UI output, preserved machine-readable API responses, and no secrets displayed in the UI |
| **Person 3** | Agentic workflow and interactive LLM voice calls | Implement the LangGraph/LangChain/LangSmith workflow; define tenant-aware graph state and safe tools; add prompt versioning and evaluation; design a turn-by-turn customer conversation in which the LLM understands the customer, asks follow-up questions, and responds through Arabic TTS; integrate STT input, conversation memory, interruption handling, timeouts, escalation, and final outcome routing | Agent graph, tool contracts, LangSmith tracing/evaluations, prompt registry, interactive voice state machine, LLM/TTS/STT integration, multi-turn Arabic call demo, voice safety and fallback policy | Depends on Person 1’s audit/correlation contracts and Person 2’s Vonage callback integration. Acceptance requires reproducible traces, tenant-safe tool calls, a complete Egyptian-Arabic multi-turn call, correct escalation behavior, and no live transfer |
| **Person 4** | Multimodal, OCR, and complex-file support | Add image uploads, scanned-PDF OCR, table extraction, image/document understanding, MIME detection, size limits, safe file handling, and support for additional complicated formats; preserve page, image, table, and source provenance; connect extracted content to the organization-scoped RAG pipeline | Multimodal ingestion pipeline, OCR adapters, file-security policy, supported-format matrix, page/image/table citations, sample fixtures, ingestion tests, deployment notes | Depends on the document/chunk metadata and Storage policies. Acceptance requires organization filtering, malicious-file rejection, successful Arabic queries over scanned documents and images, and verifiable source provenance |

## Cross-cutting work that should not be missed

The four ownership areas cover the main implementation tracks, but some responsibilities must be shared rather than left unassigned. The team should nominate one person for each responsibility during planning and review it at every milestone.

| Cross-cutting responsibility | Why it matters | Suggested coordination |
| --- | --- | --- |
| Database and API contract changes | Interactive voice, agentic tools, multimodal documents, logs, and UI output all depend on stable schemas and endpoint contracts | Person 1 owns the contract review; every schema change requires migration, RLS review, API tests, and an updated README/runbook |
| Security and tenant isolation | New graph tools, OCR workers, logs, files, and voice callbacks can become data-leak paths | Person 1 leads security tests; every contributor must prove organization filtering and avoid exposing service-role credentials |
| Privacy, consent, and retention | Voice transcripts, audio, OCR text, customer issues, and logs may contain sensitive data | Person 2 leads voice consent and recording policy; Person 1 leads log/audit retention; Person 4 leads uploaded-file retention and deletion behavior |
| End-to-end testing and acceptance | Unit tests alone cannot prove the complete path from upload or call to RAG answer, escalation, and report | Person 2 owns telephony acceptance, Person 4 owns multimodal acceptance, and Person 1 maintains cross-tenant/RAG regression tests |
| Deployment and operations | Tokens, webhook URLs, worker supervision, storage, backups, and observability must work outside a developer laptop | Person 2 documents Vonage deployment; Person 1 documents observability and incident response; the whole team signs off the Docker/Codespaces runbook |
| Prompt and embedding quality | Interactive voice and RAG quality depend on prompt versions, Arabic examples, embedding choice, chunking, reranking, and evaluation | Person 3 owns prompt/agent quality; Person 1 owns repeatable RAG tests and benchmark reporting |

## Recommended implementation order

### Phase 1: Backend contracts, logging, and RAG testing

Person 1 should first define stable identifiers and event contracts for organization, user, case, call, follow-up task, document, conversation, message, and agent run. The same identifiers must appear in API logs, database audit events, provider callbacks, RAG evaluations, and future LangSmith traces. At the same time, Person 1 should create Arabic retrieval fixtures and tenant-isolation regression tests.

### Phase 2: Vonage integration, UI, and output improvement

Person 2 should validate Vonage credentials, token/key configuration, webhook verification, and provider callbacks using the simulator before a controlled live test. The UI should then present human-readable Arabic results rather than forcing users to interpret raw JSON. JSON should remain available behind the API and in an expandable technical-details view so integrations and debugging do not lose structured data.

### Phase 3: Agentic orchestration and interactive voice

Person 3 should build the agent graph around explicit tenant-aware tools and then connect it to the interactive phone state machine. The first milestone should support one controlled Egyptian-Arabic question-and-answer loop using STT input, LLM reasoning, Arabic TTS output, timeout handling, and a terminal resolved/escalated decision. LangSmith tracing should only be enabled after sensitive-data redaction and organization isolation are verified.

### Phase 4: Multimodal ingestion and full acceptance

Person 4 should extend the ingestion contract with MIME validation, file-size limits, OCR output, page coordinates, image/table provenance, and safe deletion behavior. The final acceptance suite should test the complete path: upload → tenant-filtered ingestion → OCR/multimodal extraction → retrieval → Arabic answer → citation → call/escalation workflow.

## Production checklist

Before handling real customers, apply and review all migrations, bootstrap the platform administrator, configure JWT verification, confirm RLS and organization-isolation tests, configure private Storage, set a valid Gemini or approved LLM provider, configure Vonage and public HTTPS callbacks, and run an authorized internal live-call test.

The operations team should also configure supervised scheduler execution, database backups, secret rotation, log retention, alerting, health checks, rate limits, file upload limits, provider failure handling, and a documented deletion process for customer data. Audio recording must not be enabled without explicit consent language, access controls, retention rules, and a compliance review.

## Key documentation

| Document | Purpose |
| --- | --- |
| [`docs/00_use_case.md`](docs/00_use_case.md) | Requirements baseline and agreed post-call behavior |
| [`docs/05_voice_design.md`](docs/05_voice_design.md) | Vonage voice flow, Arabic TTS/STT responsibility, transcript boundaries, and recording status |
| [`docs/06_database.md`](docs/06_database.md) | PostgreSQL, Supabase, RLS, Storage, and pgvector design |
| [`docs/vonage_integration.md`](docs/vonage_integration.md) | Vonage application, webhook, and live-call setup |
| [`docs/08_completeness_audit.md`](docs/08_completeness_audit.md) | Completion audit and operational boundaries |
| [`docs/09_codespaces_deployment_runbook.md`](docs/09_codespaces_deployment_runbook.md) | Codespaces deployment and demonstration procedure |
| [`docs/architecture_presentation_guide.md`](docs/architecture_presentation_guide.md) | Architecture explanation for project presentation |

## References

[1]: docs/00_use_case.md "Use-case requirements"

[2]: docs/05_voice_design.md "Voice design and provider boundaries"

[3]: docs/06_database.md "Database and tenant isolation design"

[4]: docs/08_completeness_audit.md "Completeness audit"

[5]: docs/vonage_integration.md "Vonage integration guide"

[6]: docs/architecture_presentation_guide.md "Architecture presentation guide"

This README describes the repository as it currently exists and clearly distinguishes implemented functionality from planned extensions. External provider accounts, credentials, public HTTPS infrastructure, and production acceptance testing remain deployment responsibilities rather than repository defaults.

---

## Gap Analysis vs Reference Implementation (Team Member A Branch)

The following table compares this repository against the reference implementation in eature/agentic-voice-rag-team-member-a (https://github.com/mamdouh-salem/Ai_Arabic_Outbound_calls_Rag_Assistance.git). Items marked ❌ are **missing or significantly different** and require implementation.

### Telephony & Voice Layer

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-turn NCCO dialogue | ❌ | Single answer → input flow only. No update_call_ncco for mid-call NCCO updates. |
| ElevenLabs TTS integration | ❌ | Only Vonage native 	alk or local MMS-TTS. No ElevenLabs streaming. |
| ElevenLabs voice caching | ❌ | No audio cache with hash-based deduplication. |
| Hold audio synthesis | ❌ | No pre-synthesized looping hold message. |
| Conversation UUID adoption | ❌ | Mid-call NCCO transfer changes conversation_uuid; no adoption logic. |
| Negation-aware resolution detection | ❌ | Basic keyword matching only. Arabic negation (
