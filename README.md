# Daily News Email Agent (Free)

This project sends you a daily email of curated news based on region and sector (topics), running on a free GitHub Actions schedule.

Highlights:
- Free: uses RSS (e.g., Google News) + GitHub Actions on a public repo
- Filter by regions (FR, US, etc.) and sectors/topics
- Include/exclude keywords
- Clean HTML email via SMTP (Gmail or another SMTP)

## How it works

1. We build RSS search feeds using Google News for each sector/topic and region.
2. We fetch entries from the last day, apply keyword filters, deduplicate, and sort.
3. We render an HTML email and send it via SMTP.

No scraping of websites; we only consume RSS feeds.

## Setup

1) Fork this repo (public to get free GitHub Actions minutes).

2) Edit `config.yaml`
   - Choose your regions (e.g., FR, US)
   - Customize sectors and queries
   - Adjust subject, grouping, and limits

3) Add GitHub Secrets (Repository Settings → Secrets and variables → Actions → New repository secret):
   - `SMTP_SERVER` (e.g., `smtp.gmail.com`)
   - `SMTP_PORT` (e.g., `465`)
   - `SMTP_USER` (your SMTP username; for Gmail this is your full email)
   - `SMTP_PASS` (SMTP/App Password; see below for Gmail)
   - `FROM_EMAIL` (usually same as `SMTP_USER`)
   - `TO_EMAIL` (where you want to receive the digest)

4) Schedule
   - The workflow is set to run daily at 07:00 UTC. Change the cron in `.github/workflows/daily-news.yml` as needed.

5) Test
   - Run the workflow manually via the “Actions” tab (Workflow Dispatch).

## Gmail SMTP (App Password)

If you use Gmail:
- Enable 2FA on your Google account.
- Create an App Password (Google Account → Security → App passwords).
- Use the generated 16‑character password as `SMTP_PASS`.

Alternatively, you can use a free-tier SMTP provider (e.g., Mailjet free, Sendinblue/Brevo, etc.). Check their current free limits and SMTP settings.

## Customizing sources

- By default this uses Google News RSS search:
  - Example URL: `https://news.google.com/rss/search?q=AI+startups+when:1d&hl=en-US&gl=US&ceid=US:en`
  - Change queries in `config.yaml` to match your interests.

- You can also add direct RSS feeds by sector:
  - Add your favorite RSS URLs into a new list in `config.yaml` (you’d need minor code changes to mix in raw RSS URLs per sector).

## Run locally (optional)

You can run locally with a cron:

```bash
pip install -r requirements.txt
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="465"
export SMTP_USER="you@gmail.com"
export SMTP_PASS="your_app_password"
export FROM_EMAIL="you@gmail.com"
export TO_EMAIL="you@gmail.com"
python src/news_agent.py
```

Crontab example (runs every day at 7:00):

```
0 7 * * * cd /path/to/repo && /usr/bin/python3 src/news_agent.py >> /tmp/news_agent.log 2>&1
```

## Notes and tips

- Keep your repo public to leverage free GitHub Actions minutes.
- Respect RSS/API providers’ terms of service.
- You can tweak `days_window` (default 1) to widen the time window.
- Use `keywords_include` and `keywords_exclude` to tighten the feed.
- Set `group_by` to `region` or `none` if you prefer a different layout.

## Troubleshooting

- If emails don’t arrive, check the Action logs and your spam folder.
- Verify SMTP credentials and ports.
- Some corporate email filters block external SMTP—try a different provider.

PRs welcome!