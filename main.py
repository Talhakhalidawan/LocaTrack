from kivy import Config
Config.set('graphics', 'multisamples', '0')
import os
os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Color, RoundedRectangle
from threading import Thread
import requests
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from plyer import gps
import geocoder
from datetime import datetime

app = Flask(__name__)

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:1234786@192.168.42.114/FlaskApp'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

# Location model
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<Location {self.username}, {self.latitude}, {self.longitude}>'

with app.app_context():
    db.create_all()

# Flask routes
@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    user = User.query.filter_by(username=username, password=password).first()
    
    if user:
        return {"status": "Success", "message": "Login successful!"}, 200
    else:
        return {"status": "Error", "message": "Invalid credentials!"}, 400

@app.route('/submit_location', methods=['POST'])
def submit_location():
    data = request.json
    username = data.get("username")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    timestamp = data.get("timestamp")

    if username and latitude and longitude and timestamp:
        # Save location data into the database
        location = Location(username=username, latitude=latitude, longitude=longitude, timestamp=datetime.fromisoformat(timestamp))
        db.session.add(location)
        db.session.commit()

        return {"status": "Success", "message": "Location data saved!"}, 200
    else:
        return {"status": "Error", "message": "Invalid location data!"}, 400

def start_flask():
    app.run(host='127.0.0.1', port=5000, use_reloader=False)

# Custom widget class for rounded corners
class RoundedButton(Button):
    def __init__(self, **kwargs):
        super(RoundedButton, self).__init__(**kwargs)
        self.background_normal = ''  # Remove default background
        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0, 0.5, 1, 1)  # Button color
            # Draw rounded rectangle
            RoundedRectangle(pos=self.pos, size=self.size, radius=[20])  # Radius for rounded corners

# Global variable to store the logged-in username
logged_in_username = None

# Kivy screen for login page
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super(LoginScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=30, spacing=15)
        
        title = Label(text="Login", font_size=32, bold=True, color=(0, 0, 1, 1))
        layout.add_widget(title)

        self.username_input = TextInput(hint_text="Username", multiline=False, padding=(10, 10), size_hint=(1, 0.3))
        layout.add_widget(self.username_input)

        self.password_input = TextInput(hint_text="Password", multiline=False, password=True, padding=(10, 10), size_hint=(1, 0.3))
        layout.add_widget(self.password_input)

        login_button = RoundedButton(text="Login", font_size=18)
        login_button.bind(on_press=self.submit_data)
        layout.add_widget(login_button)

        self.add_widget(layout)

    def submit_data(self, instance):
        # Data to send to Flask server
        data = {
            "username": self.username_input.text,
            "password": self.password_input.text
        }
        try:
            # Post data to Flask server
            response = requests.post("http://127.0.0.1:5000/submit", json=data)
            response_data = response.json()
            print("Response from Flask:", response_data)
            if response_data['status'] == 'Success':
                print("Login successful!")
                global logged_in_username
                logged_in_username = self.username_input.text  # Store the logged-in username
                # Redirect to HomeScreen
                self.manager.current = 'home'
            else:
                print("Login failed:", response_data.get("message"))
        except Exception as e:
            print("Error connecting to Flask:", e)

# Kivy screen for home page
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=30, spacing=15)

        title = Label(text="Home", font_size=32, bold=True, color=(0, 0, 1, 1))
        layout.add_widget(title)

        save_button = RoundedButton(text="Save Location", font_size=18)
        save_button.bind(on_press=self.save_location)
        layout.add_widget(save_button)

        self.add_widget(layout)

    def save_location(self, instance):
        # Fetch location data
        g = geocoder.ip("me") if not gps_available() else get_gps_location()
        latitude, longitude = g.latlng if g.latlng else (None, None)
        timestamp = datetime.now()

        # Use the stored logged-in username
        if logged_in_username:
            username = logged_in_username
            data = {
                "username": username,
                "latitude": latitude,
                "longitude": longitude,
                "timestamp": timestamp.isoformat()
            }
            try:
                response = requests.post("http://127.0.0.1:5000/submit_location", json=data)
                response_data = response.json()
                if response_data['status'] == 'Success':
                    print("Location data saved successfully!")
                else:
                    print("Failed to save location:", response_data.get("message"))
            except Exception as e:
                print("Error connecting to Flask:", e)
        else:
            print("No user logged in!")

def gps_available():
    """Check if GPS is available."""
    try:
        gps.configure()
        return True
    except Exception:
        return False

def get_gps_location():
    """Fetch GPS location using plyer."""
    location = None
    def on_location_changed(latitude, longitude):
        nonlocal location
        location = (latitude, longitude)

    gps.configure(on_location_changed=on_location_changed)
    gps.start()
    gps.stop()

    return location

# Main app with screen manager
class MainApp(App):
    def build(self):
        # Start Flask server in a separate thread
        Thread(target=start_flask).start()

        # Screen manager to switch between login and home
        sm = ScreenManager()

        # Adding the screens
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(HomeScreen(name='home'))

        return sm

if __name__ == '__main__':
    MainApp().run()
