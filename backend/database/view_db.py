import sqlite3
import os

DB_PATH = "meeting_assistant.db"

def view_database():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file '{DB_PATH}' nahi mili! Pehle server chala kar data save karo.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n" + "="*50)
        print(" 📅 MEETINGS TABLE ")
        print("="*50)
        cursor.execute("SELECT id, title, start_time FROM meetings")
        meetings = cursor.fetchall()
        if not meetings:
            print("Abhi koi meeting nahi hai.")
        for row in meetings:
            print(f"ID: {row[0]} | Title: {row[1]} | Started At: {row[2]}")


        print("\n" + "="*50)
        print(" 🗣️ TRANSCRIPTS & OCR DATA ")
        print("="*50)
        cursor.execute("SELECT id, source, text, keywords, timestamp FROM transcripts")
        transcripts = cursor.fetchall()
        if not transcripts:
            print("Abhi koi transcript nahi hai.")
        for row in transcripts:
            source = row[1]
            text = row[2]
            keywords = row[3]
        
            display_text = text if len(text) < 60 else text[:57] + "..."
            
            icon = "🖥️ " if source == "OCR" else "🎤 "
            print(f"{icon} [{source}] : {display_text}")
            if keywords:
                print(f"    🔑 Keywords: {keywords}")
            print("-" * 30)

        print("\n" + "="*50)
        print(" ✅ ACTION ITEMS (TASKS) ")
        print("="*50)
        cursor.execute("SELECT id, assignee, description, status FROM action_items")
        actions = cursor.fetchall()
        if not actions:
            print("Abhi koi action item nahi hai.")
        for row in actions:
            print(f"[{row[3].upper()}] 👤 {row[1]} ➡️ {row[2]}")

    except sqlite3.OperationalError as e:
        print(f"❌ Table error: {e}. (Shayad tables abhi theek se create nahi hui hain)")
    finally:
        conn.close()
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    view_database()