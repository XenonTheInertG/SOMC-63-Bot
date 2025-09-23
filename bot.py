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

def parse_time_to_minutes(time_str):
    """Convert HH:MM time to minutes since midnight"""
    try:
        hour, minute = map(int, time_str.split(':'))
        return hour * 60 + minute
    except:
        return None

def get_upcoming_classes(schedule, day_name, notify_minutes_before=15):
    """Get classes that start within the notification window"""
    if ZoneInfo:
        try:
            tz = ZoneInfo(TIMEZONE)
            now = datetime.now(tz)
        except:
            now = datetime.now()
    else:
        now = datetime.now()
    
    current_minutes = now.hour * 60 + now.minute
    day = schedule.get(day_name)
    
    if not day:
        return []
    
    upcoming_classes = []
    
    for slot in day:
        time_range = slot.get("time", "")
        if "-" not in time_range:
            continue
            
        start_time = time_range.split('-')[0].strip()
        start_minutes = parse_time_to_minutes(start_time)
        
        if start_minutes is None:
            continue
            
        # Check if class starts within the notification window
        time_until_class = start_minutes - current_minutes
        
        if 0 <= time_until_class <= notify_minutes_before:
            for activity in slot.get("activities", []):
                batches = activity.get("batches", [])
                upcoming_classes.append({
                    "time": time_range,
                    "start_time": start_time,
                    "subject": activity.get("subject", "Unknown"),
                    "type": activity.get("type", ""),
                    "location": activity.get("location", "TBA"),
                    "batches": batches,
                    "minutes_until": time_until_class
                })
    
    return upcoming_classes

def compose_preclass_message(class_info):
    """Create a pre-class notification message"""
    subject = html.escape(str(class_info["subject"]))
    activity_type = html.escape(str(class_info["type"]))
    location = html.escape(str(class_info["location"]))
    start_time = html.escape(str(class_info["start_time"]))
    minutes_until = class_info["minutes_until"]
    
    # Get appropriate emoji
    type_emoji = "📖" if "Lecture" in class_info["type"] else "🧪" if "Practical" in class_info["type"] else "📝" if "Tutorial" in class_info["type"] else "🔬"
    
    # Create urgency indicator
    if minutes_until <= 5:
        urgency = "🔴 <b>STARTING SOON!</b>"
    elif minutes_until <= 10:
        urgency = "🟡 <b>Starting in a few minutes</b>"
    else:
        urgency = "🔔 <b>Upcoming class</b>"
    
    # Build message
    lines = []
    lines.append(f"{urgency}")
    lines.append(f"{type_emoji} <b>{subject}</b> <i>({activity_type})</i>")
    lines.append(f"🕐 Starts at <code>{start_time}</code>")
    lines.append(f"📍 Location: <b>{location}</b>")
    
    if minutes_until <= 1:
        lines.append(f"\n⏰ <b>Starting NOW!</b> \n")
    else:
        lines.append(f"\n⏰ <i>Starts in {minutes_until} minute{'s' if minutes_until != 1 else ''}</i>\n")
    
    lines.append("🏃‍♂️ <i>Get ready and head to class!</i>")
    lines.append("<i>— SOMC'63 Bot</i>")
    
    return "\n".join(lines)

def send_preclass_notifications():
    """Check for upcoming classes and send notifications"""
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    upcoming = get_upcoming_classes(sched, today)
    
    if not upcoming:
        print("🔕 No upcoming classes in the next 15 minutes")
        return
    
    # Group by batches to avoid duplicate notifications
    notifications_sent = 0
    
    for class_info in upcoming:
        batches = class_info["batches"]
        message = compose_preclass_message(class_info)
        
        # Determine which batches to notify
        batch_list = []
        if "All" in batches or set(batches) == set(BATCHES):
            batch_list = ["All Batches"]
        else:
            batch_list = batches
        
        print(f"📢 Sending pre-class notification for {class_info['subject']} to batches: {', '.join(batch_list)}")
        
        # Send as single message (not individual batch messages for pre-class alerts)
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
            print("\n------- PRE-CLASS NOTIFICATION -------")
            print(f"Target batches: {', '.join(batch_list)}")
            print(message)
            print("------- END NOTIFICATION -------\n")
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            
            # Add batch info to message header
            if len(batch_list) == 1 and batch_list[0] == "All Batches":
                final_message = f"🎆 <b>All Batches (A, B, C, D, E)</b>\n\n{message}"
            else:
                final_message = f"🎆 <b>Batch{'es' if len(batch_list) > 1 else ''} {', '.join(batch_list)}</b>\n\n{message}"
            
            payload = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": final_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            try:
                r = requests.post(url, json=payload)
                if r.status_code == 200:
                    print("✅ Pre-class notification sent successfully")
                    notifications_sent += 1
                else:
                    print(f"❌ Failed to send pre-class notification: {r.text}")
            except Exception as e:
                print(f"❌ Error sending pre-class notification: {e}")
    
    if notifications_sent > 0:
        print(f"📊 Sent {notifications_sent} pre-class notification{'s' if notifications_sent != 1 else ''}")

def job_send_today():
    """Send today's schedule as individual batch messages (7 AM daily routine)"""
    print("🌅 Sending daily routine messages...")
    today = get_today_name()
    sched = load_schedule(SCHEDULE_FILE)
    messages = build_batch_messages(sched, today)
    send_telegram_messages(messages)
    print("✅ Daily routine messages completed")

def job_check_preclass():
    """Check for pre-class notifications (runs every few minutes)"""
    send_preclass_notifications()

if __name__ == "__main__":
    import sys
    
    # Check if we should run in test mode or scheduler mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode: Preview messages only
        print("=== TEST MODE: Preview of Individual Batch Messages ===")
        today = get_today_name()
        sched = load_schedule(SCHEDULE_FILE)
        messages = build_batch_messages(sched, today)
        
        for i, (batch, message) in enumerate(messages, 1):
            print(f"\n========== MESSAGE {i} (Batch {batch}) ==========")
            preview = message.replace('<b>', '**').replace('</b>', '**').replace('<i>', '_').replace('</i>', '_').replace('<code>', '`').replace('</code>', '`')
            print(preview)
        
        print(f"\n=== Testing Pre-class Notification System ===")
        send_preclass_notifications()
        
        print("\n=== Test completed ===")
        
    elif len(sys.argv) > 1 and sys.argv[1] == "--send-daily":
        # Manual daily routine send
        print("=== Sending Daily Routine Manually ===")
        job_send_today()
        
    elif len(sys.argv) > 1 and sys.argv[1] == "--check-preclass":
        # Manual pre-class check
        print("=== Checking for Pre-class Notifications ===")
        send_preclass_notifications()
        
    else:
        # Production mode: Start scheduler
        print("🤖 SOMC 63 Telegram Bot Starting...")
        print(f"📅 Current time: {datetime.now()}")
        print(f"🌏 Timezone: {TIMEZONE}")
        
        try:
            scheduler = BlockingScheduler(timezone=TIMEZONE)
            
            # Daily routine at 7:00 AM
            scheduler.add_job(
                job_send_today, 
                "cron", 
                hour=7, 
                minute=0, 
                timezone=TIMEZONE,
                id="daily_routine"
            )
            print("📅 Scheduled daily routine messages at 07:00 AM")
            
            # Check for pre-class notifications every 5 minutes
            scheduler.add_job(
                job_check_preclass, 
                "interval", 
                minutes=5,
                timezone=TIMEZONE,
                id="preclass_check"
            )
            print("🔔 Scheduled pre-class notifications (every 5 minutes)")
            
            # Show scheduled jobs
            print("\\n📋 Scheduled Jobs:")
            for job in scheduler.get_jobs():
                print(f"  • {job.id}: {job.trigger}")
            
            print("\\n🚀 Bot is now running... Press Ctrl+C to stop")
            print("Will send:")
            print("  • Daily routines at 7:00 AM (individual messages per batch)")
            print("  • Pre-class notifications 15 minutes before each class starts")
            print("-" * 50)
            
            scheduler.start()
            
        except KeyboardInterrupt:
            print("\\n⏹️  Bot stopped by user")
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
            raise
