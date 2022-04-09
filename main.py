# -*- coding: utf-8 -*-
import os
import time
import re
import json
import telebot
import schedule
import gitlab
from threading import Thread

TOKEN = os.getenv('BOT_TOKEN')
G_TOKEN = os.getenv('GITLAB_PAT')
CHANNEL_ID = '@letovo_quotes'
MOD_ID = -1001791070494
BAN_TIME = 3600

bot = telebot.TeleBot(TOKEN)
gl = gitlab.Gitlab('https://gitlab.com', private_token=G_TOKEN)
project = gl.projects.get(35046550)
sent_quotes = {}
call_cnt = 0

_banlist = open('banlist.json', 'wb')
try:
    project.files.raw(file_path='banlist.json', ref='main', streamed=True, action=_banlist.write)
except gitlab.exceptions.GitlabGetError:
    pass
_banlist.close()

_queue = open('queue.json', 'wb')
try:
    project.files.raw(file_path='queue.json', ref='main', streamed=True, action=_queue.write)
except gitlab.exceptions.GitlabGetError:
    pass
_queue.close()


def format_time(value):
    return time.strftime("%H:%M:%S", time.gmtime(value))


def push_gitlab(filename):
    f = open(filename, 'r', encoding='utf-8')
    data = f.read()
    action = 'create'
    for i in project.repository_tree():
        if i['name'] == filename:
            action = 'update'
            break
    payload = {
        'branch': 'main',
        'commit_message': 'Update',
        'actions': [
            {
                'action': action,
                'file_path': filename,
                'content': data,
            }
        ]
    }
    project.commits.create(payload)
    f.close()


def publish_quote():
    try:
        with open('queue.json', 'r', encoding='utf-8') as file:
            queue = dict(json.load(file))
    except json.decoder.JSONDecodeError:
        queue = dict()

    if queue == dict():
        bot.send_message(MOD_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue.keys()) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue.keys()) - 1))

    with open('queue.json', 'w', encoding='utf-8') as file:
        json.dump(queue, file, ensure_ascii=False)

    push_gitlab('queue.json')


@bot.message_handler(commands=['start'])
def hello(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')


@bot.message_handler(commands=['suggest'])
def suggest(message):
    global sent_quotes, call_cnt
    quote = message.text[9:]
    author = message.from_user.username
    author_id = str(message.from_user.id)
    if author is None:
        author = message.from_user.first_name + ' ' + message.from_user.last_name
    if quote:
        try:
            with open('banlist.json', 'r', encoding='utf-8') as file:
                banlist = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            banlist = dict()
        if author_id not in banlist.keys() or int(time.time()) > banlist[author_id] + BAN_TIME:
            if author_id in banlist.keys():
                banlist.pop(author_id)

            with open('banlist.json', 'w', encoding='utf-8') as file:
                json.dump(banlist, file, ensure_ascii=False)

            push_gitlab('banlist.json')
            bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton(text='🔔 Опубликовать', callback_data=f'publish: {call_cnt}'))
            sent_quotes.update({call_cnt: quote})
            call_cnt += 1
            keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отменить', callback_data='reject'))
            bot.send_message(MOD_ID,
                             f'Пользователь @{author} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             f'Вы были заблокированы, поэтому не можете предлагать цитаты. Оставшееся время блокировки: {format_time(BAN_TIME - int(time.time()) + banlist[str(author_id)])}')
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest и ждать публикации. '
                         'И, пожалуйста, не пиши ерунду!')


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.chat.id == MOD_ID:
        try:
            message = int(message.text[4:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        try:
            with open('banlist.json', 'r', encoding='utf-8') as file:
                banlist = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            banlist = dict()

        message = str(message).replace(' ', '')
        banlist.update({message: int(time.time())})

        with open('banlist.json', 'w', encoding='utf-8') as file:
            json.dump(banlist, file, ensure_ascii=False)

        push_gitlab('banlist.json')
        bot.send_message(MOD_ID, f'Пользователь {message} успешно заблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['unban'])
def unban(message):
    if message.chat.id == MOD_ID:
        try:
            message = int(message.text[6:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        try:
            with open('banlist.json', 'r', encoding='utf-8') as file:
                banlist = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            banlist = dict()

        message = str(message).replace(' ', '')
        if message not in banlist.keys():
            bot.send_message(MOD_ID, f'Пользователь {message} не заблокирован!')
        else:
            banlist.pop(message)

        with open('banlist.json', 'w', encoding='utf-8') as file:
            json.dump(banlist, file, ensure_ascii=False)

        push_gitlab('banlist.json')
        bot.send_message(MOD_ID, f'Пользователь {message} успешно разблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['queue'])
def add_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 6:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return
        try:
            with open('queue.json', 'r', encoding='utf-8') as file:
                quotes = json.load(file)
        except json.decoder.JSONDecodeError:
            quotes = dict()
        next_num = len(quotes.keys())
        message = message.text[7:]
        quotes.update({str(next_num): message})

        with open('queue.json', 'w', encoding='utf-8') as file:
            json.dump(quotes, file, ensure_ascii=False)

        push_gitlab('queue.json')
        bot.send_message(MOD_ID, 'Успешно занес цитату в очередь публикации!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_queue'])
def get_queue(message):
    if message.chat.id == MOD_ID:
        try:
            with open('queue.json', 'r', encoding='utf-8') as file:
                queue = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            queue = dict()
        for num, quote in queue.items():
            bot.send_message(MOD_ID, f'#*{num}*\n{quote}', parse_mode='Markdown')
        if queue == dict():
            bot.send_message(MOD_ID, 'Очередь публикации пуста!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_banlist'])
def get_banlist(message):
    if message.chat.id == MOD_ID:
        try:
            with open('banlist.json', 'r', encoding='utf-8') as file:
                banlist = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            banlist = dict()

        a = []
        for key, value in banlist.items():
            a.append(key + ': ' + format_time(int(value)) + ' -> ' + format_time(int(value) + BAN_TIME) + '\n')
        if not banlist.keys():
            bot.send_message(MOD_ID, 'Список заблокированных пользователей пуст!')
        else:
            bot.send_message(MOD_ID, 'ID пользователя: время блокировки -> время разблокировки')
            bot.send_message(MOD_ID, ''.join(a))
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['del_queue'])
def del_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 10:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        try:
            num = int(message.text[10:])
        except ValueError:
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        num = str(num)

        try:
            with open('queue.json', 'r', encoding='utf-8') as file:
                queue = dict(json.load(file))
        except json.decoder.JSONDecodeError:
            queue = dict()

        for key in range(int(num), len(queue.keys()) - 1):
            queue[str(key)] = queue[str(int(key) + 1)]
        queue.pop(str(len(queue.keys()) - 1))

        with open('queue.json', 'w', encoding='utf-8') as file:
            json.dump(queue, file, ensure_ascii=False)

        push_gitlab('queue.json')

        bot.send_message(MOD_ID, f'Успешно удалил цитату с номером {num}!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['clear_queue'])
def clear_queue(message):
    if message.chat.id == MOD_ID:
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton(text='➕ Да', callback_data=f'clear: yes'))
        keyboard.add(
            telebot.types.InlineKeyboardButton(text='➖ Нет', callback_data=f'clear: no'))
        bot.send_message(MOD_ID, 'Вы уверены в том, что хотите очистить очередь публикаций?', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    if not re.match(r'publish', call.data) is None:
        try:
            with open('queue.json', 'r', encoding='utf-8') as file:
                quotes = json.load(file)
        except json.decoder.JSONDecodeError:
            quotes = dict()

        message = sent_quotes[int(call.data[9:])]
        next_num = len(quotes.keys()) + 1
        quotes.update({str(next_num): message})

        with open('queue.json', 'w', encoding='utf-8') as file:
            json.dump(quotes, file, ensure_ascii=False)

        push_gitlab('queue.json')

        bot.edit_message_text(f'{call.message.text}\n\nОпубликовано модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'reject':
        bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
    elif call.data == 'clear: yes':
        queue = dict()
        with open('queue.json', 'w', encoding='utf-8') as file:
            json.dump(queue, file, ensure_ascii=False)

        bot.edit_message_text('Успешно очистил очередь публикаций!', MOD_ID,
                              call.message.id, reply_markup=None)
        push_gitlab('queue.json')
    elif call.data == 'clear: no':
        bot.edit_message_text('Запрос на очистку очереди публикаций отклонен.', MOD_ID,
                              call.message.id, reply_markup=None)
    bot.answer_callback_query(call.id)


Thread(target=bot.polling, args=()).start()
schedule.every().day.at('09:00').do(publish_quote)
schedule.every().day.at('15:00').do(publish_quote)

while True:
    schedule.run_pending()
    time.sleep(1)
