from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import random
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__, template_folder=r'templets')
app.secret_key = 'your_secret_key'

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT") 



# PostgreSQL connection settings
conn = psycopg2.connect(
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT')
)

# Get the service account credentials from the environment variable
google_credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')

# Ensure the credentials are available
if google_credentials_json is None:
    raise ValueError("Google credentials are not set in the environment variables.")

# Dummy admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Sample data for live count and logs (in a real project, you would fetch this from a database)
live_count = 5  # Initial dummy live count
total_entered = 20
total_exited = 15

# Folder where images are stored
IMAGE_FOLDER = os.path.join('static', 'images')

def upload_to_drive(local_path, filename, folder_id):
    # Load credentials
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(google_credentials_json),
        scopes=['https://www.googleapis.com/auth/drive']
    )

    # Build the Drive API client
    drive_service = build('drive', 'v3', credentials=credentials)

    # Create file metadata including folder location
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }

    media = MediaFileUpload(local_path, resumable=True)
    
    # Upload the file
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    print(f"Uploaded File ID: {file.get('id')}")
    return file.get('id')

# Function to extract timestamp from image filename
def extract_timestamp(filename):

    
    # Regex to match the timestamp part of the filename (e.g., 'unknown_20250423_095445.jpg')
    match = re.match(r"unknown_(\d{8})_(\d{6})\.jpg", filename)
    if match:
        # Extract date and time components
        date = match.group(1)  # YYYYMMDD
        time = match.group(2)  # HHMMSS
        timestamp = f"{date} {time[:2]}:{time[2:4]}:{time[4:]}"  # Format as 'YYYYMMDD HH:MM:SS'
        return timestamp
    return None

def get_authorized_persons():
    # Directory where authorized images are stored
    images_folder = os.path.join('static', 'images')
    
    # Get all image files in the 'images' folder
    image_files = [f for f in os.listdir(images_folder) if f.endswith('.jpg')]
    
    # Extract person_id and name from the image filenames and prepare the list
    authorized_persons = []
    for image_file in image_files:
        try:
            # Assuming filename format: id_name.jpg
            person_id, name_with_extension = image_file.split('_', 1)
            name = name_with_extension.split('.')[0]  # Remove file extension
            
            # Convert person_id to an integer if it's a valid number
            person_id = int(person_id)  # This will raise an error if it's not a valid integer
            
            authorized_persons.append({
                'id': person_id,
                'name': name,
                'image_filename': image_file
            })
        except ValueError:
            # Handle the case where the filename format is incorrect or ID can't be converted to an integer
            continue

    return authorized_persons




# Fetch recent logs for face recognition
def get_recent_logs():
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT user_id, name, entry_time
        FROM entry_logs_v2
        ORDER BY entry_time DESC
        LIMIT 5;
    """)
    entry_logs = cur.fetchall()
    return entry_logs

# Dummy data for live count (you can simulate different random counts)
def generate_dummy_data():
    global live_count, total_entered, total_exited
    
    total_entered += random.randint(1, 3)
    total_exited += random.randint(0, 2)
    live_count=total_entered-total_exited

@app.route('/')
def index():
    if 'logged_in' in session:
        generate_dummy_data()  # Simulate live count updates
        entry_logs = get_recent_logs()  # Fetch recent face recognition logs
        
        # List of image files in the static/images folder
        image_files = [f for f in os.listdir(IMAGE_FOLDER) if f.endswith('.jpg')]
        
        # Extract the timestamp and prepare a list of image data
        images_data = []
        for image_file in image_files:
            timestamp = extract_timestamp(image_file)
            if timestamp:
                images_data.append({
                    'filename': image_file,
                    'timestamp': timestamp
                })
        
        # Pass the images data to the template
        return render_template('index.html',
                               live_count=live_count,
                               total_entered=total_entered,
                               total_exited=total_exited,
                               entry_logs=entry_logs,
                               images_data=images_data)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials, please try again.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/add_person', methods=['GET', 'POST'])
def add_person():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        image = request.files['image']
        name = request.form['name']
        person_id = request.form['person_id']
        
        # Check if the image is valid
        if image:
            # Create the filename as id_name.jpg
            filename = f"{person_id}_{name}.jpg"
            
            # Secure the filename and save the image to the static/images folder
            image_path = os.path.join('static', 'images', filename)
            image.save(image_path)
            upload_to_drive(image_path, filename, '1HDnzyC7squbq6aheymQF0xAprCR8H0Nz')
        
        return render_template('add_person.html', success=True, name=name, person_id=person_id)
    
    return render_template('add_person.html')

@app.route('/authorized_persons')
def authorized_persons():
    authorized_persons = get_authorized_persons()
    
    # Debugging: Ensure the IDs are integers
    # Debugging: Ensure the IDs are integers
    for person in authorized_persons:
        if not isinstance(person['id'], int):  # Accessing 'id' as a dictionary key
            print(f"Invalid ID found: {person['id']}")  # Debugging
            # Optionally replace invalid ID with a valid value or skip this person
            person['id'] = -1  # Example: Replace with a default ID (if appropriate)

    
    return render_template('authorized_persons.html', authorized_persons=authorized_persons)



@app.route('/remove_person/<int:person_id>', methods=['POST'])
def remove_person(person_id):
    # Directory where authorized images are stored
    images_folder = os.path.join('static', 'images')
    
    # Get the authorized person data
    authorized_persons_list = get_authorized_persons()
    
    # Find the person with the specified ID
    person_to_remove = next((person for person in authorized_persons_list if person['id'] == person_id), None)
    
    if person_to_remove:
        # Get the image filename from the person's data
        person_image = person_to_remove['image_filename']
        
        # Construct the full path to the image file
        image_path = os.path.join(images_folder, person_image)
        
        try:
            # Ensure the file exists before attempting to remove it
            if os.path.exists(image_path):
                os.remove(image_path)  # Remove the image
            else:
                print(f"File not found: {image_path}")
        except Exception as e:
            print(f"Error removing file: {e}")
        
        # After removal, redirect or render a page to update the list
        return redirect(url_for('authorized_persons'))
    
    return "Person not found", 404



if __name__ == "__main__":
    app.run(debug=True)
