# bot.py - Telegram schedule notifier (post today's routine for all batches)
# Needs: schedule.json + TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL_ID

import os, json, requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from apscheduler.schedulers.blocking import BlockingScheduler

SCHEDULE_FILE = os.environ.get("SCHEDULE_FILE", "schedule.json")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Dhaka")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

BATCHES = ["A", "B", "C", "D", "E"]

def load_schedule(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_today_name(tz_name=TIMEZONE):
    if ZoneInfo:
        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()
    else:
        now = datetime.now()
    return now.strftime("%A")

def compose_message(schedule, day_name):
    out_lines = []
    out_lines.append("📌 *SOMC 63 Class Routine*")
    out_lines.append(f"📅 Today is *{day_name}*\n")

    day = schedule.get(day_name)
    if not day:
        out_lines.append("No classes scheduled today. (Holiday)")
        return "\n".join(out_lines)

    # Loop over batches
    for batch in BATCHES:
        out_lines.append(f"👥 *Batch {batch}:*")
        batch_has_class = False

        for slot in day:
            time = slot.get("time", "")
            activities = slot.get("activities", [])
            appl = []
            for act in activities:
                batches = act.get("batches", [])
                if "All" in batches or batch in batches or set(batches) == set(BATCHES):
                    appl.append(act)

            if not appl:
                continue
            batch_has_class = True
            out_lines.append(f"🕘 {time}:")
            for act in appl:
                subj = act.get("subject")
                typ = act.get("type", "")
                loc = act.get("location", "TBA")
                bs = ", ".join(act.get("batches", []))
                out_lines.append(f"   • {subj} ({typ}) — 📍 {loc} — 🎯 {bs}")
            out_lines.append("")

        if not batch_has_class:
            out_lines.append("   • No classes today for this batch.\n")

    out_lines.append("✅ Have a productive day!\n— Mahin, SOMC'63")
    return "\n".join(out_lines)

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("⚠️ Telegram BOT_TOKEN or CHANNEL_ID missing.")
        print("------- MESSAGE START -------")
        print(message)
        print("------- MESSAGE END ---------")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code != 200:
            print("❌ Failed:", r.text)
        else:
            print("✅ Message sent to Telegram channel.")
    except Exception as e:
        print("❌ Error sending message:", e)

def job_send_today():
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    msg = compose_message(sched, today)
    send_telegram_message(msg)

if name == "main":
    # Preview in console
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    print("== Sample message preview ==")
    print(compose_message(sched, today))

    # ✅ Auto-run at 7:00 AM every day
    # scheduler = BlockingScheduler()
    # scheduler.add_job(job_send_today, "cron", hour=7, minute=0, timezone=TIMEZONE)
    # print("Scheduler started... Will post today's routine at 07:00.")
    # scheduler.start()
