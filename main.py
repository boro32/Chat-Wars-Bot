# coding=utf-8
from pytg.sender import Sender
from pytg.receiver import Receiver
from pytg.utils import coroutine
from collections import deque
from time import time, sleep
from getopt import getopt
import sys
import datetime
import re
import _thread
import random

# username игрового бота
bot_username = 'ChatWarsBot'

# ваш username или username человека, который может отправлять запросы этому скрипту
admin_username = ''

# username бота и/или человека, которые будут отправлять приказы
order_usernames = ''

# имя замка
castle_name = 'blue'

captcha_bot = 'ChatWarsCaptchaBot'

# путь к сокет файлу
socket_path = ''

# хост чтоб слушать telegram-cli
host = 'localhost'

# порт по которому слушать
port = 1338

opts, args = getopt(sys.argv[1:], 'a:o:c:s:h:p', ['admin=', 'order=', 'castle=', 'socket=', 'host=', 'port='])

for opt, arg in opts:
    if opt in ('-a', '--admin'):
        admin_username = arg
    elif opt in ('-o', '--order'):
        order_usernames = arg.split(',')
    elif opt in ('-c', '--castle'):
        castle_name = arg
    elif opt in ('-s', '--socket'):
        socket_path = arg
    elif opt in ('-h', '--host'):
        host = arg
    elif opt in ('-p', '--port'):
        port = int(arg)

orders = {
    'red': '🇮🇲',
    'black': '🇬🇵',
    'white': '🇨🇾',
    'yellow': '🇻🇦',
    'blue': '🇪🇺',
    'lesnoi_fort': '🌲Лесной форт',
    'les': '🌲Лес',
    'gorni_fort': '⛰Горный форт',
    'gora': '⛰',
    'cover': '🛡 Защита',
    'attack': '⚔ Атака',
    'cover_symbol': '🛡',
    'hero': '🏅Герой',
    'corovan': '/go',
    'peshera': '🕸Пещера'
}

captcha_answers = {
    # блядь, кольцов, ну и хуйню же ты придумал
    'watermelon_n_cherry': '🍉🍒',
    'bread_n_cheese': '🍞🧀',
    'cheese': '🧀',
    'pizza': '🍕',
    'hotdog': '🌭',
    'eggplant_n_carrot': '🍆🥕',
    'dog': '🐕',
    'horse': '🐎',
    'goat': '🐐',
    'cat': '🐈',
    'pig': '🐖',
    'squirrel': '🐿'
}

arena_cover = ['🛡головы', '🛡корпуса', '🛡ног']
arena_attack = ['🗡в голову', '🗡по корпусу', '🗡по ногам']
# поменять blue на red, black, white, yellow в зависимости от вашего замка
castle = orders[castle_name]
# текущий приказ на атаку/защиту, по умолчанию всегда защита, трогать не нужно
current_order = {'time': 0, 'order': castle}

sender = Sender(sock=socket_path) if socket_path else Sender(host=host,port=port)
action_list = deque([])
log_list = deque([], maxlen=30)
lt_arena = 0
get_info_diff = 360
hero_message_id = 0
last_captcha_id = 0

bot_enabled = True
arena_enabled = True
les_enabled = True
corovan_enabled = True
order_enabled = True
auto_def_enabled = True
donate_enabled = False

@coroutine
def work_with_message(receiver):
    while True:
        msg = (yield)
        try:
            if msg['event'] == 'message' and 'text' in msg and msg['peer'] is not None:
                parse_text(msg['text'], msg['sender']['username'], msg['id'])
        except Exception as err:
            log('Ошибка coroutine: {0}'.format(err))


def queue_worker():
    global get_info_diff
    lt_info = 0
    # гребаная магия
    print(sender.contacts_search(bot_username))
    print(sender.contacts_search(captcha_bot))
    sleep(3)
    while True:
        try:
            if time() - lt_info > get_info_diff:
                lt_info = time()
                get_info_diff = random.randint(400, 800)
                if bot_enabled:
                    send_msg(bot_username, orders['hero'])
                continue

            if len(action_list):
                log('Отправляем ' + action_list[0])
                send_msg(bot_username, action_list.popleft())
            sleep_time = random.randint(2, 6)
            sleep(sleep_time)
        except Exception as err:
            log('Ошибка очереди: {0}'.format(err))


def parse_text(text, username, message_id):
    global lt_arena
    global hero_message_id
    global bot_enabled
    global arena_enabled
    global les_enabled
    global corovan_enabled
    global order_enabled
    global auto_def_enabled
    global donate_enabled
    global last_captcha_id
    if bot_enabled and username == bot_username:
        log('Получили сообщение от бота. Проверяем условия')
        sleep(random.randint(1, 5))
        if "На выходе из замка охрана никого не пропускает" in text:
            # send_msg(admin_username, "Командир, у нас проблемы с капчой! #captcha " + '|'.join(captcha_answers.keys()))
            # fwd(admin_username, message_id)
            action_list.clear()
            bot_enabled = False
            last_captcha_id = message_id
            fwd(captcha_bot, message_id)

        elif 'Не умничай!' in text or 'Ты долго думал, аж вспотел от напряжения' in text:
            send_msg(admin_username, "Командир, у нас проблемы с капчой! #captcha " + '|'.join(captcha_answers.keys()))
            bot_enabled = False
            if last_captcha_id != 0:
                fwd(admin_username, message_id)
            else:
                send_msg(admin_username, 'Капча не найдена?')

        elif corovan_enabled and text.find(' /go') != -1:
            action_list.append(orders['corovan'])

        elif text.find('Битва пяти замков через') != -1:
            log('Получили профиль, форвардим ботам')
            for name in order_usernames:
                fwd(name, message_id)
            hero_message_id = message_id
            m = re.search('Битва пяти замков через(?: ([0-9]+)ч)?(?: ([0-9]+))?', text)
            if not m.group(1) and ((m.group(2) and int(m.group(2)) <= 20) or not m.group(2)):
                log('Времени не достаточно, скоро битва!')
                state = re.search('Состояние:\\n(.*)\\n', text)
                log('Состояние: {}'.format(state.group(1)))
                if auto_def_enabled and state.group(1).find('🛌Отдых') != -1:
                    if donate_enabled:
                        gold = int(re.search('💰([0-9]+)', text).group(1))
                        log('Донат {0} золота в казну замка'.format(gold))
                        action_list.append('/donate {0}'.format(gold))
                    update_order(current_order['order'])
                    log('Команда {} отправлена'.format(current_order['order']))
                return
            log('Времени достаточно')
            gold = int(re.search('💰([0-9]+)', text).group(1))
            endurance = int(re.search('Выносливость: ([0-9]+)', text).group(1))
            log('Золото: {0}, выносливость: {1}'.format(gold, endurance))
            if arena_enabled and gold >= 5 and '🔎Поиск соперника' not in action_list and time() - lt_arena > 3600:
                action_list.append('🔎Поиск соперника')
            elif les_enabled and endurance >= 1 and orders['les'] not in action_list:
                action_list.append(orders['les'])

        elif arena_enabled and text.find('выбери точку атаки и точку защиты') != -1:
            lt_arena = time()
            attack_chosen = arena_attack[random.randint(0, 2)]
            cover_chosen = arena_cover[random.randint(0, 2)]
            log('Атака: {0}, Защита: {1}'.format(attack_chosen, cover_chosen))
            action_list.append(attack_chosen)
            action_list.append(cover_chosen)

    elif username == 'ChatWarsCaptchaBot':
        if len(text) <= 4 and text in captcha_answers.values():
            sleep(3)
            action_list.append(text)
            bot_enabled = True

    else:
        if bot_enabled and order_enabled and username in order_usernames:
            if text == orders['red']:
                update_order(orders['red'])
            elif text == orders['black']:
                update_order(orders['black'])
            elif text == orders['white']:
                update_order(orders['white'])
            elif text == orders['yellow']:
                update_order(orders['yellow'])
            elif text == orders['blue']:
                update_order(orders['blue'])
            elif text == orders['lesnoi_fort']:
                update_order(orders['lesnoi_fort'])
            elif text == orders['gorni_fort']:
                update_order(orders['gorni_fort'])

            # send_msg(admin_username, 'Получили команду ' + current_order['order'] + ' от ' + username)

        if username == admin_username:
            if text == '#help':
                send_msg(admin_username, '\n'.join([
                    '#enable_bot - Включить бота',
                    '#disable_bot - Выключить бота',
                    '#enable_arena - Включить арену',
                    '#disable_arena - Выключить арену',
                    '#enable_les - Включить лес',
                    '#disable_les - Выключить лес',
                    '#enable_corovan - Включить корован',
                    '#disable_corovan - Выключить корован',
                    '#enable_order - Включить приказы',
                    '#disable_order - Выключить приказы',
                    '#enable_auto_def - Включить авто деф',
                    '#disable_auto_def - Выключить авто деф',
                    '#enable_donate - Включить донат',
                    '#disable_donate - Выключить донат',
                    '#status - Получить статус',
                    '#hero - Получить информацию о герое',
                    '#push_order - Добавить приказ ({0})'.format(','.join(orders)),
                    '#order - Дебаг, последняя команда защиты/атаки замка',
                    '#log - Дебаг, последние 30 сообщений из лога',
                    '#time - Дебаг, текущее время',
                    '#lt_arena - Дебаг, последняя битва на арене',
                    '#get_info_diff - Дебаг, последняя разница между запросами информации о герое',
                    '#ping - Дебаг, проверить жив ли бот',
                ]))

            # Вкл/выкл бота
            elif text == '#enable_bot':
                bot_enabled = True
                send_msg(admin_username, 'Бот успешно включен')
            elif text == '#disable_bot':
                bot_enabled = False
                send_msg(admin_username, 'Бот успешно выключен')

            # Вкл/выкл арены
            elif text == '#enable_arena':
                arena_enabled = True
                send_msg(admin_username, 'Арена успешно включена')
            elif text == '#disable_arena':
                arena_enabled = False
                send_msg(admin_username, 'Арена успешно выключена')

            # Вкл/выкл леса
            elif text == '#enable_les':
                les_enabled = True
                send_msg(admin_username, 'Лес успешно включен')
            elif text == '#disable_les':
                les_enabled = False
                send_msg(admin_username, 'Лес успешно выключен')

            # Вкл/выкл корована
            elif text == '#enable_corovan':
                corovan_enabled = True
                send_msg(admin_username, 'Корованы успешно включены')
            elif text == '#disable_corovan':
                corovan_enabled = False
                send_msg(admin_username, 'Корованы успешно выключены')

            # Вкл/выкл команд
            elif text == '#enable_order':
                order_enabled = True
                send_msg(admin_username, 'Приказы успешно включены')
            elif text == '#disable_order':
                order_enabled = False
                send_msg(admin_username, 'Приказы успешно выключены')

            # Вкл/выкл авто деф
            elif text == '#enable_auto_def':
                auto_def_enabled = True
                send_msg(admin_username, 'Авто деф успешно включен')
            elif text == '#disable_auto_def':
                auto_def_enabled = False
                send_msg(admin_username, 'Авто деф успешно выключен')

            # Вкл/выкл авто донат
            elif text == '#enable_donate':
                donate_enabled = True
                send_msg(admin_username, 'Донат успешно включен')
            elif text == '#disable_donate':
                donate_enabled = False
                send_msg(admin_username, 'Донат успешно выключен')

            # Получить статус
            elif text == '#status':
                send_msg(admin_username, '\n'.join([
                    'Бот включен: {0}',
                    'Арена включена: {1}',
                    'Лес включен: {2}',
                    'Корованы включены: {3}',
                    'Приказы включены: {4}',
                    'Авто деф включен: {5}',
                    'Донат включен: {6}',
                ]).format(bot_enabled, arena_enabled, les_enabled, corovan_enabled, order_enabled, auto_def_enabled, donate_enabled))

            # Информация о герое
            elif text == '#hero':
                if hero_message_id == 0:
                    send_msg(admin_username, 'Информация о герое пока еще недоступна')
                else:
                    fwd(admin_username, hero_message_id)

            # Получить лог
            elif text == '#log':
                send_msg(admin_username, '\n'.join(log_list))
                log_list.clear()

            elif text == '#lt_arena':
                send_msg(admin_username, str(lt_arena))

            elif text == '#order':
                text_date = datetime.datetime.fromtimestamp(current_order['time']).strftime('%Y-%m-%d %H:%M:%S')
                send_msg(admin_username, current_order['order'] + ' ' + text_date)

            elif text == '#time':
                text_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                send_msg(admin_username, text_date)

            elif text == '#ping':
                send_msg(admin_username, '#pong')

            elif text == '#get_info_diff':
                send_msg(admin_username, str(get_info_diff))

            elif text.startswith('#push_order'):
                command = text.split(' ')[1]
                if command in orders:
                    update_order(orders[command])
                    send_msg(admin_username, 'Команда ' + command + ' применена')
                else:
                    send_msg(admin_username, 'Команда ' + command + ' не распознана')

            elif text.startswith('#captcha'):
                command = text.split(' ')[1]
                if command in captcha_answers:
                    action_list.append(captcha_answers[command])
                    bot_enabled = True
                    send_msg(admin_username, 'Команда ' + command + ' применена')
                else:
                    send_msg(admin_username, 'Команда ' + command + ' не распознана')


def send_msg(to, message):
    sender.send_msg('@' + to, message)


def fwd(to, message_id):
    sender.fwd('@' + to, message_id)


def update_order(order):
    current_order['order'] = order
    current_order['time'] = time()
    if order == castle:
        action_list.append(orders['cover'])
    else:
        action_list.append(orders['attack'])
    action_list.append(order)


def log(text):
    message = '{0:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()) + ' ' + text
    print(message)
    log_list.append(message)


if __name__ == '__main__':
    receiver = Receiver(sock=socket_path) if socket_path else Receiver(port=port)
    receiver.start()  # start the Connector.
    _thread.start_new_thread(queue_worker, ())
    receiver.message(work_with_message(receiver))
    receiver.stop()
