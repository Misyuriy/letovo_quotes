import time
from threading import Thread
import schedule
import telebot
from backend import *

TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = '@letovo_quotes'
MOD_ID = -1001791070494
BAN_TIME = 3600

bot = telebot.TeleBot(TOKEN)
pending = {}
pinned_pending = {}
call_count = 0

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


def publish_quote():
    queue = open_json('queue.json')

    if queue == dict():
        bot.send_message(MOD_ID, text='Цитаты в очереди закончились! :(')
        return

    bot.send_message(CHANNEL_ID, text=queue['0'])

    for key in range(len(queue.keys()) - 1):
        queue[str(key)] = queue[str(int(key) + 1)]
    queue.pop(str(len(queue.keys()) - 1))

    save_json(queue, 'queue.json')
    push_gitlab('queue.json')


@bot.message_handler(commands=['start'])
def hello(message):
    bot.send_message(message.chat.id,
                     'Привет! Сюда ты можешь предлагать цитаты для публикации в канале "Забавные цитаты Летово". Если ты вдруг еще не подписан - держи ссылку: '
                     'https://t.me/letovo_quotes. Никаких ограничений - предлагай все, что покажется тебе смешным (с помощью команды /suggest), главное, укажи автора цитаты :)')


@bot.message_handler(commands=['suggest'])
def suggest(message):
    global pending, call_count
    quote = reformat_quote(message.text[9:])
    author = message.from_user.username
    author_id = str(message.from_user.id)
    if author is None:
        author = message.from_user.first_name + ' ' + message.from_user.last_name
    if quote:
        for i in pending.values():
            if check_similarity(i, quote) > 75:
                bot.send_message(message.chat.id,
                                 'Подобная цитата уже отправлена в предложку! Флудить не стоит, ожидай решения модерации :)')
                return

        banlist = open_json('banlist.json')
        if author_id in banlist.keys() and int(time.time()) > banlist[author_id]:
            banlist.pop(author_id)
            save_json(banlist, 'banlist.json')
            push_gitlab('banlist.json')
        if author_id not in banlist.keys():
            bot.send_message(message.chat.id, 'Принято! Отправил твою цитату в предложку :)')
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton(text='🔔 Опубликовать', callback_data=f'publish: {call_count}'))
            pending.update({call_count: quote})

            keyboard.add(telebot.types.InlineKeyboardButton(text='🚫 Отменить', callback_data=f'reject: {call_count}'))
            sent_quote = bot.send_message(MOD_ID,
                                          f'Пользователь @{author} [ID: {author_id}] предложил следующую цитату:\n\n{quote}',
                                          reply_markup=keyboard)
            bot.pin_chat_message(MOD_ID, sent_quote.message_id)
            pinned_pending[call_count] = sent_quote
            call_count += 1
        else:
            bot.send_message(message.chat.id,
                             f'Вы были заблокированы, поэтому не можете предлагать цитаты. Оставшееся время блокировки: {format_time(banlist[author_id] - int(time.time()))}')
    else:
        bot.send_message(message.chat.id,
                         'Эта команда используется для отправки цитат в предложку. Все, что тебе нужно сделать - ввести текст после команды /suggest и ждать публикации. '
                         'И, пожалуйста, не пиши ерунду!')


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.chat.id == MOD_ID:
        args = message.text[5:].split(' ')
        if len(args) == 2:
            user_id, period = args
        else:
            user_id = args[0]
            period = BAN_TIME

        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        banlist = open_json('banlist.json')

        banlist.update({user_id: int(time.time()) + int(period)})

        save_json(banlist, 'banlist.json')
        push_gitlab('banlist.json')
        bot.send_message(MOD_ID, f'Пользователь {user_id} успешно заблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['unban'])
def unban(message):
    if message.chat.id == MOD_ID:
        user_id = message.text[6:].replace(' ', '')
        if not user_id.isdigit():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        banlist = open_json('banlist.json')

        if user_id not in banlist.keys():
            bot.send_message(MOD_ID, f'Пользователь {user_id} не заблокирован!')
        else:
            banlist.pop(user_id)

        save_json(banlist, 'banlist.json')
        push_gitlab('banlist.json')
        bot.send_message(MOD_ID, f'Пользователь {user_id} успешно разблокирован!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['queue'])
def add_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 6:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return
        queue = open_json('queue.json')

        next_quote_id = len(queue.keys())
        quote = message.text[7:]
        queue.update({str(next_quote_id): quote})

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')
        bot.send_message(MOD_ID, 'Успешно занес цитату в очередь публикации!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_queue'])
def get_queue(message):
    if message.chat.id == MOD_ID:
        queue = open_json('queue.json')
        for quote_id, quote in queue.items():
            bot.send_message(MOD_ID, f'#*{quote_id}*\n{quote}', parse_mode='Markdown')
        if queue == dict():
            bot.send_message(MOD_ID, 'Очередь публикации пуста!')
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['get_banlist'])
def get_banlist(message):
    if message.chat.id == MOD_ID:
        banlist = open_json('banlist.json')

        if banlist == dict():
            bot.send_message(MOD_ID, 'Список заблокированных пользователей пуст!')
            return

        bot.send_message(MOD_ID, 'ID пользователя: время разблокировки')
        for key, value in banlist.items():
            bot.send_message(MOD_ID, key + ': ' + format_time(int(value)))
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.message_handler(commands=['del_queue'])
def del_queue(message):
    if message.chat.id == MOD_ID:
        if len(message.text) == 10:
            bot.send_message(message.chat.id, 'Эта команда должна содержать какой-то параметр!')
            return

        queue = open_json('queue.json')

        quote_id = message.text[10:].replace(' ', '')
        if quote_id not in queue.keys():
            bot.send_message(message.chat.id, 'Введи корректное значение идентификатора!')
            return

        for key in range(int(quote_id), len(queue.keys()) - 1):
            queue[str(key)] = queue[str(int(key) + 1)]
        queue.pop(str(len(queue.keys()) - 1))

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')

        bot.send_message(MOD_ID, f'Успешно удалил цитату с номером {quote_id}!')
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


@bot.message_handler(commands=['edit_quote'])
def edit_quote(message):
    if message.chat.id == MOD_ID:
        args = message.text[12:].split('; ')
        if len(args) == 2:
            quote_id, new_text = args
            if not quote_id.isdigit():
                bot.send_message(MOD_ID, 'Введи корректное значение идентификатора!')
                return

            queue = open_json('queue.json')
            if quote_id in queue.keys():
                queue[quote_id] = new_text
            else:
                bot.send_message(MOD_ID, 'Цитаты с таким номером не существует!')
                return
            bot.send_message(MOD_ID, f'Успешно изменил цитату под номером {quote_id}!')
            save_json(queue, 'queue.json')
            push_gitlab('queue.json')

        else:
            bot.send_message(MOD_ID, 'Проверь корректность аргументов!')
            return
    else:
        bot.send_message(message.chat.id, 'У вас нет доступа к этой функции.')


@bot.callback_query_handler(func=lambda call: True)
def button_handler(call):
    actual_quote_id = 0
    if call.data[:7] == 'publish':
        queue = open_json('queue.json')
        actual_quote_id = int(call.data[9:])
        quote = pending[actual_quote_id]
        next_quote_id = len(queue.keys())
        queue.update({str(next_quote_id): quote})

        save_json(queue, 'queue.json')
        push_gitlab('queue.json')

        bot.edit_message_text(f'{call.message.text}\n\nОпубликовано модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
        pending.pop(actual_quote_id)
    elif call.data[:6] == 'reject':
        actual_quote_id = int(call.data[8:])
        bot.edit_message_text(f'{call.message.text}\n\nОтклонено модератором @{call.from_user.username}', MOD_ID,
                              call.message.id, reply_markup=None)
        pending.pop(actual_quote_id)
    elif call.data == 'clear: yes':
        save_json(dict(), 'queue.json')

        bot.edit_message_text('Успешно очистил очередь публикаций!', MOD_ID,
                              call.message.id, reply_markup=None)
        push_gitlab('queue.json')
    elif call.data == 'clear: no':
        bot.edit_message_text('Запрос на очистку очереди публикаций отклонен.', MOD_ID,
                              call.message.id, reply_markup=None)
    bot.answer_callback_query(call.id)
    try:
        bot.unpin_chat_message(MOD_ID, pinned_pending[actual_quote_id].message_id)
    except KeyError:
        bot.send_message(MOD_ID, 'Возникла проблема с обработкой цитаты :( Если это необходимо, проведи ее вручную.')


Thread(target=bot.polling, args=()).start()
schedule.every().day.at('09:00').do(publish_quote)
schedule.every().day.at('15:00').do(publish_quote)

while True:
    schedule.run_pending()
    time.sleep(1)
