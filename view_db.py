import sqlite3

def show_saved_data():
    conn = sqlite3.connect("meeting_assistant.db")
    cursor = conn.cursor()
    
    print("\n--- 📝 SAVED TRANSCRIPTS ---")
    cursor.execute("SELECT text, keywords FROM transcripts")
    for row in cursor.fetchall():
        print(f"Text: {row[0]} | Keywords: {row[1]}")
        
    print("\n--- ✅ SAVED ACTION ITEMS ---")
    cursor.execute("SELECT description FROM action_items")
    for row in cursor.fetchall():
        print(f"Task: {row[0]}")
        
    conn.close()

if __name__ == "__main__":
    show_saved_data()