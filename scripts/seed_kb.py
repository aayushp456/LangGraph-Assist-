#!/usr/bin/env python3
"""
Seed the Knowledge Base with sample articles covering all 7 categories.
Usage: python scripts/seed_kb.py
"""

import requests
import sys
import time

API_URL = "http://localhost:8000"

ARTICLES = [
    # ---- BUG ----
    {
        "title": "Fix: Application crashes on file upload exceeding 50MB",
        "content": (
            "Issue: The application crashes with an OutOfMemoryError when users attempt to upload files larger than 50MB.\n\n"
            "Root Cause: The file upload handler loads the entire file into memory before processing. "
            "For large files, this exceeds the default JVM heap allocation.\n\n"
            "Resolution Steps:\n"
            "1. Update the file upload configuration to use streaming/chunked uploads.\n"
            "2. Set the max upload size in application.yml: spring.servlet.multipart.max-file-size=100MB\n"
            "3. Increase JVM heap if needed: -Xmx512m\n"
            "4. Implement client-side file size validation to show a user-friendly error before upload.\n"
            "5. Add a progress bar for large uploads.\n\n"
            "Verification: Upload a 75MB file and confirm it completes without error."
        ),
        "category": "BUG",
        "product": "Platform",
        "tags": ["file-upload", "crash", "memory"],
    },
    {
        "title": "Fix: Null pointer exception in user profile update",
        "content": (
            "Issue: Users encounter a 500 error when updating their profile if the 'phone' field is left blank.\n\n"
            "Root Cause: The profile update handler does not null-check optional fields before calling .trim().\n\n"
            "Resolution Steps:\n"
            "1. Add null checks for all optional fields in UserProfileService.updateProfile().\n"
            "2. Use Optional.ofNullable() pattern for nullable string fields.\n"
            "3. Add unit tests for profile updates with missing optional fields.\n"
            "4. Deploy fix and verify via: PUT /api/users/profile with phone=null.\n\n"
            "Prevention: Add @Valid annotations and use a DTO with proper Optional<String> types."
        ),
        "category": "BUG",
        "product": "Platform",
        "tags": ["null-pointer", "profile", "500-error"],
    },

    # ---- PERFORMANCE ----
    {
        "title": "Resolving slow dashboard load times (>10s)",
        "content": (
            "Issue: The main dashboard takes over 10 seconds to load for customers with large datasets (>10k records).\n\n"
            "Root Cause: The dashboard API endpoint fetches all records in a single query without pagination. "
            "The frontend then renders all rows at once, causing browser lag.\n\n"
            "Resolution Steps:\n"
            "1. Implement server-side pagination: GET /api/dashboard?page=1&limit=50\n"
            "2. Add database indexes on frequently queried columns: created_at, status, category.\n"
            "3. Use virtual scrolling on the frontend (react-virtualized or @tanstack/virtual).\n"
            "4. Cache aggregated stats in Redis with a 60s TTL.\n"
            "5. Add a loading skeleton to improve perceived performance.\n\n"
            "Expected Result: Dashboard loads in under 2 seconds for any dataset size."
        ),
        "category": "PERFORMANCE",
        "product": "Platform",
        "tags": ["dashboard", "slow-load", "pagination", "optimization"],
    },
    {
        "title": "Database query optimization for reporting module",
        "content": (
            "Issue: Monthly report generation takes 45+ minutes for enterprise accounts.\n\n"
            "Root Cause: The reporting queries use multiple JOINs across unindexed tables and run full table scans.\n\n"
            "Resolution Steps:\n"
            "1. Add composite indexes: CREATE INDEX idx_reports_date_status ON reports(created_at, status).\n"
            "2. Use materialized views for commonly aggregated data.\n"
            "3. Implement query result caching with 15-minute invalidation.\n"
            "4. Move heavy reports to async background jobs with progress tracking.\n"
            "5. Consider read replicas for report queries to reduce primary DB load.\n\n"
            "Verification: Run EXPLAIN ANALYZE on report queries to confirm index usage."
        ),
        "category": "PERFORMANCE",
        "product": "Platform",
        "tags": ["database", "reporting", "query-optimization"],
    },

    # ---- API_ISSUE ----
    {
        "title": "Troubleshooting 401 Unauthorized errors on API endpoints",
        "content": (
            "Issue: API requests return 401 Unauthorized even with valid credentials.\n\n"
            "Common Causes:\n"
            "1. Expired JWT token — tokens expire after 1 hour by default.\n"
            "2. Missing 'Bearer ' prefix in Authorization header.\n"
            "3. API key was regenerated but client still uses the old key.\n"
            "4. Clock skew between client and server exceeding JWT tolerance (5 minutes).\n\n"
            "Resolution Steps:\n"
            "1. Verify token format: Authorization: Bearer <token>\n"
            "2. Check token expiration: decode the JWT and verify 'exp' claim.\n"
            "3. Regenerate API key from Settings > API Keys and update client.\n"
            "4. Sync system clock: sudo ntpdate pool.ntp.org\n"
            "5. Test with curl: curl -H 'Authorization: Bearer YOUR_TOKEN' https://api.example.com/v1/me\n\n"
            "If issue persists, check server logs for detailed auth rejection reasons."
        ),
        "category": "API_ISSUE",
        "product": "API",
        "tags": ["401", "authentication", "jwt", "api-key"],
    },
    {
        "title": "Handling 429 Rate Limit errors",
        "content": (
            "Issue: API returns 429 Too Many Requests during peak usage.\n\n"
            "Rate Limits:\n"
            "- Free tier: 100 requests/minute\n"
            "- Pro tier: 1000 requests/minute\n"
            "- Enterprise tier: 10000 requests/minute\n\n"
            "Resolution Steps:\n"
            "1. Check current usage: GET /api/v1/rate-limit-status\n"
            "2. Implement exponential backoff with jitter in your client.\n"
            "3. Batch multiple operations into single requests where supported.\n"
            "4. Use webhooks instead of polling for real-time updates.\n"
            "5. Upgrade your plan if consistently hitting limits.\n\n"
            "Example backoff (Python):\n"
            "  import time, random\n"
            "  for attempt in range(5):\n"
            "      response = requests.get(url)\n"
            "      if response.status_code != 429: break\n"
            "      wait = (2 ** attempt) + random.uniform(0, 1)\n"
            "      time.sleep(wait)"
        ),
        "category": "API_ISSUE",
        "product": "API",
        "tags": ["429", "rate-limit", "throttling"],
    },

    # ---- SECURITY ----
    {
        "title": "Responding to suspicious login activity alerts",
        "content": (
            "Issue: Customer receives 'Suspicious login detected' email alerts.\n\n"
            "What triggers this alert:\n"
            "- Login from a new geographic location\n"
            "- Multiple failed login attempts (>5 in 10 minutes)\n"
            "- Login from a known compromised IP address\n"
            "- Simultaneous sessions from different countries\n\n"
            "Resolution Steps:\n"
            "1. Verify the alert is legitimate by checking the IP and location in account activity.\n"
            "2. If unauthorized: immediately change password and enable 2FA.\n"
            "3. Revoke all active sessions: Settings > Security > Active Sessions > Revoke All.\n"
            "4. Review API keys and regenerate any that may be compromised.\n"
            "5. Check for unauthorized data exports in the audit log.\n"
            "6. Enable login notifications for future monitoring.\n\n"
            "Escalation: If data breach is confirmed, escalate to Security team immediately (SEV1)."
        ),
        "category": "SECURITY",
        "product": "Platform",
        "tags": ["suspicious-login", "2fa", "breach", "account-security"],
    },

    # ---- INFRASTRUCTURE ----
    {
        "title": "Troubleshooting deployment failures on Kubernetes",
        "content": (
            "Issue: Application deployment fails with 'CrashLoopBackOff' or 'ImagePullBackOff' in Kubernetes.\n\n"
            "Diagnosis Steps:\n"
            "1. Check pod status: kubectl get pods -n production\n"
            "2. View pod logs: kubectl logs <pod-name> -n production --previous\n"
            "3. Describe pod for events: kubectl describe pod <pod-name> -n production\n\n"
            "Common Causes & Fixes:\n"
            "- ImagePullBackOff: Verify image tag exists in registry. Check imagePullSecrets.\n"
            "- CrashLoopBackOff: Application crashes on startup. Check environment variables and config maps.\n"
            "- OOMKilled: Container exceeds memory limit. Increase resources.limits.memory.\n"
            "- Readiness probe failing: Health endpoint not responding. Check /healthz endpoint and startup time.\n\n"
            "Quick Fix Checklist:\n"
            "1. Verify Docker image builds locally: docker build -t app:latest .\n"
            "2. Confirm environment variables are set: kubectl get configmap -n production\n"
            "3. Check resource limits aren't too restrictive.\n"
            "4. Verify secrets exist: kubectl get secrets -n production"
        ),
        "category": "INFRASTRUCTURE",
        "product": "DevOps",
        "tags": ["kubernetes", "deployment", "crashloop", "docker"],
    },
    {
        "title": "Database connection pool exhaustion",
        "content": (
            "Issue: Application throws 'Connection pool exhausted' errors during high traffic.\n\n"
            "Root Cause: All database connections in the pool are in use and new requests cannot acquire a connection.\n\n"
            "Resolution Steps:\n"
            "1. Check current pool usage: SELECT count(*) FROM pg_stat_activity WHERE state = 'active';\n"
            "2. Increase pool size in config: DATABASE_POOL_SIZE=20 (default is 10).\n"
            "3. Set max overflow: DATABASE_MAX_OVERFLOW=10\n"
            "4. Add connection timeout: DATABASE_POOL_TIMEOUT=30\n"
            "5. Identify and fix long-running queries: SELECT pid, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;\n"
            "6. Consider PgBouncer for connection pooling at the infrastructure level.\n\n"
            "Prevention: Monitor pool usage with metrics and set alerts at 80% utilization."
        ),
        "category": "INFRASTRUCTURE",
        "product": "Platform",
        "tags": ["database", "connection-pool", "high-traffic"],
    },

    # ---- FEATURE_REQUEST ----
    {
        "title": "Feature: Dark mode support for web dashboard",
        "content": (
            "Feature Request: Add dark mode theme option to the web dashboard.\n\n"
            "Current Status: Under consideration for Q3 roadmap.\n\n"
            "Workaround: Users can use browser extensions like 'Dark Reader' to approximate dark mode.\n\n"
            "Implementation Notes (internal):\n"
            "- Use CSS custom properties (--bg-primary, --text-primary) for theme switching.\n"
            "- Store preference in user settings (persisted to backend).\n"
            "- Respect OS-level prefers-color-scheme media query as default.\n"
            "- Ensure WCAG AA contrast ratios in both themes.\n\n"
            "Response Template: Thank you for your feedback! Dark mode is on our roadmap. "
            "In the meantime, you can use the 'Dark Reader' browser extension for a similar experience."
        ),
        "category": "FEATURE_REQUEST",
        "product": "Platform",
        "tags": ["dark-mode", "ui", "theme"],
    },

    # ---- GENERAL_INQUIRY ----
    {
        "title": "How to export data from the platform",
        "content": (
            "Question: How do I export my data from the platform?\n\n"
            "Available Export Options:\n"
            "1. CSV Export: Go to any list view > click 'Export' button > select CSV.\n"
            "2. API Bulk Export: GET /api/v1/export?format=json&start_date=2024-01-01\n"
            "3. Scheduled Reports: Settings > Reports > New Schedule > choose frequency and format.\n"
            "4. Full Account Export: Settings > Account > Data Export > Request Full Export (takes 24-48 hours).\n\n"
            "Supported Formats: CSV, JSON, Excel (.xlsx), PDF (reports only)\n\n"
            "Rate Limits for API export:\n"
            "- Max 10,000 records per request\n"
            "- Use pagination for larger datasets: ?page=1&per_page=10000\n\n"
            "Data Retention: Exported files are available for download for 7 days after generation."
        ),
        "category": "GENERAL_INQUIRY",
        "product": "Platform",
        "tags": ["export", "data", "csv", "api"],
    },
    {
        "title": "Getting started with the API: Authentication and first request",
        "content": (
            "Guide: How to authenticate and make your first API request.\n\n"
            "Step 1: Generate an API Key\n"
            "- Navigate to Settings > API Keys > Generate New Key\n"
            "- Copy the key immediately (it won't be shown again)\n\n"
            "Step 2: Make your first request\n"
            "  curl -H 'Authorization: Bearer YOUR_API_KEY' \\\n"
            "       -H 'Content-Type: application/json' \\\n"
            "       https://api.example.com/v1/me\n\n"
            "Step 3: Explore endpoints\n"
            "- GET /v1/me — Your account info\n"
            "- GET /v1/tickets — List tickets\n"
            "- POST /v1/tickets — Create ticket\n"
            "- GET /v1/reports — List reports\n\n"
            "SDKs Available: Python (pip install our-sdk), Node.js (npm install our-sdk), Go\n\n"
            "Need help? Check the full API reference at https://docs.example.com/api"
        ),
        "category": "GENERAL_INQUIRY",
        "product": "API",
        "tags": ["getting-started", "authentication", "api-key"],
    },
]


def seed_kb():
    print(f"Seeding {len(ARTICLES)} KB articles to {API_URL}...\n")

    success = 0
    failed = 0

    for i, article in enumerate(ARTICLES, 1):
        try:
            resp = requests.post(f"{API_URL}/api/kb/index", json=article, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [{i}/{len(ARTICLES)}] ✓ {article['title'][:60]}... → {data.get('article_id', 'ok')}")
                success += 1
            else:
                print(f"  [{i}/{len(ARTICLES)}] ✗ {article['title'][:60]}... → {resp.status_code}: {resp.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"  [{i}/{len(ARTICLES)}] ✗ {article['title'][:60]}... → Error: {e}")
            failed += 1

        time.sleep(0.5)  # Small delay between requests

    print(f"\nDone! {success} succeeded, {failed} failed out of {len(ARTICLES)} articles.")


if __name__ == "__main__":
    seed_kb()
