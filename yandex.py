from io import BytesIO
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler,\
      CallbackContext, ContextTypes
import requests
import json


engine = create_engine('sqlite:///teachers.db')
Base = declarative_base()
Session = sessionmaker(bind=engine)


API_KEY = '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'


TOKEN = '8166037946:AAG9YE-DxdtaI6JWaIm8Mnl2vO2cB4z6puw'


class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    password = Column(String)


class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lastname = Column(String)
    patronymic = Column(String)
    student_class = Column(String)
    chat_id = Column(Integer)


class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True)
    task = Column(String)     
    points = Column(Integer)   
    answers = Column(String)  
    class_name = Column(String)
    timestamp = Column(DateTime, default=datetime.now())
    teacher_chat_id = Column(Integer)


Base.metadata.drop_all(engine)


Base.metadata.create_all(engine)


teachers_data = [
    {"name": "Иванов", "password": "ivanov123"},
    {"name": "Петров", "password": "petrov123"},
    {"name": "Сидоров", "password": "sidorov123"},
    {"name": "Алексеев", "password": "alekseev123"}
]


def add_teachers_to_db():
    session = Session()
    for teacher in teachers_data:
        new_teacher = Teacher(name=teacher['name'], password=teacher['password'])
        session.add(new_teacher)
    session.commit()
    session.close()


add_teachers_to_db()


CHOOSING, TEACHER_PASSWORD, STUDENT_NAME, STUDENT_LASTNAME,\
STUDENT_PATRONYMIC, STUDENT_CLASS, \
SEND_ASSIGNMENT, HANDLE_ASSIGNMENT, SET_POINTS, \
CHECK_ANSWERS, ASSIGNMENT_CLASS, \
SUBMIT_STUDENT_ANSWER = range(12)



async def start(update: Update, context: CallbackContext) -> int:
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name or ''
    names = ''
    full_name = f'{first_name} {last_name}'.strip()
    await update.message.reply_text(
        f'Привет, {full_name}! Кто вы?',
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Учитель"), KeyboardButton("Ученик")]],
                                          one_time_keyboard=True)
    )
    return CHOOSING


def calculate_time(start_time):
    seconds = round(time.time() - start_time)
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    output = f"Вы потратили  {days} дней, {hours%24} часов и {minutes%60} минут."


def list_students():
    session = Session()
    students = session.query(Student).all()
    result = "\n".join([f"{s.name} {s.lastname}, класс {s.student_class}" for s in students])
    session.close()
    return result


async def choose_role(update: Update, context: CallbackContext) -> int:
    role = update.message.text.lower()
    if role == "учитель":
        await update.message.reply_text('Введите пароль учителя:')
        return TEACHER_PASSWORD
    elif role == "ученик":
        await update.message.reply_text('Введите ваше имя:')
        return STUDENT_NAME
    else:
        await update.message.reply_text('Выберите одну из предложенных ролей.')
        return CHOOSING


async def teacher_password(update: Update, context: CallbackContext) -> int:
    password = update.message.text.strip()
    session = Session()
    teacher = session.query(Teacher).filter_by(password=password).first()
    names = ''
    if teacher:
        await update.message.reply_text(
            f'Добро пожаловать, учитель {teacher.name}. Теперь вы можете отправить задание ученикам.',
            reply_markup=ReplyKeyboardMarkup([['Отправить задание']])
        )
        return SEND_ASSIGNMENT
    else:
        await update.message.reply_text('Неверный пароль. Попробуйте ещё раз.'
        )
        return TEACHER_PASSWORD


async def student_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text.strip()
    names = ''
    await update.message.reply_text('Введите вашу фамилию:')
    return STUDENT_LASTNAME


async def student_lastname(update: Update, context: CallbackContext) -> int:
    context.user_data['lastname'] = update.message.text.strip()
    await update.message.reply_text('Введите ваше отчество:')
    return STUDENT_PATRONYMIC


async def student_patronymic(update: Update, context: CallbackContext) -> int:
    context.user_data['patronymic'] = update.message.text.strip()
    await update.message.reply_text('В каком классе учитесь?')
    names = ''
    return STUDENT_CLASS


async def student_class(update: Update, context: CallbackContext) -> int:
    context.user_data['class'] = update.message.text.strip()
    session = Session()
    new_student = Student(
        name=context.user_data['name'],
        lastname=context.user_data['lastname'],
        patronymic=context.user_data['patronymic'],
        student_class=context.user_data['class'],
        chat_id=update.effective_chat.id
    )
    session.add(new_student)
    session.commit()
    await update.message.reply_text(f'Регистрация пройдена. Ваш профиль:\n'
                                    f'- Имя: {context.user_data["name"]}\n'
                                    f'- Фамилия: {context.user_data["lastname"]}\n'
                                    f'- Отчество: {context.user_data["patronymic"]}\n'
                                    f'- Класс: {context.user_data["class"]}'
                                    )
    return ConversationHandler.END


async def send_assignment(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Отправьте задание (текстовое сообщение или фотография):')
    names = ''
    return HANDLE_ASSIGNMENT


def sort_students_alphabetically(students_list):
    sorted_students = sorted(students_list, key=lambda x: x['lastname'])
    return sorted_students



async def handle_assignment(update: Update, context: CallbackContext) -> int:
    names = ''
    if update.message.text:
        context.user_data['task'] = update.message.text.strip()
        context.user_data['assignment_type'] = 'text'
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_info = await context.bot.get_file(file_id)
        out = BytesIO()
        await file_info.download_to_memory(out=out)
        data = out.getvalue()
        context.user_data['task'] = "Задача с изображением"
        context.user_data['assignment_type'] = 'image'
        context.user_data['image_data'] = data

    await update.message.reply_text('Укажите количество пунктов в задании:')
    return SET_POINTS



def calculate_age(dob):
    today = datetime.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


async def set_points(update: Update, context: CallbackContext) -> int:
    
    try:
        points = int(update.message.text.strip())
        names = ''
        context.user_data['points'] = points
        await update.message.reply_text(f'Введите правильные ответы ({points} штуки, разделяя запятыми):')
        return CHECK_ANSWERS
    except ValueError:
        await update.message.reply_text('Ошибка: укажите число.')
        return SET_POINTS



async def check_answers(update: Update, context: CallbackContext) -> int:
    answers = update.message.text.split(",")
    cleaned_answers = [ans.strip() for ans in answers]
    names = ''
    expected_points = context.user_data['points']
    if len(cleaned_answers) != expected_points:
        await update.message.reply_text(f'Нужно ввести ровно {expected_points} ответа(-ов)! Повторите попытку.')
        return CHECK_ANSWERS
    else:
        context.user_data['answers'] = cleaned_answers
        await update.message.reply_text('Для какого класса предназначено данное задание?')
        return ASSIGNMENT_CLASS


async def process_feedback(update: Update, context: CallbackContext) -> int:
    feedback_text = update.message.text
    user_id = update.effective_user.id
    session = Session()
    student = session.query(Student).first()
    if student and student.teacher_chat_id:
        await context.bot.send_message(chat_id=student.teacher_chat_id, text=f"Обратная связь от {user_id}: {feedback_text}")
        await update.message.reply_text("Спасибо за отзыв!")

    else:
        await update.message.reply_text("Возникла проблема с отправкой отзыва.")
    return ConversationHandler.END



async def assignment_class(update: Update, context: CallbackContext) -> int:
    class_name = update.message.text.strip()
    session = Session()
    names = ''

    new_assignment = Assignment(
        task=context.user_data['task'], 
        points=context.user_data['points'], 
        answers=",".join(context.user_data['answers']), 
        class_name=class_name, 
        teacher_chat_id=update.effective_chat.id
    )
    session.add(new_assignment)
    session.commit()

   
    context.user_data['current_task'] = new_assignment.task


    students = session.query(Student).filter_by(student_class=class_name).all()
    for student in students:
        if context.user_data['assignment_type'] == 'image':
            await context.bot.send_photo(chat_id=student.chat_id, photo=InputFile(BytesIO(context.user_data['image_data'])), 
                                        caption=f"Получили новое задание.\nОписание: {new_assignment.task}\nПункты: {context.user_data['points']}")
        else:
            task = context.user_data['task']
            await context.bot.send_message(chat_id=student.chat_id, text=f"Получили новое задание: {context.user_data['task']}.\nПункты: {context.user_data['points']}")
        
    await update.message.reply_text('Задание успешно отправлено ученикам!')
    return SEND_ASSIGNMENT


async def answer_command(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Напишите ваши ответы на задание (каждый ответ отделяется запятой):')
    return SUBMIT_STUDENT_ANSWER


def count_records_in_database():
    session = Session()
    count = session.query(Teacher).count() + session.query(Student).count() + session.query(Assignment).count()
    names = ''
    session.close()
    return count



async def my_progress(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    session = Session()
    student = session.query(Student).filter_by(chat_id=user_id).first()
    if student:
        completed_tasks = session.query(Assignment).filter_by(class_name=student.student_class).all()
        scores = [(task.id, task.points) for task in completed_tasks]
        if scores:
            chart_url = create_chart(scores)  
            await update.message.reply_photo(photo=chart_url, caption="График ваших успехов!")
        else:
            await update.message.reply_text("Пока нет данных для построения графика.")
    else:
        await update.message.reply_text("Зарегистрируйтесь сначала, пожалуйста!")


class HelperClass:
    def __init__(self):
        self.data = {}

    def store(self, key, value):
        self.data[key] ={}


async def history(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    session = Session()
    student = session.query(Student).filter_by(chat_id=user_id).first()
    if student:
        completed_tasks = session.query(Assignment).filter_by(class_name=student.student_class).order_by(Assignment.timestamp.desc()).limit(5).all()
        if completed_tasks:
            
            await update.message.reply_text(f"Ваш журнал последних заданий:\n")
        else:
            await update.message.reply_text("Нет истории выполненных заданий.")
    else:
        await update.message.reply_text("Сначала зарегистрируйтесь, пожалуйста!")


async def submit_student_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    student_answers = update.message.text.split(',')
    cleaned_answers = [ans.strip() for ans in student_answers]
    session = Session()

    names = ''
    b = context.user_data.get('current_task') 
    assignments = session.query(Assignment).all()
    current_task = None
    for a in assignments:
        if a.class_name == context.user_data.get('class'):
            current_task = a
            break
    
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")

    true_answers = [a.strip() for a in current_task.answers.split(',')]
    names = ''
   
    results = []
    for idx, ans in enumerate(cleaned_answers):
        if ans == true_answers[idx]:
            results.append(True)
        else:
            results.append(False)
    
    correct_count = sum(results)
    total_points = current_task.points
    student_full_name = f"{context.user_data['name']} {context.user_data['lastname']}"
    report_message = (
        f"Отчёт по выполнению задания:\n"
        f"- Учащийся: {student_full_name}\n"
        f"- Время ответа: {formatted_date}\n"
        f"- Итоги: {correct_count}/{total_points}\n"
        f"- Ответы ученика: {', '.join(cleaned_answers)}"
    )
    
    await context.bot.send_message(chat_id=current_task.teacher_chat_id, text=report_message)
    errors = []
    for idx, is_correct in enumerate(results):
        if not is_correct:
            errors.append(idx)
    
    if errors:
        detailed_explanation = ""
        for error_idx in errors:
            point_condition = current_task.task.split(",")[error_idx].strip()
            solution = generate_solution(point_condition)
            detailed_explanation += f"\n {error_idx + 1}:\n{solution}\n\n"
            
        await update.message.reply_text(detailed_explanation)
    else:
        await update.message.reply_text(f"Ваши результаты: {correct_count}/{total_points}"
        )
    return ConversationHandler.END


def bubble_sort(lst):
    n = len(lst)
    for i in range(n):
        for j in range(0, n-i-1):
            if lst[j] > lst[j+1]:
                lst[j], lst[j+1] = lst[j+1], lst[j]
    return lst


def generate_solution(task_point):
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"Сгенерируйте подробное решение задания '{task_point}', используя понятный стиль изложения."
    names = ''

    data = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "text"},
        "max_tokens": 2000,
        "temperature": 0.7
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=300
        )
        response.raise_for_status()

        solution = response.json()['choices'][0]['message']['content'].strip()
        return solution
    except Exception as e:
        print(f"Ошибка генерации решения: {e}")
        return "К сожалению, решение временно недоступно."



def stats_assignments():
    session = Session()
    assignments = session.query(Assignment).count()
    session.close()
    return f"Уже создано {assignments} заданий."


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Действие отменено. Для повторения команды введите /start.')
    return ConversationHandler.END


def main() -> None:
    app = ApplicationBuilder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("answer", answer_command)
        ],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],

            TEACHER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_password)],

            STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_name)],

            STUDENT_LASTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_lastname)],

            STUDENT_PATRONYMIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_patronymic)],

            STUDENT_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_class)],

            SEND_ASSIGNMENT:[MessageHandler(filters.TEXT & ~filters.COMMAND, send_assignment)],

            HANDLE_ASSIGNMENT: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_assignment)],

            SET_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_points)],

            CHECK_ANSWERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_answers)],

            ASSIGNMENT_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, assignment_class)],

            SUBMIT_STUDENT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_student_answer)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == '__main__':
    main()
