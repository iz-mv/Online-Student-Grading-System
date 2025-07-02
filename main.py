from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from app import db
from models import User, Assignment, Score, Submission, Question, AnswerOption
from datetime import datetime
from werkzeug.security import generate_password_hash
from functools import wraps

main = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@main.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if user.role == 'teacher':
        students = user.students.order_by(User.name.asc()).all()
        assignments = Assignment.query.filter_by(teacher_id=user.id).all()
        avg_scores = {}
        for student in students:
            submissions = Submission.query.filter_by(student_id=student.id).all()
            scores = [s.score for s in submissions if s.score is not None]
            avg_scores[student.id] = round(sum(scores) / len(scores), 2) if scores else None
        return render_template(
            'teacher_dashboard.html',
            students=students,
            assignments=assignments,
            current_user=user,
            avg_scores=avg_scores
        )
    else:
        return redirect(url_for('main.student_dashboard'))

@main.route('/student_dashboard')
@login_required
def student_dashboard():
    user = User.query.get(session['user_id'])
    if user.role != 'student':
        return redirect(url_for('main.dashboard'))
    now = datetime.now()
    assignments = Assignment.query.filter(
        Assignment.teacher_id.in_([t.id for t in user.teachers])
    ).all()
    for assignment in assignments:
        assignment.submission = Submission.query.filter_by(
            student_id=user.id,
            assignment_id=assignment.id
        ).first()
    return render_template(
        'student_dashboard.html',
        assignments=assignments,
        now=now,
        current_user=user
    )

@main.route('/students')
@login_required
def students():
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        abort(403)
    group_filter = request.args.get('group', '').strip()
    score_filter = request.args.get('score', '')
    students_query = user.students.order_by(User.name.asc())
    if group_filter:
        students_query = students_query.filter_by(group=group_filter)
    students = students_query.all()
    all_groups = [g[0] for g in db.session.query(User.group).distinct() if g[0]]
    avg_scores = {}
    for student in students:
        submissions = Submission.query.filter_by(student_id=student.id).all()
        scores = [s.score for s in submissions if s.score is not None]
        avg_scores[student.id] = round(sum(scores) / len(scores), 2) if scores else 0
    if score_filter:
        op = score_filter[0]
        try:
            value = float(score_filter[1:])
            if op == '>':
                students = [s for s in students if avg_scores.get(s.id, 0) > value]
            elif op == '<':
                students = [s for s in students if avg_scores.get(s.id, 0) < value]
            elif op == '=':
                students = [s for s in students if avg_scores.get(s.id, 0) == value]
        except Exception:
            pass
    return render_template('students.html', students=students, all_groups=all_groups, avg_scores=avg_scores,
                           group_filter=group_filter, score_filter=score_filter)

@main.route('/students/add', methods=['POST'])
@login_required
def add_student():
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        abort(403)
    try:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        if not all([name, email]):
            flash('Имя и email обязательны', 'error')
            return redirect(url_for('main.students'))
        student = User.query.filter_by(email=email, role='student').first()
        if not student:
            flash('Пользователь с таким email не найден или он не является студентом', 'error')
            return redirect(url_for('main.students'))
        if student in user.students:
            flash('Студент уже добавлен к вам', 'warning')
        else:
            user.students.append(student)
            db.session.commit()
            flash('Студент успешно добавлен!', 'success')
        if student.name != name:
            student.name = name
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении студента: {str(e)}', 'error')
    return redirect(url_for('main.students'))

@main.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        abort(403)
    try:
        student = User.query.get_or_404(student_id)
        if student.role != 'student':
            flash('Нельзя удалить пользователя с другой ролью', 'error')
            return redirect(url_for('main.students'))
        if student in user.students:
            user.students.remove(student)
            db.session.commit()
            flash('Студент удалён из вашей группы', 'success')
        else:
            flash('Этот студент не прикреплён к вам', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении студента: {str(e)}', 'error')
    return redirect(url_for('main.students'))

@main.route('/assignments/create', methods=['GET', 'POST'])
@login_required
def create_assignment():
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        abort(403)
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form['description']
            deadline_str = request.form.get('deadline')
            deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else None
            max_score = int(request.form['max_score'])
            assignment = Assignment(
                title=title,
                description=description,
                deadline=deadline,
                max_score=max_score,
                teacher_id=user.id
            )
            db.session.add(assignment)
            db.session.flush()
            questions = request.form.getlist('question_text[]')
            for idx, q_text in enumerate(questions):
                question = Question(text=q_text, assignment_id=assignment.id)
                db.session.add(question)
                db.session.flush()
                options = request.form.getlist(f'answer_option_{idx+1}[]')
                correct_option = request.form.get(f'correct_option_{idx+1}')
                for opt_idx, opt_text in enumerate(options):
                    answer_option = AnswerOption(
                        text=opt_text,
                        is_correct=(str(opt_idx) == correct_option),
                        question_id=question.id
                    )
                    db.session.add(answer_option)
            db.session.commit()
            flash('Задание успешно создано', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании задания: {str(e)}', 'error')
    return render_template('create_assignment.html')

@main.route('/assignments/<int:assignment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assignment(assignment_id):
    user = User.query.get(session['user_id'])
    assignment = Assignment.query.get_or_404(assignment_id)
    if user.role != 'teacher' or assignment.teacher_id != user.id:
        abort(403)
    if request.method == 'POST':
        try:
            assignment.title = request.form['title']
            assignment.description = request.form['description']
            assignment.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%dT%H:%M') if request.form['deadline'] else None
            assignment.max_score = int(request.form['max_score'])
            db.session.commit()
            flash('Задание успешно обновлено', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении задания: {str(e)}', 'error')
    return render_template('edit_assignment.html', assignment=assignment)

@main.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    user = User.query.get(session['user_id'])
    assignment = Assignment.query.get_or_404(assignment_id)
    if user.role != 'teacher' or assignment.teacher_id != user.id:
        abort(403)
    try:
        db.session.delete(assignment)
        db.session.commit()
        flash('Задание успешно удалено', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении задания: {str(e)}', 'error')
    return redirect(url_for('main.dashboard'))

@main.route('/assignments/<int:assignment_id>/submissions')
@login_required
def view_submissions(assignment_id):
    user = User.query.get(session['user_id'])
    assignment = Assignment.query.get_or_404(assignment_id)
    if user.role != 'teacher' or assignment.teacher_id != user.id:
        abort(403)
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    # --- добавляем обработку для красивого вывода решений ---
    for submission in submissions:
        if submission.solution_text:
            answer_ids = [int(x) for x in submission.solution_text.replace(" ", "").split(",") if x.strip()]
            answer_options = AnswerOption.query.filter(AnswerOption.id.in_(answer_ids)).all()
            # Сохраняем порядок как в ответе
            answer_options_sorted = sorted(answer_options, key=lambda x: answer_ids.index(x.id))
            submission.answers_texts = [opt.text for opt in answer_options_sorted]
        else:
            submission.answers_texts = []
    # --------------------------------------------------------
    return render_template('view_submissions.html',
                         assignment=assignment,
                         submissions=submissions)

@main.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@login_required
def grade_submission(submission_id):
    user = User.query.get(session['user_id'])
    submission = Submission.query.get_or_404(submission_id)
    assignment = submission.assignment
    if user.role != 'teacher' or assignment.teacher_id != user.id:
        abort(403)
    try:
        submission.score = int(request.form['score']) if request.form['score'] else None
        submission.feedback = request.form['feedback']
        db.session.commit()
        flash('Оценка сохранена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при сохранении оценки: {str(e)}', 'error')
    return redirect(url_for('main.view_submissions', assignment_id=assignment.id))

@main.route('/submit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def submit_assignment(assignment_id):
    user = User.query.get(session['user_id'])
    if user.role != 'student':
        abort(403)
    assignment = Assignment.query.get_or_404(assignment_id)
    if request.method == 'POST':
        answers = []
        for question in assignment.questions:
            selected_option_id = request.form.get(f'question_{question.id}')
            if not selected_option_id:
                flash('Необходимо ответить на все вопросы.', 'error')
                return redirect(url_for('main.submit_assignment', assignment_id=assignment.id))
            answers.append(int(selected_option_id))
        submission = Submission(
            student_id=user.id,
            assignment_id=assignment.id,
            solution_text=", ".join(map(str, answers)),
            submitted_at=datetime.utcnow()
        )
        db.session.add(submission)
        db.session.commit()
        flash('Решение успешно отправлено', 'success')
        return redirect(url_for('main.student_dashboard'))
    return render_template(
        'submit_assignment.html',
        assignment=assignment,
        current_user=user
    )

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        try:
            user.name = request.form.get('name', user.name)
            user.last_name = request.form.get('last_name', user.last_name)
            user.email = request.form.get('email', user.email)
            if request.form.get('password'):
                if len(request.form.get('password')) < 6:
                    flash('Пароль должен содержать минимум 6 символов', 'error')
                else:
                    user.password = generate_password_hash(request.form.get('password'))
            db.session.commit()
            # <-- Вот здесь обновляем имя в сессии!
            session['username'] = user.name
            flash('Профиль успешно обновлен', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении профиля: {str(e)}', 'error')
        return redirect(url_for('main.profile'))
    return render_template('profile.html', user=user)

@main.route('/statistics')
@login_required
def statistics():
    user = User.query.get(session['user_id'])
    if user.role == 'teacher':
        students = user.students.all()
        assignments = Assignment.query.all()
        submissions = Submission.query.all()
        student_stats = []
        for student in students:
            student_subs = [s for s in submissions if s.student_id == student.id]
            scores = [s.score for s in student_subs if s.score is not None]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0
            total_assignments = len(assignments)
            completed = len([s for s in student_subs if s.solution_text and s.score is not None])
            not_completed = total_assignments - completed
            late = len([s for s in student_subs if s.submitted_at and any(a.id == s.assignment_id and a.deadline and s.submitted_at > a.deadline for a in assignments)])
            last_submission = max(student_subs, key=lambda x: x.submitted_at, default=None)
            last_score = last_submission.score if last_submission and last_submission.score is not None else '—'
            first_try = 0
            for a in assignments:
                subs_for_a = [s for s in student_subs if s.assignment_id == a.id]
                if len(subs_for_a) == 1 and subs_for_a[0].score is not None:
                    first_try += 1
            student_stats.append({
                'student': student,
                'avg_score': avg_score,
                'completed': completed,
                'not_completed': not_completed,
                'late': late,
                'last_score': last_score,
                'first_try': first_try,
            })
        avg_scores = [s['avg_score'] for s in student_stats]
        student_names = [s['student'].name for s in student_stats]
        scores_distribution = [s['last_score'] if isinstance(s['last_score'], (int, float)) else 0 for s in student_stats]
        from collections import Counter
        import datetime
        day_counts = Counter(
            s.submitted_at.date() for s in submissions if s.submitted_at is not None
        )
        heatmap_data = []
        if day_counts:
            date_from = min(day_counts)
            date_to = max(day_counts)
            curr = date_from
            while curr <= date_to:
                heatmap_data.append({
                    'date': curr.strftime('%Y-%m-%d'),
                    'count': day_counts.get(curr, 0)
                })
                curr += datetime.timedelta(days=1)
        return render_template(
            'statistics_teacher.html',
            student_stats=student_stats,
            student_names=student_names,
            avg_scores=avg_scores,
            scores_distribution=scores_distribution,
            heatmap_data=heatmap_data,
            assignments=assignments,
            submissions=submissions
        )
    elif user.role == 'student':
        assignments = Assignment.query.all()
        submissions = Submission.query.filter_by(student_id=user.id).all()
        scores = [s.score for s in submissions if s.score is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0
        total_assignments = len(assignments)
        completed = len([s for s in submissions if s.score is not None])
        not_completed = total_assignments - completed
        first_try = 0
        for a in assignments:
            subs_for_a = [s for s in submissions if s.assignment_id == a.id]
            if len(subs_for_a) == 1 and subs_for_a[0].score is not None:
                first_try += 1
        late = len([
            s for s in submissions if s.submitted_at and any(
                a.id == s.assignment_id and a.deadline and s.submitted_at > a.deadline for a in assignments
            )
        ])
        last_submission = max(submissions, key=lambda x: x.submitted_at, default=None)
        last_score = last_submission.score if last_submission and last_submission.score is not None else '—'
        assignment_titles = [a.title for a in assignments]
        assignment_scores = []
        for a in assignments:
            s = next((sub for sub in submissions if sub.assignment_id == a.id), None)
            assignment_scores.append(s.score if s and s.score is not None else 0)
        from collections import Counter
        import datetime
        day_counts = Counter(
            s.submitted_at.date() for s in submissions if s.submitted_at is not None
        )
        heatmap_data = []
        if day_counts:
            date_from = min(day_counts)
            date_to = max(day_counts)
            curr = date_from
            while curr <= date_to:
                heatmap_data.append({
                    'date': curr.strftime('%Y-%m-%d'),
                    'count': day_counts.get(curr, 0)
                })
                curr += datetime.timedelta(days=1)
        return render_template(
            'statistics_students.html',
            avg_score=avg_score,
            total_assignments=total_assignments,
            completed=completed,
            not_completed=not_completed,
            first_try=first_try,
            late=late,
            last_score=last_score,
            assignment_titles=assignment_titles,
            assignment_scores=assignment_scores,
            heatmap_data=heatmap_data
        )
    else:
        abort(403)

@main.route('/assignments')
@login_required
def assignments_list():
    user = User.query.get(session['user_id'])
    if user.role == 'teacher':
        assignments = Assignment.query.filter_by(teacher_id=user.id).order_by(Assignment.created_at.desc()).all()
        return render_template('assignments.html', assignments=assignments)
    elif user.role == 'student':
        assignments = Assignment.query.filter(
            Assignment.teacher_id.in_([t.id for t in user.teachers])
        ).order_by(Assignment.created_at.desc()).all()
        return render_template('student_assignments.html', assignments=assignments)
    else:
        abort(403)
