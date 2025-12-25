# Legal & Ethical Guidelines

## Overview

This system is designed for **personal job search purposes only**. It collects publicly available information from company websites to identify potential employment opportunities.

---

## Core Principles

### 1. robots.txt Compliance ✅

**Always respect robots.txt directives.**

```python
# The system checks robots.txt before every request
if not robots_checker.is_allowed(url):
    skip_url(url)  # Do not scrape
```

- Cache robots.txt for 24 hours to minimize requests
- Honor `Crawl-delay` directives when specified
- If robots.txt is unavailable (404), proceed with caution and rate limiting

### 2. Rate Limiting ✅

**Never overwhelm servers with requests.**

Default settings:
- **2-5 seconds** between requests to the same domain
- **Max 20 requests** per domain per hour
- **Exponential backoff** on errors (2x delay per consecutive error)
- **Adaptive delays** based on server response times

```python
# Rate limit configuration
min_delay_sec: 2.0
max_delay_sec: 5.0
requests_per_domain_per_hour: 20
```

### 3. Public Data Only ✅

**Only access publicly available information.**

- ❌ No login bypass or authentication circumvention
- ❌ No scraping of password-protected pages
- ❌ No accessing private APIs
- ❌ No cookie manipulation to access restricted content
- ✅ Only scrape pages accessible via normal browser navigation

### 4. User-Agent Identification ✅

**Identify the bot clearly.**

```
User-Agent: HiddenJobMarketBot/1.0 (Personal Job Search; Contact: your@email.com)
```

- Include contact information
- Be transparent about purpose
- Allow site owners to block if desired

### 5. No Spam or Mass Outreach ✅

**This is a discovery tool, not an outreach automation system.**

- ❌ No automated email sending
- ❌ No mass application submissions
- ❌ No automated LinkedIn messages
- ✅ Manual, personalized outreach only
- ✅ Use discovered contacts for research, not automation

---

## What This System Does NOT Do

| Prohibited Action | Why |
|------------------|-----|
| Scrape job boards | Violates ToS, duplicates existing services |
| Bypass login walls | Unauthorized access |
| Store personal data | Privacy concerns |
| Send automated emails | Spam, CAN-SPAM violations |
| Impersonate users | Fraud |
| Resell data | Commercial use of scraped data |
| Ignore rate limits | Server abuse |
| Scrape after robots.txt denial | Trespass |

---

## Legal Considerations by Jurisdiction

### United States

**Computer Fraud and Abuse Act (CFAA)**
- Scraping public data is generally legal (hiQ Labs v. LinkedIn, 2022)
- Violating ToS alone may not constitute "unauthorized access"
- However, circumventing technical barriers can be problematic

**Best Practices:**
- Only access public pages
- Respect robots.txt
- Don't circumvent access controls
- Don't cause server disruption

### European Union

**GDPR Considerations**
- Personal data (names, emails) requires legal basis
- Public business contact info generally has legitimate interest basis
- Don't store unnecessary personal data
- Provide deletion mechanism if requested

**Best Practices:**
- Minimize personal data collection
- Only store business contact emails (careers@, jobs@)
- Don't build profiles on individuals
- Delete data when no longer needed

### General

- Check local laws before use
- When in doubt, err on the side of caution
- This tool is for personal use only

---

## Ethical Guidelines

### Do

✅ Use for personal job search only
✅ Respect website owners' wishes
✅ Rate limit all requests
✅ Identify your bot clearly
✅ Delete data you no longer need
✅ Report security issues you discover
✅ Be transparent about your methods

### Don't

❌ Resell or share scraped data
❌ Use for competitive intelligence
❌ Scrape sites that explicitly prohibit it
❌ Store data longer than necessary
❌ Ignore cease-and-desist requests
❌ Cause any disruption to services
❌ Use for any commercial purpose

---

## Handling Blocks & Complaints

### If You Get Blocked

1. **Stop immediately** - Don't try to circumvent
2. **Review your behavior** - Were you too aggressive?
3. **Add to blocklist** - Don't attempt again
4. **Adjust rate limits** - Be more conservative

### If You Receive a Complaint

1. **Stop scraping that domain immediately**
2. **Delete any stored data from that domain**
3. **Add to permanent blocklist**
4. **Respond politely and professionally**
5. **Document the interaction**

### Sample Response Template

```
Subject: Re: Web Scraping Inquiry

Hello,

Thank you for reaching out. I have immediately:
1. Stopped all automated access to your website
2. Deleted any data collected from your domain
3. Added your domain to my permanent blocklist

I apologize for any inconvenience. This was a personal job search tool,
and I did not intend to cause any issues.

Please let me know if you need any additional information.

Best regards,
[Your Name]
```

---

## Configuration Checklist

Before running the system, ensure:

- [ ] robots.txt checking is **enabled** (`respect_robots: true`)
- [ ] Rate limiting is **enabled** (`rate_limit: true`)
- [ ] User-agent includes your **contact information**
- [ ] Blocklist includes all **job boards and prohibited sites**
- [ ] Max pages per domain is **reasonable** (≤10)
- [ ] Delay between requests is **adequate** (≥2 seconds)

---

## Disclaimer

This software is provided for educational and personal use only. The authors are not responsible for any misuse or legal consequences arising from the use of this software. Users are responsible for ensuring their use complies with all applicable laws and website terms of service.

**When in doubt, don't scrape.**
