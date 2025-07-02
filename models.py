from flask_login import UserMixin
from datetime import datetime
from app import db

# Связка "учитель-студент"
teacher_student = db.Table(
    'teacher_student',
    db.Column('teacher_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    role = db.Column(db.String(50))  # 'student' or 'teacher'
    group = db.Column(db.String(50))
    first_name = db.Column(db.String(150))
    last_name = db.Column(db.String(150))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # 'male', 'female', 'other'

    # связь с другими пользователями (студентами/учителями)
    students = db.relationship(
        'User',
        secondary=teacher_student,
        primaryjoin=(id == teacher_student.c.teacher_id),
        secondaryjoin=(id == teacher_student.c.student_id),
        backref=db.backref('teachers', lazy='dynamic'),
        lazy='dynamic'
    )

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.DateTime)
    max_score = db.Column(db.Integer, default=10)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submissions = db.relationship('Submission', backref='assignment', lazy=True)
    # связь с вопросами:
    questions = db.relationship('Question', backref='assignment', cascade='all, delete-orphan', lazy=True)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    solution_text = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    # для использования {{ submission.student.name }}
    student = db.relationship('User', foreign_keys=[student_id])

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'))
    score = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # связь с вариантами ответов:
    options = db.relationship('AnswerOption', backref='question', cascade='all, delete-orphan', lazy=True)

class AnswerOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)