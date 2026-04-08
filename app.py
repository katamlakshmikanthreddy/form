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
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_private = db.Column(db.Boolean, default=False)
    habits = db.relationship('Habit', backref='owner', lazy=True)
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers_list', lazy='dynamic'), lazy='dynamic'
    )
    def follow(self, user):
        if not self.is_following(user): self.followed.append(user)
    def unfollow(self, user):
        if self.is_following(user): self.followed.remove(user)
    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class FollowRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    habit_name = db.Column(db.String(200))
    status = db.Column(db.String(50), default='pending') 

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# -------- PAGE ROUTES -------- #
@app.route('/')
def home(): return render_template('login.html')
@app.route('/signup_page')
def signup_page(): return render_template('signup.html')
@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')
@app.route('/other/<username>')
def other_user_page(username): return render_template('other.html')
@app.route('/user/<username>/followers')
def followers_view(username): return render_template('followers.html')
@app.route('/user/<username>/following')
def following_view(username): return render_template('following.html')
@app.route('/notifications')
def notifications_page(): return render_template('notifications.html')
@app.route('/chats')
def chats_page(): return render_template('chats.html')
@app.route('/chat/<username>')
def chat_view(username): return render_template('chat.html')
@app.route('/new_chat')
def new_chat_page(): return render_template('new_chat.html')

# -------- API -------- #
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first(): return jsonify({"message":"Taken"}), 400
    db.session.add(User(username=data['username'], password=data['password']))
    db.session.commit()
    return jsonify({"message": "Signup successful"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if not user: return jsonify({"message": "Invalid"}), 401
    return jsonify({"token": create_access_token(identity=str(user.id)), "username": user.username})

@app.route('/api/user_info/<username>')
@jwt_required()
def get_user_info(username):
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"message": "Not found"}), 404
    me = User.query.get(get_jwt_identity())
    pending = FollowRequest.query.filter_by(sender_id=me.id, recipient_id=user.id).first()
    return jsonify({
        "username": user.username,
        "follower_count": user.followers_list.count(),
        "following_count": user.followed.count(),
        "is_following": me.is_following(user),
        "has_requested": pending is not None,
        "follows_me": user.is_following(me),
        "is_private": user.is_private
    })

# --- CHAT API ---
@app.route('/api/mutuals', methods=['GET'])
@jwt_required()
def get_mutuals():
    me = User.query.get(get_jwt_identity())
    following = me.followed.all()
    mutuals = [u for u in following if u.is_following(me)]
    return jsonify([{"username": u.username} for u in mutuals])

@app.route('/api/chats/summary', methods=['GET'])
@jwt_required()
def get_chat_summary():
    uid = int(get_jwt_identity())
    msgs = Message.query.filter((Message.sender_id == uid) | (Message.recipient_id == uid)).order_by(Message.timestamp.desc()).all()
    summary = {}
    for m in msgs:
        other_id = m.recipient_id if m.sender_id == uid else m.sender_id
        if other_id not in summary:
            other_user = User.query.get(other_id)
            summary[other_id] = {
                "username": other_user.username,
                "last_msg": m.content,
                "time": m.timestamp.strftime("%H:%M")
            }
    return jsonify(list(summary.values()))

@app.route('/api/messages/<username>', methods=['GET', 'POST'])
@jwt_required()
def handle_messages(username):
    me = User.query.get(get_jwt_identity())
    other = User.query.filter_by(username=username).first()
    if not other: return jsonify({"message": "User not found"}), 404
    if request.method == 'POST':
        content = request.get_json().get('content')
        db.session.add(Message(sender_id=me.id, recipient_id=other.id, content=content))
        db.session.commit()
        return jsonify({"message": "Sent"})
    msgs = Message.query.filter(
        ((Message.sender_id == me.id) & (Message.recipient_id == other.id)) |
        ((Message.sender_id == other.id) & (Message.recipient_id == me.id))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{"content": m.content, "is_me": m.sender_id == me.id, "time": m.timestamp.strftime("%H:%M")} for m in msgs])

# ... [Existing Follow, Reminder, and Habit APIs remain the same] ...

@app.route('/api/follow/<username>', methods=['POST'])
@jwt_required()
def follow_user(username):
    me, target = User.query.get(get_jwt_identity()), User.query.filter_by(username=username).first()
    if not target or me.id == target.id: return jsonify({"message": "Error"}), 400
    if target.is_private:
        if FollowRequest.query.filter_by(sender_id=me.id, recipient_id=target.id).first():
            return jsonify({"message": "Request already sent"}), 400
        db.session.add(FollowRequest(sender_id=me.id, recipient_id=target.id))
        db.session.commit()
        return jsonify({"message": "Request Sent"})
    me.follow(target); db.session.commit()
    return jsonify({"message": "Followed"})

@app.route('/api/requests', methods=['GET'])
@jwt_required()
def get_requests():
    reqs = FollowRequest.query.filter_by(recipient_id=get_jwt_identity()).all()
    return jsonify([{"id": r.id, "sender": User.query.get(r.sender_id).username} for r in reqs])

@app.route('/api/request_action/<int:rid>/<action>', methods=['POST'])
@jwt_required()
def request_action(rid, action):
    req = FollowRequest.query.get(rid)
    if not req or str(req.recipient_id) != get_jwt_identity(): return jsonify({"message": "Error"}), 403
    if action == 'accept':
        User.query.get(req.sender_id).follow(User.query.get(req.recipient_id))
    db.session.delete(req); db.session.commit()
    return jsonify({"message": "Success"})

@app.route('/api/remind', methods=['POST'])
@jwt_required()
def send_reminder():
    data = request.get_json()
    me_id = get_jwt_identity()
    target = User.query.filter_by(username=data['target']).first()
    if not target or not target.is_private:
        return jsonify({"message": "Only private users can be reminded"}), 400
    existing = Reminder.query.filter_by(sender_id=me_id, recipient_id=target.id, habit_name=data['habit']).first()
    if existing: return jsonify({"message": "Reminder already sent for this habit"}), 400
    db.session.add(Reminder(sender_id=me_id, recipient_id=target.id, habit_name=data['habit']))
    db.session.commit()
    return jsonify({"message": "Reminder sent!"})

@app.route('/api/notifications/reminders', methods=['GET'])
@jwt_required()
def get_reminders():
    uid = get_jwt_identity()
    received = Reminder.query.filter_by(recipient_id=uid, status='pending').all()
    acks = Reminder.query.filter_by(sender_id=uid, status='acknowledged').all()
    return jsonify({
        "received": [{"id": r.id, "sender": User.query.get(r.sender_id).username, "habit": r.habit_name} for r in received],
        "acks": [{"id": r.id, "recipient": User.query.get(r.recipient_id).username, "habit": r.habit_name} for r in acks]
    })

@app.route('/api/remind/ack/<int:rid>', methods=['POST'])
@jwt_required()
def ack_reminder(rid):
    rem = Reminder.query.get(rid)
    if rem and str(rem.recipient_id) == get_jwt_identity():
        rem.status = 'acknowledged'; db.session.commit()
    return jsonify({"message": "OK"})

@app.route('/api/remind/clear/<int:rid>', methods=['DELETE'])
@jwt_required()
def clear_reminder(rid):
    rem = Reminder.query.get(rid)
    if rem: db.session.delete(rem); db.session.commit()
    return jsonify({"message": "Cleared"})

@app.route('/api/search')
@jwt_required()
def search():
    target = User.query.filter_by(username=request.args.get('username', '').strip()).first()
    if not target: return jsonify({"message": "Not found"}), 404
    me = User.query.get(get_jwt_identity())
    if target.is_private and not me.is_following(target) and me.id != target.id:
        return jsonify({"message": "Private", "habits": []})
    return jsonify({"habits": [{"name": h.name, "completed": h.completed} for h in target.habits]})

@app.route('/api/habits', methods=['GET', 'POST'])
@jwt_required()
def handle_habits():
    uid = get_jwt_identity()
    if request.method == 'GET':
        habits = Habit.query.filter_by(user_id=uid).all()
        return jsonify([{"id": h.id, "name": h.name, "completed": h.completed} for h in habits])
    db.session.add(Habit(name=request.get_json()['name'], user_id=uid))
    db.session.commit()
    return jsonify({"message": "Added"}), 201

@app.route('/api/habits/<int:hid>', methods=['PUT', 'DELETE'])
@jwt_required()
def habit_ops(hid):
    h = Habit.query.filter_by(id=hid, user_id=get_jwt_identity()).first()
    if not h: return jsonify({"message": "Not found"}), 404
    if request.method == 'PUT': h.completed = not h.completed
    else: db.session.delete(h)
    db.session.commit()
    return jsonify({"message": "Success"})

@app.route('/api/user/privacy', methods=['POST'])
@jwt_required()
def toggle_privacy():
    user = User.query.get(get_jwt_identity())
    user.is_private = request.get_json().get('is_private', False)
    db.session.commit()
    return jsonify({"is_private": user.is_private})

@app.route('/api/social/<username>/<type>')
@jwt_required()
def get_social(username, type):
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify([]), 404
    users = user.followers_list.all() if type == 'followers' else user.followed.all()
    return jsonify([{"username": u.username} for u in users])

@app.route('/api/remove_follower/<username>', methods=['POST'])
@jwt_required()
def remove_follower(username):
    me, target = User.query.get(get_jwt_identity()), User.query.filter_by(username=username).first()
    if target: target.unfollow(me); db.session.commit()
    return jsonify({"message": "Removed"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)