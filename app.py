from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)

app = Flask(__name__)

app.config['JWT_SECRET_KEY'] = 'supersecretkey' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)

# -------- MODELS -------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    habits = db.relationship('Habit', backref='owner', lazy=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# -------- FRONTEND ROUTES -------- #

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/signup_page')
def signup_page():
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/other/<username>')
def other_user_page(username):
    return render_template('other.html')

# -------- AUTH API -------- #

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Missing fields"}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({"message": "User exists"}), 400

    user = User(username=data['username'], password=data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Signup successful"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(
        username=data.get('username'),
        password=data.get('password')
    ).first()

    if not user:
        return jsonify({"message": "Invalid credentials"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token})

# -------- HABITS API -------- #

@app.route('/api/habits', methods=['GET'])
@jwt_required()
def get_habits():
    user_id = get_jwt_identity()
    habits = Habit.query.filter_by(user_id=user_id).all()
    return jsonify([
        {"id": h.id, "name": h.name, "completed": h.completed}
        for h in habits
    ])

@app.route('/api/habits', methods=['POST'])
@jwt_required()
def add_habit():
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"message": "Name required"}), 400

    habit = Habit(name=data['name'], user_id=user_id)
    db.session.add(habit)
    db.session.commit()
    return jsonify({"message": "Added"}), 201

@app.route('/api/habits/<int:id>', methods=['PUT'])
@jwt_required()
def toggle_habit(id):
    user_id = get_jwt_identity()
    habit = Habit.query.filter_by(id=id, user_id=user_id).first()
    if not habit: return jsonify({"message": "Not found"}), 404
    habit.completed = not habit.completed
    db.session.commit()
    return jsonify({"message": "Updated"})

@app.route('/api/habits/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_habit(id):
    user_id = get_jwt_identity()
    habit = Habit.query.filter_by(id=id, user_id=user_id).first()
    if not habit: return jsonify({"message": "Not found"}), 404
    db.session.delete(habit)
    db.session.commit()
    return jsonify({"message": "Deleted"})

# -------- SEARCH API -------- #

@app.route('/api/search', methods=['GET'])
@jwt_required()
def search_habits():
    username = request.args.get('username')
    target_user = User.query.filter_by(username=username).first()
    
    if not target_user:
        return jsonify({"message": "User not found"}), 404

    habits = Habit.query.filter_by(user_id=target_user.id).all()
    return jsonify({
        "username": target_user.username,
        "habits": [{"name": h.name, "completed": h.completed} for h in habits]
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)