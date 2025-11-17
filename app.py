from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import base64

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learncircle.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'creator'
    points = db.Column(db.Integer, default=0)
    badges = db.Column(db.String(500), default='')
    reputation_level = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_circles = db.relationship('Circle', backref='creator', lazy=True, foreign_keys='Circle.creator_id')
    completed_tasks = db.relationship('TaskCompletion', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
    messages = db.relationship('Message', backref='user', lazy=True)

class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(500))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    privacy = db.Column(db.String(20), default='public')  # 'public' or 'private'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    resources = db.relationship('Resource', backref='circle', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='circle', lazy=True, cascade='all, delete-orphan')
    members = db.relationship('CircleMember', backref='circle', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='circle', lazy=True, cascade='all, delete-orphan')

class CircleMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False)
    is_following = db.Column(db.Boolean, default=False)
    is_member = db.Column(db.Boolean, default=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='circle_memberships')

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_type = db.Column(db.String(20), nullable=False)  # 'pdf', 'link', 'video'
    content = db.Column(db.Text)  # File path or URL
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)
    
    creator = db.relationship('User', backref='resources')
    comments = db.relationship('Comment', backref='resource', lazy=True, cascade='all, delete-orphan')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    completions = db.relationship('TaskCompletion', backref='task', lazy=True, cascade='all, delete-orphan')

class TaskCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    completion_date = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PointsHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='points_history')

# Helper Functions
def award_points(user_id, points, reason):
    user = User.query.get(user_id)
    if user:
        user.points += points
        history = PointsHistory(user_id=user_id, points=points, reason=reason)
        db.session.add(history)
        
        # Update reputation level
        if user.points >= 1000:
            user.reputation_level = 5
        elif user.points >= 500:
            user.reputation_level = 4
        elif user.points >= 200:
            user.reputation_level = 3
        elif user.points >= 50:
            user.reputation_level = 2
        
        db.session.commit()

# API Routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/index.html')
def index_html():
    return send_from_directory('.', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    hashed_password = generate_password_hash(data['password'])
    user = User(
        username=data['username'],
        email=data['email'],
        password=hashed_password,
        role=data['role']
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    
    if user and check_password_hash(user.password, data['password']):
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'points': user.points,
            'reputation_level': user.reputation_level
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/circles', methods=['GET', 'POST'])
def circles():
    if request.method == 'POST':
        data = request.json
        circle = Circle(
            title=data['title'],
            description=data['description'],
            tags=data.get('tags', ''),
            creator_id=data['creator_id'],
            privacy=data.get('privacy', 'public')
        )
        
        db.session.add(circle)
        db.session.commit()
        
        return jsonify({
            'id': circle.id,
            'title': circle.title,
            'description': circle.description,
            'tags': circle.tags,
            'creator_id': circle.creator_id,
            'privacy': circle.privacy,
            'created_at': circle.created_at.isoformat()
        }), 201
    
    # GET - Search and filter circles
    search = request.args.get('search', '')
    circles = Circle.query.filter(Circle.privacy == 'public')
    
    if search:
        circles = circles.filter(
            db.or_(
                Circle.title.ilike(f'%{search}%'),
                Circle.tags.ilike(f'%{search}%'),
                Circle.description.ilike(f'%{search}%')
            )
        )
    
    circles = circles.all()
    
    return jsonify([{
        'id': c.id,
        'title': c.title,
        'description': c.description,
        'tags': c.tags,
        'creator_id': c.creator_id,
        'creator_username': c.creator.username,
        'privacy': c.privacy,
        'created_at': c.created_at.isoformat(),
        'member_count': len(c.members)
    } for c in circles])

@app.route('/api/circles/<int:circle_id>', methods=['GET'])
def get_circle(circle_id):
    circle = Circle.query.get_or_404(circle_id)
    
    return jsonify({
        'id': circle.id,
        'title': circle.title,
        'description': circle.description,
        'tags': circle.tags,
        'creator_id': circle.creator_id,
        'creator_username': circle.creator.username,
        'privacy': circle.privacy,
        'created_at': circle.created_at.isoformat(),
        'member_count': len(circle.members)
    })

@app.route('/api/circles/<int:circle_id>/join', methods=['POST'])
def join_circle(circle_id):
    data = request.json
    user_id = data['user_id']
    
    existing = CircleMember.query.filter_by(user_id=user_id, circle_id=circle_id).first()
    
    if existing:
        return jsonify({'message': 'Already a member'}), 200
    
    member = CircleMember(user_id=user_id, circle_id=circle_id, is_member=True)
    db.session.add(member)
    db.session.commit()
    
    # Award points to creator
    circle = Circle.query.get(circle_id)
    award_points(circle.creator_id, 5, f'New member joined {circle.title}')
    
    return jsonify({'message': 'Joined successfully'}), 201

@app.route('/api/circles/<int:circle_id>/follow', methods=['POST'])
def follow_circle(circle_id):
    data = request.json
    user_id = data['user_id']
    
    member = CircleMember.query.filter_by(user_id=user_id, circle_id=circle_id).first()
    
    if member:
        member.is_following = True
    else:
        member = CircleMember(user_id=user_id, circle_id=circle_id, is_following=True, is_member=False)
        db.session.add(member)
    
    db.session.commit()
    
    # Award points to creator
    circle = Circle.query.get(circle_id)
    award_points(circle.creator_id, 10, f'New follower on {circle.title}')
    
    return jsonify({'message': 'Following successfully'}), 201

@app.route('/api/circles/<int:circle_id>/unfollow', methods=['POST'])
def unfollow_circle(circle_id):
    data = request.json
    user_id = data['user_id']
    
    member = CircleMember.query.filter_by(user_id=user_id, circle_id=circle_id).first()
    
    if member:
        member.is_following = False
        if not member.is_member:
            db.session.delete(member)
        db.session.commit()
    
    return jsonify({'message': 'Unfollowed successfully'}), 200

@app.route('/api/circles/<int:circle_id>/membership', methods=['GET'])
def get_membership(circle_id):
    user_id = request.args.get('user_id')
    
    member = CircleMember.query.filter_by(user_id=user_id, circle_id=circle_id).first()
    
    if member:
        return jsonify({
            'is_member': member.is_member,
            'is_following': member.is_following
        })
    
    return jsonify({
        'is_member': False,
        'is_following': False
    })

@app.route('/api/resources', methods=['POST'])
def create_resource():
    data = request.json
    
    resource = Resource(
        title=data['title'],
        circle_id=data['circle_id'],
        creator_id=data['creator_id'],
        resource_type=data['resource_type'],
        content=data['content']
    )
    
    db.session.add(resource)
    db.session.commit()
    
    return jsonify({
        'id': resource.id,
        'title': resource.title,
        'resource_type': resource.resource_type,
        'upload_date': resource.upload_date.isoformat()
    }), 201

@app.route('/api/resources/upload', methods=['POST'])
def upload_resource():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    title = request.form.get('title')
    circle_id = request.form.get('circle_id')
    creator_id = request.form.get('creator_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    resource = Resource(
        title=title,
        circle_id=circle_id,
        creator_id=creator_id,
        resource_type='pdf',
        content=filename
    )
    
    db.session.add(resource)
    db.session.commit()
    
    return jsonify({
        'id': resource.id,
        'title': resource.title,
        'resource_type': resource.resource_type
    }), 201

@app.route('/api/circles/<int:circle_id>/resources', methods=['GET'])
def get_circle_resources(circle_id):
    resources = Resource.query.filter_by(circle_id=circle_id).all()
    
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'resource_type': r.resource_type,
        'content': r.content,
        'upload_date': r.upload_date.isoformat(),
        'view_count': r.view_count,
        'creator_username': r.creator.username
    } for r in resources])

@app.route('/api/resources/<int:resource_id>/view', methods=['POST'])
def view_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    resource.view_count += 1
    db.session.commit()
    
    # Award points to creator every 10 views
    if resource.view_count % 10 == 0:
        award_points(resource.creator_id, 5, f'Resource "{resource.title}" reached {resource.view_count} views')
    
    return jsonify({'view_count': resource.view_count})

@app.route('/api/tasks', methods=['POST'])
def create_task():
    try:
        data = request.json
        
        # Parse the due_date
        due_date_str = data['due_date']
        # Handle both formats: with 'T' or with space
        if 'T' in due_date_str:
            due_date = datetime.fromisoformat(due_date_str)
        else:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
        
        task = Task(
            title=data['title'],
            description=data['description'],
            due_date=due_date,
            circle_id=data['circle_id']
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'due_date': task.due_date.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/circles/<int:circle_id>/tasks', methods=['GET'])
def get_circle_tasks(circle_id):
    tasks = Task.query.filter_by(circle_id=circle_id).all()
    
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'due_date': t.due_date.isoformat(),
        'created_at': t.created_at.isoformat(),
        'completion_count': len(t.completions)
    } for t in tasks])

@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    data = request.json
    user_id = data['user_id']
    
    existing = TaskCompletion.query.filter_by(task_id=task_id, user_id=user_id).first()
    
    if existing:
        return jsonify({'message': 'Task already completed'}), 200
    
    completion = TaskCompletion(task_id=task_id, user_id=user_id)
    db.session.add(completion)
    db.session.commit()
    
    # Award points to task creator
    task = Task.query.get(task_id)
    circle = Circle.query.get(task.circle_id)
    award_points(circle.creator_id, 15, f'Student completed task "{task.title}"')
    
    return jsonify({'message': 'Task completed'}), 201

@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def get_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    followed_circles = CircleMember.query.filter_by(user_id=user_id, is_following=True).all()
    created_circles = Circle.query.filter_by(creator_id=user_id).all()
    completed_tasks = TaskCompletion.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'points': user.points,
        'badges': user.badges,
        'reputation_level': user.reputation_level,
        'followed_circles': [{
            'id': m.circle.id,
            'title': m.circle.title
        } for m in followed_circles],
        'created_circles': [{
            'id': c.id,
            'title': c.title,
            'member_count': len(c.members)
        } for c in created_circles],
        'completed_tasks_count': len(completed_tasks)
    })

@app.route('/api/comments', methods=['POST'])
def create_comment():
    data = request.json
    
    comment = Comment(
        text=data['text'],
        user_id=data['user_id'],
        resource_id=data['resource_id']
    )
    
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'text': comment.text,
        'timestamp': comment.timestamp.isoformat()
    }), 201

@app.route('/api/resources/<int:resource_id>/comments', methods=['GET'])
def get_comments(resource_id):
    comments = Comment.query.filter_by(resource_id=resource_id).order_by(Comment.timestamp.desc()).all()
    
    return jsonify([{
        'id': c.id,
        'text': c.text,
        'user_id': c.user_id,
        'username': c.user.username,
        'timestamp': c.timestamp.isoformat()
    } for c in comments])

@app.route('/api/circles/<int:circle_id>/messages', methods=['GET', 'POST'])
def circle_messages(circle_id):
    if request.method == 'POST':
        data = request.json
        
        message = Message(
            text=data['text'],
            user_id=data['user_id'],
            circle_id=circle_id
        )
        
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'id': message.id,
            'text': message.text,
            'timestamp': message.timestamp.isoformat()
        }), 201
    
    messages = Message.query.filter_by(circle_id=circle_id).order_by(Message.timestamp.asc()).all()
    
    return jsonify([{
        'id': m.id,
        'text': m.text,
        'user_id': m.user_id,
        'username': m.user.username,
        'timestamp': m.timestamp.isoformat()
    } for m in messages])

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)