from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)

app = Flask(__name__)

# 🔐 JWT config
app.config['JWT_SECRET_KEY'] = 'supersecretkey'

# DB config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

with app.app_context():
    db.create_all()

# ---------------- FRONTEND ---------------- #

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/signup_page')
def signup_page():
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ---------------- API ---------------- #

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "User exists"}), 400

    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Signup successful"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username, password=password).first()

    if not user:
        return jsonify({"message": "Invalid credentials"}), 401

    # 🔥 Create JWT token
    token = create_access_token(identity=username)

    return jsonify({
        "message": "Login successful",
        "token": token
    })

@app.route('/api/submit', methods=['POST'])
@jwt_required()
def submit():
    current_user = get_jwt_identity()

    data = request.get_json()
    message = data.get('message')

    if message == "123":
        return jsonify({
            "user": current_user,
            "response": "456"
        })
    else:
        return jsonify({"response": "Invalid input"})

# ---------------- RUN ---------------- #

if __name__ == '__main__':
    app.run(debug=True)