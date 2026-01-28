# Emergent Architecture Framework

> **Core Principle:** Meaning emerges from structure, not specification.
> **Actionable Form:** Traverse the graph, don't annotate the nodes.

## When to Use This Skill

Trigger phrases:
- "I need to manually tag/label/specify every..."
- "How do I avoid hardcoding..."
- "This doesn't scale because..."
- "Apply emergent architecture"
- "/emergent"

## The Framework

### Step 1: Identify the Annotation Problem
What are you trying to specify for each element?
```
Examples:
- Voice IDs for every button
- Permissions for every API endpoint
- Documentation for every function
- Routing rules for every query
```

### Step 2: Find the Implicit Graph
What structure already exists that connects these elements?
```
Questions to ask:
- What contains these elements? (hierarchy)
- What do they connect to? (edges)
- What's near them? (proximity)
- What created them? (lineage)
- What do they affect? (causality)
```

### Step 3: Define Traversal Rules
How do you extract meaning from the structure?
```
Patterns:
- ANCESTOR: Walk up the tree (DOM → parent classes → section headers)
- NEIGHBOR: Check siblings (previous label, adjacent elements)
- AGGREGATE: Combine multiple sources (voting, consensus)
- INHERIT: Properties flow down (config inheritance)
- CLUSTER: Group by proximity (semantic similarity)
```

### Step 4: Implement the Core Function
Create ONE function that derives meaning from structure:
```typescript
function deriveContext(element) {
  // Traverse the graph
  // Aggregate structural signals
  // Return emergent meaning
}
```

### Step 5: Let Behavior Emerge
The system now self-organizes:
- New elements automatically get context
- Changes propagate through structure
- No manual annotation required

## Architecture Pattern Template

```
┌─────────────────────────────────────────────────────────┐
│                    SYSTEM BOUNDARY                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐              │
│   │ Simple  │───│ Simple  │───│ Simple  │  ← Nodes     │
│   │ Element │   │ Element │   │ Element │    (dumb)    │
│   └────┬────┘   └────┬────┘   └────┬────┘              │
│        │             │             │                    │
│        └─────────────┴─────────────┘                    │
│                      │                                  │
│              ┌───────▼───────┐                         │
│              │   TRAVERSAL   │  ← Core Function        │
│              │    FUNCTION   │    (smart)              │
│              └───────┬───────┘                         │
│                      │                                  │
│              ┌───────▼───────┐                         │
│              │   EMERGENT    │  ← Derived Meaning      │
│              │    CONTEXT    │                         │
│              └───────────────┘                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Examples

### Example 1: Voice UI (What We Built)
```
Problem: Need voice-id for every button
Graph: DOM hierarchy
Traversal: getComponentContext() walks up parents
Emergence: "biometric-panel-start-sensors" derived automatically
```

### Example 2: API Permissions
```
Problem: Need permissions for every endpoint
Graph: Route hierarchy + controller inheritance
Traversal: Walk up route tree, inherit from parent routes
Emergence: /admin/users/delete inherits admin.* permissions
```

### Example 3: Documentation
```
Problem: Need docs for every function
Graph: AST + type signatures + call graph
Traversal: Analyze function signature, callers, return usage
Emergence: Auto-generated docs from structural analysis
```

### Example 4: Query Routing (DQ Scoring)
```
Problem: Need quality score for every response
Graph: Agent network + voting topology
Traversal: Aggregate votes across agents
Emergence: Consensus-based DQ score
```

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Emergent Solution |
|--------------|---------|-------------------|
| Manual tagging | Doesn't scale | Traverse hierarchy |
| Hardcoded mappings | Brittle | Derive from structure |
| Central registry | Bottleneck | Distributed context |
| Explicit config per item | Verbose | Inherit from ancestors |

## The Meta-Principle

When stuck, ask:
> "What structure already exists that encodes this implicitly?"

The answer reveals the graph. The graph reveals the traversal. The traversal reveals the emergence.

## Quick Reference

```
1. SPOT the annotation problem
2. FIND the implicit graph
3. DEFINE traversal rules
4. BUILD one smart function
5. LET behavior emerge
```

---

*Framework derived from: Voice System Architecture Session, 2026-01-23*
*Principle: Local simplicity + Network topology = Emergent intelligence*
