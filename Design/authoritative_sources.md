# Catalyst Trading System - Authoritative Documentation Sources

**Name of Application**: Catalyst Trading System  
**Name of file**: authoritative-sources.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-18  
**Purpose**: Define what constitutes "official" and "currently documented" sources

---

## TIER 1: PRIMARY AUTHORITATIVE SOURCES

These are the ONLY sources that constitute "official documentation" and "best practice":

### **FastMCP (MCP Server Framework)**
- **Official Site**: https://gofastmcp.com/
- **GitHub**: https://github.com/jlowin/fastmcp
- **PyPI**: https://pypi.org/project/fastmcp/
- **Valid for**: FastMCP API, decorators, transport options, lifecycle management

**How to verify it's current:**
- Check version number matches installed version
- Check "last updated" date is recent (2024-2025)
- Confirm in GitHub main branch, not old issues

---

### **Anthropic (Claude & MCP Protocol)**
- **MCP Specification**: https://modelcontextprotocol.io/
- **Anthropic Docs**: https://docs.anthropic.com/
- **Claude Desktop**: https://claude.ai/download
- **Valid for**: MCP protocol specification, Claude Desktop configuration, official MCP concepts

**How to verify it's current:**
- Official Anthropic domain only
- Protocol version matches (currently 2024-11-05)
- Not community tutorials or third-party interpretations

---

### **Python Language**
- **Official Docs**: https://docs.python.org/3/
- **PyPI**: https://pypi.org/ (for official package versions)
- **PEPs**: https://peps.python.org/ (Python Enhancement Proposals)
- **Valid for**: Python language features, standard library, typing, async/await

**How to verify it's current:**
- docs.python.org domain only
- Version matches your Python version (3.10, 3.11, etc.)
- Not blogs, tutorials, or Stack Overflow

---

### **Docker**
- **Official Docs**: https://docs.docker.com/
- **Docker Hub**: https://hub.docker.com/ (for official images)
- **Valid for**: Dockerfile syntax, docker-compose.yml, container best practices

**How to verify it's current:**
- docs.docker.com domain only
- Version matches your Docker version
- Not third-party Docker tutorials

---

### **FastAPI**
- **Official Docs**: https://fastapi.tiangolo.com/
- **GitHub**: https://github.com/tiangolo/fastapi
- **Valid for**: FastAPI framework, REST APIs, WebSocket endpoints

**How to verify it's current:**
- fastapi.tiangolo.com domain only
- Version matches installed FastAPI version
- Creator's (Sebastián Ramírez) official site

---

### **Nginx**
- **Official Docs**: https://nginx.org/en/docs/
- **Valid for**: Nginx configuration, reverse proxy, SSL/TLS setup

**How to verify it's current:**
- nginx.org domain only
- Matches your Nginx version
- Not blog posts or tutorials

---

### **PostgreSQL**
- **Official Docs**: https://www.postgresql.org/docs/
- **Valid for**: Database schema, SQL syntax, asyncpg compatibility

**How to verify it's current:**
- postgresql.org domain only
- Version-specific docs (e.g., PostgreSQL 14, 15, 16)

---

## TIER 2: ACCEPTABLE SECONDARY SOURCES

These can be used for **examples and context**, but NOT as authoritative "best practice":

### **Official Package Documentation on Read the Docs**
- **asyncpg**: https://magicstack.github.io/asyncpg/
- **aiohttp**: https://docs.aiohttp.org/
- **Pydantic**: https://docs.pydantic.dev/

**Usage rules:**
- ✅ Can reference for API usage examples
- ✅ Can cite for specific function parameters
- ❌ Cannot claim as "best practice" without primary source
- ❌ Must verify against primary source if critical

---

### **Official GitHub Repositories**
- FastMCP Issues/Discussions (for known bugs, workarounds)
- Python SDK repositories (for implementation details)

**Usage rules:**
- ✅ Can reference for bug reports and known issues
- ✅ Can use for version-specific workarounds
- ❌ Cannot use closed issues as "current best practice"
- ❌ Must check if issue is resolved in current version

---

## TIER 3: UNRELIABLE SOURCES

These should **NEVER** be cited as "best practice" or "official documentation":

### **Community Tutorials & Blogs**
- ❌ Medium articles
- ❌ Dev.to posts
- ❌ Personal blogs
- ❌ YouTube tutorials

**Why unreliable:**
- Often outdated within months
- May use deprecated patterns
- Author's interpretation, not official
- No guarantee of accuracy

---

### **AI-Generated Content**
- ❌ ChatGPT/Claude responses without sources
- ❌ Stack Overflow answers without verification
- ❌ Reddit posts
- ❌ Discord/Slack discussions

**Why unreliable:**
- May hallucinate APIs that don't exist
- Mix multiple versions/frameworks
- No accountability or verification
- Perpetuate outdated patterns

---

### **Old Project Code**
- ❌ Code from 6+ months ago in this project
- ❌ Deprecated examples in old commits
- ❌ Comments referencing old versions

**Why unreliable:**
- APIs change frequently
- FastMCP 1.0 → 2.0 had breaking changes
- May contain failed experiments
- No guarantee it ever worked correctly

---

## VERIFICATION PROTOCOL

Before claiming something is "best practice" or "currently documented":

### **Step 1: Find Primary Source**
```
Question: How do I initialize FastMCP?

✅ CORRECT:
- Search: https://gofastmcp.com/ for "initialization"
- Find: Official documentation on mcp.run()
- Cite: "According to FastMCP documentation at gofastmcp.com..."

❌ WRONG:
- Find pattern in old project code
- Assume it's correct
- Present as "best practice"
```

### **Step 2: Verify Currency**
```
Check:
- [ ] Is the documentation dated 2024-2025?
- [ ] Does version match installed version?
- [ ] Is this the current stable release?
- [ ] Are there newer deprecation notices?
```

### **Step 3: Cross-Reference**
```
If found in secondary source:
- [ ] Can I find same pattern in primary source?
- [ ] Is there a primary source citation?
- [ ] Does primary source confirm this approach?
```

### **Step 4: Test Logic**
```
Before presenting as solution:
- [ ] Does the API actually exist?
- [ ] Are parameters correctly named?
- [ ] Does the approach make logical sense?
- [ ] Have I seen this work in official examples?
```

---

## RESPONSE TEMPLATES

### **When I Have Primary Source:**
```
According to the official FastMCP documentation at gofastmcp.com/servers/server:

[Quote or paraphrase with proper citation]

This is the current best practice as of version 2.x.
```

### **When I Have Secondary Source Only:**
```
Based on the asyncpg documentation, this approach should work:

[Explanation]

However, I recommend verifying this against your specific use case.
Note: This is not an official "best practice" from primary sources.
```

### **When I'm Uncertain:**
```
I don't see this documented in the official FastMCP documentation.
Let me search the primary sources to find the correct approach.

[Then actually search primary sources]
```

### **When Source is Outdated:**
```
I found this pattern in [source], but it's from [date/version].
This may be deprecated. Let me check current documentation.

[Search current primary source]
```

---

## CITATION REQUIREMENTS

When referencing documentation:

### **Required Elements:**
1. **Source name**: "FastMCP documentation"
2. **URL**: https://gofastmcp.com/servers/server
3. **Version** (if critical): "FastMCP 2.12.4"
4. **Date verified**: "Verified October 2025"

### **Example Citation:**
```
According to the FastMCP Server documentation 
(https://gofastmcp.com/servers/server, verified October 2025),
the correct way to run an HTTP server is:

    mcp.run(transport="http", host="0.0.0.0", port=5000)

This is documented for FastMCP 2.x and is the current recommended approach.
```

---

## WHAT TO DO WHEN STUCK

### **If Primary Source Not Clear:**
1. Search official documentation thoroughly
2. Check official GitHub issues for clarification
3. Look for official examples in GitHub repo
4. **State uncertainty**: "The official docs don't clearly specify this..."
5. **Propose approach**: "Based on related documentation, I believe..."
6. **Offer to test**: "Would you like me to research this further?"

### **If Primary Source Missing:**
1. **State clearly**: "I cannot find this in official documentation"
2. **Explain gap**: "The FastMCP docs don't cover lifecycle management in detail"
3. **Suggest alternatives**: "We could either..."
4. **Ask user**: "Have you found any official guidance on this?"

### **If Sources Conflict:**
1. **Prioritize by tier**: Primary > Secondary > Tertiary
2. **Check dates**: Newer documentation supersedes older
3. **Note discrepancy**: "The docs say X, but the code example shows Y"
4. **Test if possible**: "Let me verify which approach actually works"

---

## QUALITY STANDARDS

### **"Best Practice" Checklist:**
- [ ] Found in Tier 1 primary source
- [ ] Currently documented (2024-2025)
- [ ] Version matches installed software
- [ ] Official domain/repository
- [ ] Recently verified (this month/quarter)
- [ ] Not deprecated or marked for removal
- [ ] Recommended by official docs

### **"Currently Documented" Checklist:**
- [ ] Exists in current official documentation
- [ ] Not marked as deprecated
- [ ] Available in current stable release
- [ ] Has official API documentation
- [ ] Appears in official examples

---

## COMMITMENT

When providing technical guidance:

### **I WILL:**
- ✅ Only cite Tier 1 sources for "best practice"
- ✅ Verify documentation is current
- ✅ Admit when I'm uncertain
- ✅ Show my sources explicitly
- ✅ Test logic before presenting

### **I WILL NOT:**
- ❌ Assume old code patterns are current
- ❌ Present blog posts as "official"
- ❌ Claim something is "documented" without source
- ❌ Use decorators/APIs without verifying they exist
- ❌ Present guesses as facts

---

## EXAMPLE: WHAT WENT WRONG

### **The @mcp.on_initialize() Mistake:**

**What I did:**
```python
@mcp.on_initialize()  # ❌ Doesn't exist!
async def initialize():
    pass
```

**How it happened:**
1. Found pattern in old project code (v4.4.0, Sept 2024)
2. Assumed it was standard FastMCP
3. Did NOT verify in FastMCP official docs
4. Did NOT search for "on_initialize FastMCP"
5. Presented as "best practice"

**What I should have done:**
1. Search https://gofastmcp.com/ for "initialize"
2. Search https://github.com/jlowin/fastmcp for "on_initialize"
3. Check FastMCP API reference
4. Realize this decorator doesn't exist
5. Find correct approach or admit uncertainty

**Correct approach (verified):**
```python
# Initialize manually before mcp.run()
asyncio.run(initialize())
mcp.run(transport="http")
```

**Why this is correct:**
- Source: FastMCP examples in GitHub
- No special decorator needed
- Standard Python async pattern
- Actually works

---

## SUMMARY

**"Currently Documented" = Tier 1 Primary Sources Only**

- FastMCP: https://gofastmcp.com/
- Anthropic: https://modelcontextprotocol.io/
- Python: https://docs.python.org/
- Docker: https://docs.docker.com/
- FastAPI: https://fastapi.tiangolo.com/
- Nginx: https://nginx.org/
- PostgreSQL: https://www.postgresql.org/

**Everything else is supplementary and must be verified against primary sources.**

---

*This document defines the standard for what constitutes authoritative, current, and reliable documentation for the Catalyst Trading System.*
