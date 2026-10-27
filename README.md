# Export Classification Check Service (ECS)
**Course:** UE24AM342AA5 — ML System Design and AgentOps
**Mini Project:** Project 07 — Export Classification Check Service
**Domain:** Logistics and Trade Compliance
**Institution:** PES University, Department of CSE (AI & ML)

## Project team
**SRN : NAME**

PES1UG24AM085 - Dhriti Kamani
PES1UG24AM096 - Diya Agarwal

This project was assigned as **Mini Project 07** in the course handout, `MiniProject_07_Export_Classification_Check.pdf`. The assignment asks for a production-style, multi-agent service—not a model-training notebook—that proposes HS tariff classifications with supporting evidence and an export-policy status.

---

## 1. Problem statement
Every export shipment must be classified under a Harmonized System (HS) code. The classification affects which export rules, licences, and accompanying documents may apply. Incorrect classification can delay a shipment at customs and may lead to penalties.

Classifying a product is not simply a keyword lookup. A trade-compliance analyst must interpret the product description, identify the article and its materials, search for candidate tariff headings, and apply the General Rules for Interpretation (GRI) in numerical order. Relevant section and chapter notes may change or exclude an otherwise plausible classification. For example, a product made from a particular material might also be described by a heading that specifically names the article.

The challenge addressed by this project is to build a service that helps automate this evidence-based review while remaining transparent about uncertainty. It should validate incoming shipment information, retrieve relevant tariff provisions, propose a classification grounded in the retrieved evidence, state the applicable export-policy status, and route uncertain cases to a human specialist rather than inventing a confident answer.

**Important boundary:** ECS provides a proposed classification and supporting evidence. It does not file an export declaration, replace a licensed customs broker, calculate duties, or prepare shipping documents.

## 2. Objectives

- Accept a product description and shipment details through a REST API and web interface.
- Validate request data before starting the classification workflow.
- Identify the product article and relevant material information.
- Retrieve candidate tariff headings and applicable rules/notes from the indexed corpus.
- Produce an evidence-based classification recommendation with citations where supported.
- Verify that cited evidence corresponds to retrieved passages.
- Escalate ambiguous or unsupported cases for clarification or specialist review.
- Expose service health and provide run details/traces for debugging and observability.
- Run the application components locally using Docker Compose.

## 3. Example demonstration scenario
The assignment specifies this difficult case:

> Stainless steel vacuum flask with a moulded plastic outer body.
This case is challenging because a material-based search may suggest a heading for steel goods, while a tariff heading may specifically name vacuum flasks. The system should search beyond the first plausible match, consider the relevant General Rules for Interpretation and notes, and cite the evidence used. If the available evidence does not support one unambiguous result, it should escalate the case.

The current development corpus includes curated tariff-related passages and PDF sources. **Export-policy entries and legal references must be checked against the applicable current official documents before any real-world use.** A successful API response or citation check is not, by itself, proof of legal correctness.

## 4. High-level workflow

1. **Request submission:** A user submits a product description and available shipment fields through the UI or REST API.
2. **Input validation:** The service checks the request against its accepted data structure.
3. **Classification workflow:** The backend starts the agent workflow for the request.
4. **Evidence retrieval:** The system searches the indexed corpus for potentially relevant tariff headings, rules, and notes.
5. **Reasoning and follow-up search:** The workflow can use retrieved information to guide further searches for other relevant provisions.
6. **Verification and routing:** The result is checked against retrieved evidence. Depending on the outcome, the service can return a recommendation or route the case for clarification/specialist review.
7. **Run inspection:** A run identifier can be used to inspect the run result and trace.
8. **Monitoring:** Health endpoints and the included Prometheus/Grafana services support operational inspection when configured.

## 5. Architecture and components
The project is organised as a containerised service. The current Compose setup includes:

- **API (`services/api/main.py`)** — exposes the REST interface and health/run-related endpoints.
- **Workflow runner (`ecs/runner.py`)** — invokes the classification workflow.
- **Agent logic (`ecs/agents.py`)** — contains classification/retrieval decision logic.
- **Ingestion/indexing (`ecs/ingest.py`)** — parses source material and builds the searchable corpus/index.
- **Corpus (`corpus/official/`, `corpus/official_case.txt`)** — PDF sources and curated evidence passages used during retrieval.
- **Redis** — supports service workflow/queue state in the Compose environment.
- **Agent worker** — processes classification work.
- **LLM stub** — provides a local stub endpoint for model/workflow integration or testing.
- **Prometheus** — metrics collection, depending on configured scrape targets.
- **Grafana** — metrics visualization when a data source and dashboard are configured.
The exact capabilities exposed by each component depend on the current configuration. The monitoring services should only be described as collecting or visualising a particular metric when that metric is actually configured and visible.

## 6. API endpoints
The current project includes these endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check service health and key dependencies |
| `POST` | `/v1/classify` | Submit a product classification request |
| `GET` | `/v1/runs/{run_id}` | Retrieve the result/status for a run |
| `GET` | `/v1/runs/{run_id}/trace` | Inspect execution trace details |
| `POST` | `/v1/feedback` | Submit feedback for a result |
| `GET` | `/v1/feedback/summary` | Retrieve aggregated feedback summary |

The accepted request fields and response schema are defined by the running API implementation. Consult its OpenAPI documentation at `http://localhost:8000/docs` while the service is running, if enabled, rather than assuming field names.

## 7. Technology stack

- **Python** — application and agent logic.
- **FastAPI** — REST API.
- **Docker Compose** — local multi-service execution.
- **Redis** — service state/queue support in the current setup.
- **Indexed tariff corpus** — searchable source passages from tariff-related documents.
- **Prometheus** — metrics collection when scrape targets are configured.
- **Grafana** — metrics dashboards when configured.
- **LLM stub service** — local testing/integration component.
This README documents the current project setup; it does not claim that every optional requirement in the assignment handout has been completed. Check the actual repository and live configuration before presenting a feature as implemented.

## 8. Prerequisites

- Windows with Docker Desktop installed and running.
- Git, if cloning the repository.
- A terminal such as PowerShell or the VS Code integrated terminal.
- The project repository and its required files.

## 9. Run locally
Open PowerShell or the VS Code terminal in the project directory.

```powershell
cd C:\Users\dhriti\Downloads\ecs-service
docker compose up -d
docker compose ps
```
Check the API health:

```powershell
Invoke-RestMethod http://localhost:8000/health
```
Open the web interface at:

- `http://localhost:8000`
Useful local tools:

- API documentation (if enabled): `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

### Rebuild after code changes

```powershell
docker compose up --build -d
```

### Stop the services

```powershell
docker compose stop
```
To start the stopped services again:

```powershell
docker compose start
```
Avoid `docker compose down -v` unless you intentionally want to remove the Compose volumes and understand the data-loss implications.

## 10. Demonstration checklist

1. Start the services using Docker Compose.
2. Show `docker compose ps` and the API health endpoint.
3. Open the UI and submit the assignment's vacuum-flask example.
4. Show the result, including the route/status and citations that the current implementation returns.
5. Explain why the system may request specialist review when multiple headings remain plausible.
6. Use the returned run ID to show the run result and trace endpoints.
7. Show Prometheus target health and a basic query if targets are configured.
8. Show Grafana dashboards only if a data source and dashboard are available.
9. Be transparent about source currency and any incomplete validation/evaluation features.

## 11. Current limitations and responsible use

- This is an academic prototype, not a legally authoritative customs-classification tool.
- The curated export-policy placeholder is not verified policy evidence. Do not present it as a confirmed current DGFT status.
- Source-document editions and extracted passages must be checked against current official CBIC/DGFT publications.
- Retrieval, citation resolution, and a verifier passing do not automatically establish that a classification is legally correct.
- Monitoring visibility depends on Prometheus scrape configuration and Grafana data-source/dashboard configuration.
- Do not claim that all requirements in Project 07 have been implemented unless they have been tested and documented.
For actual shipments, the proposed result must be reviewed by a qualified trade-compliance professional or licensed customs broker.

## 12. Assignment reference
The source assignment is **Mini Project 07 — Export Classification Check Service**, for **ML System Design & AgentOps (UE24AM342AA5)**. It defines the project context, difficult vacuum-flask scenario, multi-agent design expectations, LLMOps requirements, deployment/observability requirements, demonstration items, and deliverables.

The handout explicitly states that model training is not required, cloud deployment is not required, and duty calculation/shipping documentation are outside scope.

---
**Project team:**
**PES1UG24AM085 — Dhriti Kamani**
**PES1UG24AM096 — Diya Agarwal**
