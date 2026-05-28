# Project Context: AI-Powered Restaurant Recommendation System (Zomato Use Case)

This document stores the full context derived from `docs/problemStatement.txt`. Use it as the single source of truth when designing, implementing, or reviewing this project.

---

## Problem Summary

Build an **AI-powered restaurant recommendation service** inspired by Zomato. The system intelligently suggests restaurants based on user preferences by combining **structured restaurant data** with a **Large Language Model (LLM)**.

---

## Primary Objective

Design and implement an application that:

1. **Takes user preferences** — location, budget, cuisine, ratings, and related inputs
2. **Uses a real-world dataset** — Zomato-style restaurant records
3. **Leverages an LLM** — to generate personalized, human-like recommendations
4. **Displays clear, useful results** — easy for the end user to understand and act on

---

## System Workflow

The application follows five stages, from data load through final display.

### Stage 1: Data Ingestion

| Requirement | Detail |
|-------------|--------|
| **Source** | Hugging Face dataset: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) |
| **Actions** | Load and preprocess the dataset |
| **Fields to extract** | Restaurant name, location, cuisine, cost, rating, and other relevant columns |

### Stage 2: User Input

Collect the following preferences from the user:

| Preference | Examples |
|--------------|----------|
| **Location** | Delhi, Bangalore |
| **Budget** | low, medium, high |
| **Cuisine** | Italian, Chinese |
| **Minimum rating** | Numeric threshold |
| **Additional preferences** | family-friendly, quick service, etc. |

### Stage 3: Integration Layer

- Filter and prepare restaurant data that matches user input
- Pass structured, filtered results into an LLM prompt
- Design a prompt that helps the LLM **reason** and **rank** options

### Stage 4: Recommendation Engine (LLM)

Use the LLM to:

- **Rank** restaurants by fit for the user
- **Provide explanations** — why each recommendation matches the preferences
- **Optionally summarize** the overall set of choices

### Stage 5: Output Display

Present **top recommendations** in a user-friendly format. Each item should show:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation

---

## Data Source

| Item | Value |
|------|--------|
| Platform | Hugging Face |
| Dataset ID | `ManikaSaini/zomato-restaurant-recommendation` |
| URL | https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation |

---

## End-to-End Flow

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌─────────────┐    ┌────────────────┐
│   Dataset   │───▶│ User prefs   │───▶│ Filter & prep   │───▶│ LLM rank +  │───▶│ Top picks with │
│  (HF load)  │    │  (input UI)  │    │ (integration)   │    │  explain    │    │ structured UI  │
└─────────────┘    └──────────────┘    └─────────────────┘    └─────────────┘    └────────────────┘
```

**In order:**

1. **Ingest** — Load Hugging Face data; preprocess; retain name, location, cuisine, cost, rating, etc.
2. **Collect** — Gather location, budget, cuisine, min rating, and optional extras
3. **Filter** — Narrow candidates to those matching structured constraints
4. **Recommend** — LLM ranks filtered set, explains each pick, may summarize
5. **Display** — Show ranked list with metadata plus natural-language rationale

---

## Design Principles (from problem statement)

| Principle | Meaning |
|-----------|---------|
| **Structured + LLM** | Do not rely on the LLM alone over the full raw dataset; filter structured data first, then use the LLM for ranking and explanation |
| **Personalization** | Output must reflect the user’s specific combination of preferences |
| **Transparency** | Every recommendation includes a human-readable reason it fits |
| **Usability** | Results are scannable: name, cuisine, rating, cost, and explanation |

---

## Success Criteria

The implementation meets the problem statement when a user can:

1. Enter preferences (location, budget, cuisine, minimum rating, and optional extras)
2. Receive recommendations grounded in real Zomato-style data from the Hugging Face dataset
3. See a ranked list where each entry includes structured fields and an LLM-generated explanation
4. Trust that candidates respect stated constraints before ranking and explanation

---

## Open Decisions (not defined in problem statement)

These are left to implementation; they are **not** requirements from `problemStatement.txt`:

- Tech stack (language, framework, UI)
- LLM provider and model
- Number of top results (project folder name suggests **top 5** as a reasonable default)
- Authentication, persistence, or deployment
- API vs. CLI vs. web UI

---

## Traceability

| Problem statement section | Covered in this doc |
|---------------------------|---------------------|
| Title & one-line description | Problem Summary |
| Objective (4 bullets) | Primary Objective |
| Data Ingestion | Stage 1, Data Source |
| User Input | Stage 2 |
| Integration Layer | Stage 3 |
| Recommendation Engine | Stage 4 |
| Output Display | Stage 5 |
| Dataset URL | Data Source, Stage 1 |

**Source file:** `docs/problemStatement.txt`
