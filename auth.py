from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from app import db
from sqlalchemy.exc import SQLAlchemyError
from forms import LoginForm

auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student')
        group = request.form.get('group', '').strip() if role == 'student' else None

        if not all([email, name, password]):
            flash('Все поля обязательны для заполнения', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'error')
            return redirect(url_for('auth.register'))

        if role == 'student' and not group:
            flash('Поле "Группа" обязательно для учеников.', 'error')
            return redirect(url_for('auth.register'))

        try:
            if User.query.filter_by(email=email).first():
                flash('Пользователь с таким email уже существует', 'error')
                return redirect(url_for('auth.register'))

            new_user = User(
                email=email,
                name=name,
                role=role,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                group=group
            )
            db.session.add(new_user)
            db.session.commit()

            flash('Регистрация прошла успешно! Пожалуйста, войдите в систему.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError:
            db.session.rollback()
            flash('Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.', 'error')
            return redirect(url_for('auth.register'))

    return render_template('register.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data.strip()

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Неверный email или пароль', 'error')
            return redirect(url_for('auth.login'))

        session['user_id'] = user.id
        session['username'] = user.name
        session['role'] = user.role

        flash(f'Добро пожаловать, {user.name}!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('login.html', form=form)



@auth.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('auth.login'))
