import sqlite3
import json
import uuid

def seed_stages():
    conn = sqlite3.connect('reports.db')
    cursor = conn.cursor()

    # 1. Get the source stages (from beauty_salon)
    # We know beauty_salon has stages because we saw them.
    # We need the type_id for beauty_salon first.
    cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'beauty_salon'")
    source_type_row = cursor.fetchone()
    if not source_type_row:
        print("Error: beauty_salon type not found!")
        return

    source_type_id = source_type_row[0]
    print(f"Source Type ID (beauty_salon): {source_type_id}")

    # Get the stages
    cursor.execute("""
        SELECT stage_number, title, description, goal, expected_result, duration, tasks 
        FROM GrowthStages 
        WHERE business_type_id = ?
    """, (source_type_id,))
    
    stages_to_copy = cursor.fetchall()
    if not stages_to_copy:
        print("Error: No stages found for beauty_salon!")
        return
    
    print(f"Found {len(stages_to_copy)} stages to copy.")

    # 2. Get all other business types
    cursor.execute("SELECT id, type_key FROM BusinessTypes WHERE id != ?", (source_type_id,))
    target_types = cursor.fetchall()

    for type_id, type_key in target_types:
        print(f"Processing type: {type_key} ({type_id})...")
        
        # Check if stages already exist
        cursor.execute("SELECT COUNT(*) FROM GrowthStages WHERE business_type_id = ?", (type_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"  Skipping: Already has {count} stages.")
            continue

        # Insert stages
        for stage in stages_to_copy:
            new_id = str(uuid.uuid4())
            # Unpack stage data
            (stage_number, title, description, goal, expected_result, duration, tasks) = stage
            
            cursor.execute("""
                INSERT INTO GrowthStages (id, business_type_id, stage_number, title, description, goal, expected_result, duration, tasks, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (new_id, type_id, stage_number, title, description, goal, expected_result, duration, tasks))
        
        print(f"  Copied {len(stages_to_copy)} stages.")

    conn.commit()
    conn.close()
    print("Done!")

if __name__ == "__main__":
    seed_stages()
