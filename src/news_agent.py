import os
import sys
import time
import smtplib
import feedparser
import yaml
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader

# -------------------------
# Helpers
# -------------------------

def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def env_or_config(config, key, default=None):
    # Prefer env var; fall back to config; otherwise default
    return os.getenv(key) or config.get("email", {}).get(key.lower()) or default

def iso_region_to_params(region_code):
    # Maps a handful of common regions to Google News params
    # hl = language, gl = country, ceid = country:language
    # Extend this as you wish.
    mapping = {
        "US": ("en-US", "US", "US:en"),
        "GB": ("en-GB", "GB", "GB:en"),
        "CA": ("en-CA", "CA", "CA:en"),
        "AU": ("en-AU", "AU", "AU:en"),
        "IN": ("en-IN", "IN", "IN:en"),
        "FR": ("fr",    "FR", "FR:fr"),
        "DE": ("de",    "DE", "DE:de"),
        "ES": ("es",    "ES", "ES:es"),
        "IT": ("it",    "IT", "IT:it"),
        "BR": ("pt-BR", "BR", "BR:pt"),
    }
    # Default to US English if unknown
    return mapping.get(region_code.upper(), ("en-US", "US", "US:en"))

def google_news_search_feed(query, region_code="US"):
    # Example:
    # https://news.google.com/rss/search?q=artificial%20intelligence%20when:1d&hl=en-US&gl=US&ceid=US:en
    hl, gl, ceid = iso_region_to_params(region_code)
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}+when:1d&hl={hl}&gl={gl}&ceid={ceid}"

def uniq(seq, key=lambda x: x):
    seen = set()
    res = []
    for item in seq:
        k = key(item)
        if k not in seen:
            seen.add(k)
            res.append(item)
    return res

def within_last_days(published_parsed, days=1):
    if not published_parsed:
        return True  # keep if unknown
    published_dt = datetime.fromtimestamp(time.mktime(published_parsed), tz=timezone.utc)
    return published_dt >= (datetime.now(timezone.utc) - timedelta(days=days))

def matches_keywords(text, includes, excludes):
    t = (text or "").lower()
    if includes:
        if not any(k.lower() in t for k in includes):
            return False
    if excludes:
        if any(k.lower() in t for k in excludes):
            return False
    return True

def render_email(template_dir, context):
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("email.html")
    html = template.render(**context)
    # simple plaintext fallback
    text = "Your daily news digest is best viewed in HTML email."
    return text, html

def send_email(smtp_server, smtp_port, smtp_user, smtp_pass, from_email, to_email, subject, text_body, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    part1 = MIMEText(text_body, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())

# -------------------------
# Main logic
# -------------------------

def main():
    cfg_path = os.getenv("CONFIG_PATH", "config.yaml")
    config = load_config(cfg_path)

    regions = config.get("regions", ["US"])
    sectors = config.get("sectors", [])
    includes = config.get("keywords_include", [])
    excludes = config.get("keywords_exclude", [])
    max_items = int(config.get("max_items", 40))
    days_window = int(config.get("days_window", 1))

    # Email settings: read from env first
    smtp_server = env_or_config(config, "SMTP_SERVER", "smtp.gmail.com")
    smtp_port = env_or_config(config, "SMTP_PORT", "465")
    smtp_user = env_or_config(config, "SMTP_USER")
    smtp_pass = env_or_config(config, "SMTP_PASS")
    to_email   = env_or_config(config, "TO_EMAIL")
    from_email = env_or_config(config, "FROM_EMAIL", smtp_user or "no-reply@example.com")
    subject = config.get("subject", "Your Daily News Digest")

    if not all([smtp_user, smtp_pass, to_email, from_email]):
        print("Missing SMTP credentials or email addresses. Please set SMTP_USER, SMTP_PASS, FROM_EMAIL, TO_EMAIL.", file=sys.stderr)
        sys.exit(1)

    # Build feeds for each region/sector combination
    feeds = []
    if not sectors:
        # If no sectors, use general query from config or default to "top stories"
        base_queries = config.get("queries", ["technology", "business"])
        for r in regions:
            for q in base_queries:
                feeds.append(("General", r, google_news_search_feed(q, r)))
    else:
        for sector in sectors:
            sector_name = sector.get("name", "Sector")
            queries = sector.get("queries", [])
            for r in regions:
                for q in queries:
                    feeds.append((sector_name, r, google_news_search_feed(q, r)))

    items = []
    for sector_name, region_code, url in feeds:
        parsed = feedparser.parse(url)
        for e in parsed.entries:
            # Filter by date
            if not within_last_days(getattr(e, "published_parsed", None), days_window):
                continue

            title = getattr(e, "title", "")
            summary = getattr(e, "summary", "")
            link = getattr(e, "link", "")
            source = getattr(e, "source", {}).get("title") if hasattr(e, "source") else None

            blob = f"{title}\n{summary}\n{link}\n{source or ''}"
            if not matches_keywords(blob, includes, excludes):
                continue

            items.append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "sector": sector_name,
                "region": region_code,
                "published": getattr(e, "published", None),
                "published_parsed": getattr(e, "published_parsed", None),
            })

    # Deduplicate by link/title
    items = uniq(items, key=lambda x: x["link"] or x["title"])

    # Sort by published desc
    def sort_key(x):
        pp = x.get("published_parsed")
        if pp:
            return time.mktime(pp)
        return 0
    items.sort(key=sort_key, reverse=True)

    # Cap list
    items = items[:max_items]

    # Render
    template_dir = os.getenv("TEMPLATE_DIR", "templates")
    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": items,
        "group_by": config.get("group_by", "sector"),  # "sector" or "region" or "none"
        "title": subject,
    }
    text_body, html_body = render_email(template_dir, context)

    # Send
    send_email(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

if __name__ == "__main__":
    main()