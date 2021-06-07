#!/usr/bin/env python
# pylint: disable=C0116
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few callback functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""
import datetime
import logging
from typing import Dict
import re
import os
import schedule
import time
from pytz import timezone
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove, ForceReply
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

from ptb_firebase_persistence import FirebasePersistence
# from config import URL, PORT, API_KEY
from dotenv import load_dotenv
from os import getenv
import json
import xlsxwriter

load_dotenv()  # take environment variables from .env.

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

CHOOSING, SETTING_THE_QUESTION, SETTING_TIME, DELETING_TASKS, SAYING_GOODBYE = range(5)

SET_TASK_TEXT = 'Добавить'
DOWNLOAD_ANSWERS_TEXT = 'Скачать ответы'
SHOW_MY_TASKS_TEXT = 'Мои вопросы'
SHOW_ALL_DATA = "Показать все"
DELETE_TASK = "Удалить вопрос"
GOODBYE = "На этом все"

reply_keyboard = [
    [SET_TASK_TEXT, SHOW_MY_TASKS_TEXT, DOWNLOAD_ANSWERS_TEXT, SHOW_ALL_DATA, DELETE_TASK, GOODBYE]
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
updater = None


def facts_to_str(user_data: Dict[str, str]) -> str:
    facts = []

    for key, value in user_data.items():
        facts.append(f'{key} - {value}')

    return "\n".join(facts).join(['\n', '\n'])


def start(update: Update, context: CallbackContext) -> int:
    reply_text = "Привет! Я помогу вам ничего не забыть."
    context.chat_data['started'] = True
    update.message.reply_text(reply_text, reply_markup=markup)
    return CHOOSING


def set_task_choice(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('О чем вас спрашивать?')
    return SETTING_THE_QUESTION


def received_information_text(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    context.user_data['text_for_upcoming_task'] = text
    update.message.reply_text(
        "Ок, буду спрашивать вас: "
        f"{text}"
        "\nКогда задавать вопрос? Напишите время в формате час:минута",
    )
    return SETTING_TIME


def received_information_time(update: Update, context: CallbackContext) -> int:
    task_time = update.message.text
    if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", task_time):
        update.message.reply_text(
            "Время введено в неправильном формате",
        )
        return SETTING_TIME
    task_text = context.user_data['text_for_upcoming_task']
    task = {
        "time": task_time,
        "task": task_text,
    }
    if 'tasks' not in context.user_data:
        context.user_data['tasks'] = []

    context.user_data['tasks'].append(task)

    update.message.reply_text(
        "Ок, я буду вас спрашивать: "
        f"{task_text} в {task_time}"
        "\nЯ могу сделать еще что-то для вас?",
        reply_markup=markup,
    )

    def callback_minute(ctx):
        context.user_data['question_for_upcoming_answer'] = task_text
        context.bot.send_message(update.effective_user.id, text=task_text, reply_markup=ForceReply())

    os.environ['TZ'] = 'Europe/Moscow'
    [hour, minute] = task_time.split(':')
    tz = timezone('Europe/Moscow')
    d = datetime.time(hour=int(hour), minute=int(minute), second=0, microsecond=0, tzinfo=tz)
    # updater.job_queue.run_once(callback_minute, when=5)
    # d = datetime.datetime.strptime(task_time, '%H:%M').time()
    print("Time")
    print(d)
    updater.job_queue.run_daily(callback_minute, time=d)
    # updater.dispatcher.add_handler(MessageHandler(task_time, callback_minute, pass_job_queue=True))

    del context.user_data['text_for_upcoming_task']

    return CHOOSING


def set_answer(update: Update, context: CallbackContext) -> int:
    # update.message.reply_text("Спасибо за ответ")
    question_text = context.user_data['question_for_upcoming_answer']
    answer_text = update.message.text
    del context.user_data['question_for_upcoming_answer']

    if 'answers' not in context.user_data:
        context.user_data['answers'] = []

    context.user_data['answers'].append({
        "date": datetime.datetime.now().replace(microsecond=0).isoformat(' '),
        "question": question_text,
        "answer": answer_text
    })
    update.message.reply_text(f"""
    Вы ответили
    {answer_text}  
    на вопрос
    {question_text}
    Отлично, до встречи!
    """, reply_markup=markup)

    return CHOOSING


def show_all_data(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(f"Вот что вы уже мне рассказали:")
    task_list = context.user_data['tasks']
    answer_list = context.user_data['answers']
    for i, val in enumerate(answer_list):
        update.message.reply_text(f"{i + 1}.{val['question']} - {val['answer']}, {val['date']}", reply_markup=markup)

    print(context.user_data)
    return CHOOSING


def show_tasks_only(update: Update, context: CallbackContext) -> None:
    task_list = context.user_data['tasks']
    update.message.reply_text("Вот вопросы, которые я вам задаю:")
    for i, val in enumerate(task_list):
        update.message.reply_text(f"{i + 1}. {val['task']}", reply_markup=markup)

    return CHOOSING


def offer_to_delete(update: Update, context: CallbackContext) -> None:
    task_list = context.user_data['tasks']
    update.message.reply_text("Выберите номер вопроса, который вы хотите удалить:")
    for i, val in enumerate(task_list):
        update.message.reply_text(f"{i + 1}. {val['task']} - {val['time']}", reply_markup=markup)
    return DELETING_TASKS


def delete_tasks(update: Update, context: CallbackContext) -> None:
    if not update.message.text.isnumeric():
        update.message.reply_text("Введите число (номер задачи)")
        return DELETING_TASKS
    idx = int(update.message.text) - 1
    if idx >= len(context.user_data['tasks']) or idx < 0:
        update.message.reply_text("Упс, такого номера в списке нет", reply_markup=markup)
        return DELETING_TASKS

    del context.user_data['tasks'][idx]
    update.message.reply_text("Удалил")
    update.message.reply_text("Что-то еще?", reply_markup=markup)

    return CHOOSING


def done(update: Update, context: CallbackContext) -> int:
    # if 'choice' in context.user_data:
    #     del context.user_data['choice']
    update.message.reply_text(
        # "Вот что я о вас узнал:" f"{facts_to_str(context.user_data)} До следующей встречи!",
        "До следующей встречи!",
        reply_markup=markup)
    return CHOOSING


with open(getenv('FIREBASE_CREDENTIALS_FILE')) as json_file:
    credentials = json.load(json_file)


def download_answers(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    fname = f'results_{user_id}.xlsx'
    workbook = xlsxwriter.Workbook(fname)
    worksheet = workbook.add_worksheet()

    bold = workbook.add_format({'bold': True})
    worksheet.write('A1', 'Дата и время ответа', bold)
    worksheet.write('B1', 'Вопрос', bold)
    # worksheet.write('C1', 'Время задавания вопроса', bold)
    worksheet.write('C1', 'Ответ', bold)

    for idx, task in enumerate(context.user_data['answers']):
        row_index = idx + 1
        if 'date' in task:
            worksheet.write(f'A{row_index + 1}', task['date'])
        if 'question' in task:
            worksheet.write(f'B{row_index + 1}', task['question'])
        if 'answer' in task:
            worksheet.write(f'C{row_index + 1}', task['answer'])
    workbook.close()

    with open(fname, 'rb') as file:
        context.bot.sendDocument(user_id, document=file, reply_markup=markup)
    os.remove(fname)
    print(task)
    return CHOOSING


def main() -> None:
    global updater
    # Create the Updater and pass it your bot's token.
    persistence = FirebasePersistence(database_url=getenv('FIREBASE_URL'), credentials=credentials)
    updater = Updater(getenv('TELEGRAM_TOKEN'), persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                MessageHandler(Filters.regex(f'^{SET_TASK_TEXT}$'), set_task_choice),
                MessageHandler(Filters.reply, set_answer),
                MessageHandler(Filters.regex(f'^{SHOW_ALL_DATA}$'), show_all_data),
                MessageHandler(Filters.regex(f'^{SHOW_MY_TASKS_TEXT}$'), show_tasks_only),
                MessageHandler(Filters.regex(f'^{DOWNLOAD_ANSWERS_TEXT}$'), download_answers),
                MessageHandler(Filters.regex(f'^{DELETE_TASK}$'), offer_to_delete),
                MessageHandler(Filters.regex(f'^{GOODBYE}$'), done),
            ],
            SETTING_THE_QUESTION: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Done$')),
                    received_information_text,
                )
            ],
            DELETING_TASKS: [
                MessageHandler(Filters.text, delete_tasks)
            ],
            SETTING_TIME: [
                MessageHandler(Filters.text,
                               received_information_time,
                               )
            ],
            # ANSWERING: [
            #     MessageHandler(Filters.text,
            #                    set_answer,
            #                    )
            # ],
            SAYING_GOODBYE: [
                MessageHandler(Filters.text, done)
            ]
        },
        fallbacks=[MessageHandler(Filters.regex('^Done$'), done)],
        name="my_conversation",
        persistent=True,
    )

    dispatcher.add_handler(conv_handler)

    show_all_data_handler = CommandHandler('show_all_data', show_all_data)
    dispatcher.add_handler(show_all_data_handler)


    # Start the Bot
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

