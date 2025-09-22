# bot.py - Telegram schedule notifier (post today's routine for all batches)
# Needs: schedule.json + TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL_ID

import os, json, requests, time, re, html
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

def parse_time_for_sorting(time_str):
    """Extract start time from 'HH:MM-HH:MM' format for sorting"""
    try:
        start_time = time_str.split('-')[0].strip()
        hour, minute = map(int, start_time.split(':'))
        return hour * 60 + minute  # Convert to minutes for easy sorting
    except:
        return 999  # Put unparseable times at the end

def compose_batch_message(schedule, day_name, batch):
    """Create a pretty HTML-formatted message for a single batch"""
    day = schedule.get(day_name)
    
    # HTML escape inputs to prevent parsing issues
    safe_batch = html.escape(str(batch))
    safe_day_name = html.escape(str(day_name))
    
    if not day:
        return f"<b>📚 SOMC '63 – Batch {safe_batch}</b>\n<i>📅 {safe_day_name}</i>\n\n🎉 <b>No classes scheduled today!</b> (Holiday)"
    
    # Collect and sort time slots for this batch
    batch_slots = []
    for slot in day:
        time_str = slot.get("time", "")
        activities = slot.get("activities", [])
        applicable_activities = []
        
        for act in activities:
            batches = act.get("batches", [])
            if "All" in batches or batch in batches or set(batches) == set(BATCHES):
                applicable_activities.append(act)
        
        if applicable_activities:
            batch_slots.append((time_str, applicable_activities))
    
    if not batch_slots:
        return f"<b>📚 SOMC '63 – Batch {safe_batch}</b>\n<i>📅 {safe_day_name}</i>\n\n😴 <b>No classes scheduled for this batch today!</b>"
    
    # Sort by time
    batch_slots.sort(key=lambda x: parse_time_for_sorting(x[0]))
    
    # Build pretty HTML message with proper escaping
    lines = []
    lines.append(f"<b>📚 SOMC '63 – Batch {safe_batch}</b>")
    lines.append(f"<i>📅 {safe_day_name}</i>\n")
    
    for time_str, activities in batch_slots:
        safe_time = html.escape(str(time_str))
        lines.append(f"🕐 <code>{safe_time}</code>")
        
        for act in activities:
            # HTML escape all dynamic content
            subject = html.escape(str(act.get("subject", "Unknown")))
            activity_type = html.escape(str(act.get("type", "")))
            location = html.escape(str(act.get("location", "TBA")))
            
            # Create a clean, readable format
            type_emoji = "📖" if "Lecture" in act.get("type", "") else "🧪" if "Practical" in act.get("type", "") else "📝" if "Tutorial" in act.get("type", "") else "🔬"
            lines.append(f"   {type_emoji} <b>{subject}</b> <i>({activity_type})</i>")
            lines.append(f"   📍 {location}")
        lines.append("")  # Add spacing between time slots
    
    lines.append("✨ <b>Have a productive day!</b>")
    lines.append("<i>— Mahin, SOMC'63</i>")
    
    return "\n".join(lines)

def build_batch_messages(schedule, day_name):
    """Generate individual messages for all batches"""
    messages = []
    for batch in BATCHES:
        message = compose_batch_message(schedule, day_name, batch)
        messages.append((batch, message))
    return messages

def compose_message(schedule, day_name):
    """Legacy function for backwards compatibility - now generates preview of all batches"""
    messages = build_batch_messages(schedule, day_name)
    preview_lines = []
    preview_lines.append("📌 SOMC 63 Class Routine - PREVIEW OF ALL BATCH MESSAGES")
    preview_lines.append(f"📅 Today is {day_name}\n")
    
    for i, (batch, message) in enumerate(messages, 1):
        preview_lines.append(f"========== MESSAGE {i} (Batch {batch}) ==========")
        # Convert HTML to plain text for preview
        plain_message = message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('<code>', '').replace('</code>', '')
        preview_lines.append(plain_message)
        preview_lines.append("")
    
    return "\n".join(preview_lines)

def send_telegram_messages(messages):
    """Send multiple messages to Telegram with throttling"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("⚠️ Telegram BOT_TOKEN or CHANNEL_ID missing.")
        for i, (batch, message) in enumerate(messages, 1):
            print(f"\n------- MESSAGE {i} (Batch {batch}) START -------")
            print(message)
            print(f"------- MESSAGE {i} (Batch {batch}) END ---------")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    successful_sends = 0
    
    for i, (batch, message) in enumerate(messages):
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        try:
            print(f"📤 Sending message for Batch {batch}...")
            r = requests.post(url, json=payload)
            if r.status_code != 200:
                print(f"❌ Failed for Batch {batch}:", r.text)
            else:
                print(f"✅ Message sent for Batch {batch}")
                successful_sends += 1
                
            # Throttle between messages to avoid rate limits (1+ second for safety)
            if i < len(messages) - 1:  # Don't sleep after the last message
                time.sleep(1.2)  # 1.2 second delay for better rate limiting
                
        except Exception as e:
            print(f"❌ Error sending message for Batch {batch}:", e)
    
    print(f"\n📊 Summary: {successful_sends}/{len(messages)} messages sent successfully")

def send_telegram_message(message):
    """Legacy function for backwards compatibility"""
    # For single message, just wrap it as batch A and send
    send_telegram_messages([("Legacy", message)])

def job_send_today():
    """Send today's schedule as individual batch messages"""
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    messages = build_batch_messages(sched, today)
    send_telegram_messages(messages)

if __name__ == "__main__":
    # Preview individual batch messages
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    
    print("== Preview of Individual Batch Messages ==")
    messages = build_batch_messages(sched, today)
    
    for i, (batch, message) in enumerate(messages, 1):
        print(f"\n========== MESSAGE {i} (Batch {batch}) ==========")
        # Convert HTML to plain text for console preview
        preview = message.replace('<b>', '**').replace('</b>', '**').replace('<i>', '_').replace('</i>', '_').replace('<code>', '`').replace('</code>', '`')
        print(preview)
    
    print(f"\n== Testing Individual Batch Message Sending ==")
    print(f"Will send {len(messages)} separate messages, one for each batch...")
    send_telegram_messages(messages)

    # ✅ Auto-run at 7:00 AM every day
    # scheduler = BlockingScheduler()
    # scheduler.add_job(job_send_today, "cron", hour=7, minute=0, timezone=TIMEZONE)
    # print("Scheduler started... Will post today's routine at 07:00.")
    # scheduler.start()
