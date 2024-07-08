import sqlite3

def read_data():
    conn = sqlite3.connect('sound_meter.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sound_data")
    rows = cursor.fetchall()
    
    for row in rows:
        print(row)
    
    conn.close()

if __name__ == '__main__':
    read_data()
