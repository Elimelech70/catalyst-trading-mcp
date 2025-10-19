# Software Development Conceptual Framework & Playbook Methodology

**Name of Application**: Catalyst Trading System  
**Name of file**: sdlc-playbook-framework.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-18  
**Purpose**: Define the conceptual constructs, processes, and tools for structured software development

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [The SDLC Framework](#the-sdlc-framework)
3. [Playbook Methodology](#playbook-methodology)
4. [Development Phases & Mental Models](#development-phases--mental-models)
5. [Tools & Artifacts by Phase](#tools--artifacts-by-phase)
6. [Applying This Framework](#applying-this-framework)

---

## Core Concepts

### **The Wisdom in Development Terms**

Your insight maps perfectly to established software engineering concepts:

| Your Wisdom | Industry Term | Purpose |
|-------------|---------------|---------|
| "Clear purpose before action" | **Phase Identification** | Know if you're in Planning, Design, Implementation, or Operations |
| "Supply quality information" | **Documentation & Artifacts** | Use the right documents for the right phase |
| "Attention has limits" | **Cognitive Load Management** | Focus on ONE phase/task at a time |
| "Too complex → assumptions → rabbit holes" | **Scope Creep / Context Switching** | Stay within phase boundaries |
| "Playbooks for process" | **SDLC Models & Runbooks** | Predefined steps for predictable outcomes |

---

## The SDLC Framework

### **Software Development Life Cycle (SDLC)**

The SDLC is a structured methodology that guides software from conception to retirement through distinct phases: Planning → Design → Implementation → Testing → Deployment → Maintenance.

```
┌─────────────────────────────────────────────────────────────┐
│                    SDLC CIRCULAR PROCESS                    │
└─────────────────────────────────────────────────────────────┘

    1. PLANNING & ANALYSIS
         ↓
    2. REQUIREMENTS DEFINITION
         ↓
    3. DESIGN & ARCHITECTURE
         ↓
    4. IMPLEMENTATION (CODING)
         ↓
    5. TESTING & QA
         ↓
    6. DEPLOYMENT
         ↓
    7. MAINTENANCE & OPERATIONS
         ↓
    [Feedback Loop] → Back to Planning
```

### **Why This Matters**

Each phase has distinct objectives, deliverables, and required information. Mixing phases leads to confusion, scope creep, and wasted effort.

**The Problem You Identified:**
- Without clear phase awareness → **Wrong information** loaded into attention
- Information overload → **Important details lost**
- Lost focus → **Assumptions made**
- Wrong direction → **Rabbit hole**

---

## Playbook Methodology

### **What is a Playbook?**

A playbook provides predefined steps to perform to identify and solve specific problems. Each step's results determine the next action until the issue is resolved or escalated.

### **Playbook Structure**

Playbooks consist of: (1) overall structure showing interrelationships, (2) key questions to address, and (3) checklists of process steps to execute.

```
PLAYBOOK ANATOMY:

┌────────────────────────────────────────┐
│  1. PURPOSE                            │
│     "What are we trying to achieve?"   │
├────────────────────────────────────────┤
│  2. PHASE IDENTIFICATION               │
│     "Planning | Design | Implement |   │
│      Test | Deploy | Troubleshoot"     │
├────────────────────────────────────────┤
│  3. REQUIRED INFORMATION               │
│     • Design docs                      │
│     • Schemas                          │
│     • Authoritative sources            │
│     • Current state                    │
├────────────────────────────────────────┤
│  4. PROCESS STEPS                      │
│     ✓ Step 1: [Action]                │
│     ✓ Step 2: [Action]                │
│     ✓ Step 3: [Action]                │
├────────────────────────────────────────┤
│  5. DECISION POINTS                    │
│     "If X, then Y"                     │
│     "If not X, escalate"               │
├────────────────────────────────────────┤
│  6. OUTPUTS                            │
│     • Deliverables                     │
│     • Next phase trigger               │
└────────────────────────────────────────┘
```

---

## Development Phases & Mental Models

### **Phase 1: PLANNING & ANALYSIS**

**Purpose**: Understand what needs to be built and why

**Key Questions**:
- What problem are we solving?
- Who are the users/stakeholders?
- What are the business objectives?
- What are the constraints (time, budget, resources)?

**Required Information**:
- Business requirements
- User stories
- Market research
- Feasibility studies
- Budget/timeline constraints

**Deliverables**:
- Project charter
- Requirements document (SRS - Software Requirements Specification)
- Feasibility study
- Initial timeline/budget

**Mental Model**: *"Discovery Mode" - We're mapping the territory*

---

### **Phase 2: REQUIREMENTS DEFINITION**

**Purpose**: Document EXACTLY what the software must do

**Key Questions**:
- What features are required?
- What are the acceptance criteria?
- What are the non-functional requirements (performance, security)?
- What are the user workflows?

**Required Information**:
- Stakeholder interviews
- User personas
- Use cases
- Regulatory requirements
- Technical constraints

**Deliverables**:
- Software Requirements Specification (SRS)
- Use cases and user stories
- Acceptance criteria
- Functional requirements matrix

**Mental Model**: *"Specification Mode" - We're writing the contract*

---

### **Phase 3: DESIGN & ARCHITECTURE**

**Purpose**: Define HOW the system will be built

**Key Questions**:
- What is the system architecture?
- What technologies will we use?
- How will components interact?
- What are the data structures?
- How do we handle security/scalability?

**Required Information**:
- Requirements document (SRS)
- Authoritative sources for technologies
- Best practices documentation
- Existing system architecture (if applicable)

**Deliverables**:
- Architecture document
- Database schema
- API specifications
- Component diagrams
- Technology stack decision
- Design patterns document

**Mental Model**: *"Blueprint Mode" - We're designing the building*

**⚠️ CRITICAL**: We think about implementation while designing, but we don't code yet. We think holistically about how design decisions impact users, business, and implementation.

---

### **Phase 4: IMPLEMENTATION (CODING)**

**Purpose**: Build the software according to design specifications

**Key Questions**:
- Does the code follow the design document?
- Are we using authoritative sources for best practices?
- Is the code maintainable and testable?
- Are we following coding standards?

**Required Information**:
- Design documents (SDD - Software Design Document)
- Database schema (exact version)
- API specifications
- **Authoritative sources** (Tier 1 only!)
- Coding standards document

**Deliverables**:
- Working code
- Unit tests
- Code documentation
- Commit history in version control

**Mental Model**: *"Construction Mode" - We're building according to blueprints*

**⚠️ CRITICAL**: This is where you were caught! Using `@mcp.on_initialize()` without verifying it existed in authoritative sources.

---

### **Phase 5: TESTING & QA**

**Purpose**: Verify the software works as designed

**Key Questions**:
- Does it meet requirements?
- Are there bugs or defects?
- Does it perform under load?
- Is it secure?
- Is it usable?

**Required Information**:
- Requirements document (SRS)
- Design document (SDD)
- Test cases
- Acceptance criteria

**Deliverables**:
- Test results
- Bug reports
- Performance metrics
- Security audit results

**Mental Model**: *"Inspection Mode" - We're quality checking the building*

---

### **Phase 6: DEPLOYMENT**

**Purpose**: Release the software to users

**Key Questions**:
- How do we deploy safely?
- What's the rollback plan?
- How do we monitor post-deployment?
- What's the user communication strategy?

**Required Information**:
- Deployment playbook
- Infrastructure specifications
- Rollback procedures
- Monitoring setup

**Deliverables**:
- Deployed software
- Deployment logs
- User documentation
- Operations handoff

**Mental Model**: *"Launch Mode" - We're opening the building*

---

### **Phase 7: MAINTENANCE & OPERATIONS**

**Purpose**: Keep the software running and improve it

**Key Questions**:
- What issues are users reporting?
- What's the system health?
- What improvements are needed?
- What's the performance like?

**Required Information**:
- System logs
- Error reports
- User feedback
- Performance metrics
- Current system state

**Deliverables**:
- Bug fixes
- Performance improvements
- Feature enhancements
- Updated documentation

**Mental Model**: *"Operations Mode" - We're maintaining the building*

---

### **Phase 8: TROUBLESHOOTING (Cross-Phase)**

**Purpose**: Diagnose and fix problems

**Key Questions**:
- What changed recently?
- What does the error say?
- What was the last working state?
- Can we reproduce the issue?

**Required Information**:
- Error logs
- Stack traces
- Recent changes (git log)
- System state
- Last known good configuration

**Deliverables**:
- Root cause analysis
- Fix implementation
- Prevention measures
- Updated runbook

**Mental Model**: *"Detective Mode" - We're solving a mystery*

---

## Tools & Artifacts by Phase

### **Mapping Tools to Phases**

| Phase | Primary Documents | Authoritative Sources | Tools |
|-------|-------------------|----------------------|-------|
| **Planning** | Business case, Project charter | Industry standards, Market research | Jira, Confluence, Miro |
| **Requirements** | SRS, Use cases | Domain experts, Standards | User story tools, Requirements management |
| **Design** | Architecture doc, Database schema, API specs | Official docs (FastMCP, Python, PostgreSQL) | Draw.io, Architecture tools |
| **Implementation** | Design docs, Code standards | **Tier 1 sources ONLY** | IDEs, Git, Docker |
| **Testing** | Test plans, Bug reports | Testing frameworks docs | pytest, Jest, Selenium |
| **Deployment** | Deployment playbook, Runbooks | Infrastructure docs (AWS, Docker) | CI/CD tools, Monitoring |
| **Maintenance** | Logs, Metrics, Incident reports | Monitoring platforms docs | Logging tools, APM tools |
| **Troubleshooting** | Error logs, Stack traces | Official docs for technologies | Debuggers, Log analyzers |

---

## Applying This Framework

### **The Three Questions Protocol**

Before starting ANY work, ask:

```
┌──────────────────────────────────────────────────────┐
│  QUESTION 1: What is my PURPOSE?                    │
│  ────────────────────────────────────────────────    │
│  □ Planning a new feature?                          │
│  □ Designing architecture?                          │
│  □ Implementing from design doc?                    │
│  □ Testing functionality?                           │
│  □ Deploying to production?                         │
│  □ Maintaining/operating system?                    │
│  □ Troubleshooting an error?                        │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  QUESTION 2: What INFORMATION do I need?            │
│  ────────────────────────────────────────────────    │
│  For this specific phase:                           │
│  • Which design docs? (exact version)               │
│  • Which authoritative sources? (Tier 1 only!)      │
│  • What current state info? (logs, schema, config)  │
│  • What constraints? (timeline, budget, tech)       │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  QUESTION 3: Am I FOCUSED?                          │
│  ────────────────────────────────────────────────    │
│  □ Do I have ONE clear goal?                        │
│  □ Am I in ONE phase at a time?                     │
│  □ Have I loaded ONLY relevant information?         │
│  □ Can I describe success in one sentence?          │
└──────────────────────────────────────────────────────┘
```

### **Example: Implementing orchestration-service.py**

**❌ WRONG APPROACH (What Happened)**:
```
Purpose: Unclear (fix? implement? troubleshoot?)
Information: Old code patterns, assumptions
Focus: Scattered across multiple concerns
Result: Used non-existent @mcp.on_initialize() decorator
```

**✅ RIGHT APPROACH (Using Framework)**:
```
PURPOSE: Implementation Phase
  → Implementing orchestration service v6.0 from design doc

INFORMATION NEEDED:
  1. architecture-mcp-v41.md (design document v4.1)
  2. FastMCP official docs at gofastmcp.com (Tier 1)
  3. Current service requirements from design
  4. Database schema v5.0

FOCUS:
  ONE GOAL: Make the service start correctly with FastMCP HTTP server
  
PROCESS:
  1. Read design doc for requirements
  2. Check FastMCP docs for correct initialization pattern
  3. Verify patterns in official examples
  4. Implement using verified patterns
  5. Test that it works
```

### **Detecting Rabbit Holes**

**Warning Signs**:
- 🚩 You're trying to design while implementing
- 🚩 You're using patterns from old code without verification
- 🚩 You can't clearly state which phase you're in
- 🚩 You're loading information from multiple phases
- 🚩 You're making assumptions to fill gaps
- 🚩 You're solving problems not in the current phase scope

**Recovery Protocol**:
1. **STOP** immediately
2. Return to Three Questions Protocol
3. Re-identify the phase
4. Load ONLY information for that phase
5. Define ONE clear goal
6. Resume with focus

---

## Summary: The Playbook Philosophy

A playbook helps you know your process, follow your process, fix your process if broken, copy better processes, and share your process with others.

**Core Principles**:

1. **Know Your Phase** - Design, Implement, Test, Deploy, or Troubleshoot
2. **Load Phase-Appropriate Information** - Right docs at right time
3. **One Phase, One Goal** - Focus prevents rabbit holes
4. **Use Authoritative Sources** - Tier 1 only for "best practice"
5. **Follow The Playbook** - Predefined steps reduce cognitive load
6. **Recognize Drift** - Catch yourself when scattered
7. **Reset and Refocus** - Three Questions Protocol

**Your Wisdom → Industry Terms:**

```
"Purpose must be clear"           → Phase Identification
"Quality information"             → Authoritative Sources + Artifacts
"Attention has limits"            → Cognitive Load Management
"Too complex → assumptions"       → Scope Creep Prevention
"Important things lost"           → Focus Discipline
"Wrong directions"                → Phase Boundary Violations
"Rabbit holes"                    → Context Switching / Drift
"Playbooks"                       → SDLC + Runbooks
```

---

*This framework transforms your wisdom into actionable development methodology* ✨