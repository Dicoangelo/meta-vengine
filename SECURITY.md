# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Meta-Vengine, please report it responsibly.

**Contact:** [dicoangel@metaventionsai.com](mailto:dicoangel@metaventionsai.com)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial Assessment:** Within 7 days
- **Resolution:** Dependent on severity

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | ✅ Yes    |
| < 1.0   | ❌ No     |

## Security Design

Meta-Vengine is designed with security in mind:

### Data Privacy
- All data stored locally in `~/.claude/`
- No external API calls for telemetry
- Your patterns stay on your machine

### Self-Modification Bounds
- Recursion capped at 2 levels
- Human approval required for modifications
- All changes logged to git history
- Full rollback capability

### API Keys
- Never committed to repository
- Stored in environment variables
- `.gitignore` excludes sensitive files

## Responsible Disclosure

We appreciate responsible disclosure and will:
- Credit reporters (unless anonymity requested)
- Not pursue legal action for good-faith reports
- Work with you to understand and resolve issues

---

**Metaventions AI** — Architected Intelligence

Part of the [D-Ecosystem](https://github.com/Dicoangelo/The-Decosystem)
