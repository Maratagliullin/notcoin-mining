import os
import random
import re
import sys
import time
from datetime import datetime
from urllib.parse import unquote

import requests
from celery import Celery, shared_task
from celery.exceptions import MaxRetriesExceededError
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (TimeoutException,
                                        NoSuchElementException)
from telegram import TelegramError
from telegram.ext import Filters, MessageHandler, Updater
from urllib3.exceptions import MaxRetryError

app = Celery('tasks', broker='redis://localhost:6379/0',
             backend='redis://localhost:6379/0',
             broker_connection_retry_on_startup=True,
             task_serializer='json',
             result_serializer='json',
             accept_content=['application/json'],
             serializer='json',)


# Структура хранения подписчиков бота
chat_list = []

# Частота обращения к сервису
delay_seconds = 180

# Загрузка переменных окружения
load_dotenv()
AUTH = os.environ.get('AUTH').replace('\\\\', '\\')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Инициализация Телеграмм бота
updater = Updater(token=TELEGRAM_TOKEN)


def bot_initialize(update, context) -> None:
    '''Отправка сообщения после подписки на бота'''
    chat = update.effective_chat
    if chat.id not in chat_list:
        chat_list.append(chat.id)
    context.bot.send_message(chat_id=chat.id,
                             text='Отправка метрик по майнингу.')


def send_message_telegramm(message) -> None:
    '''Отправка сообщения в telegram'''
    for chat_item in chat_list:
        try:
            updater.bot.send_message(chat_id=chat_item,
                                     text=message, parse_mode='HTML')
        except TelegramError:
            print('Произошла ошибка при отправке сообщения в телеграм')


class TelegrammLoginError(ValueError):
    def __init__(self, message, custom_parameter, countdown=delay_seconds):
        super().__init__(message)
        self.custom_parameter = custom_parameter
        self.countdown = countdown


class TelegrammIdentityError(ValueError):
    def __init__(self, message, custom_parameter, countdown=delay_seconds):
        super().__init__(message)
        self.custom_parameter = custom_parameter
        self.countdown = countdown


class RetryTask(Exception):
    def __init__(self, countdown=delay_seconds):
        self.countdown = countdown
        super().__init__()


def click(webapp, accessToken) -> None:
    '''Имитация тапа в приложении'''
    headers = {
        'Authorization': f'Bearer {str(accessToken)}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    click_data = {'webAppData': unquote(webapp),
                  'count': random.randint(900, 1000)
                  }
    # Выполнение POST-запроса на отправку клика
    response = requests.post(
        'https://clicker-api.joincommunity.xyz/clicker/core/click/',
        data=click_data,
        headers=headers)

    json_data = response.json()
    print('HTTP код ответа: ', response.status_code)

    if response.status_code == 401:
        # Тут можно завершать процесс посольку он связан
        # с разлогиниванием в телеграмм
        print(f'401: {str(json_data)}')
        send_message_telegramm(message=f'401: {str(json_data)}')
        raise TelegrammLoginError(
            'Необходимо пройти авторизацию в телеграмм',
            custom_parameter='401')
    elif response.status_code == 400:
        # Проблема в проверке подлинности в этом случае
        # можно перезапустить получение AccesToken и повторить попытку
        print(f'400: {str(json_data)}')
        send_message_telegramm(message=f'400:  {str(json_data)}')

        raise TelegrammIdentityError(
            'Необзодимо пройти проверку подлинности',
            custom_parameter='400')

    elif response.status_code == 201:
        # Отправка текстовой части сообщение
        message = f'''
        totalCoins: {json_data['data'][0]['totalCoins']}
        limitCoins: {json_data['data'][0]['limitCoins']}
        balanceCoins:{json_data['data'][0]['balanceCoins']}
        availableCoins: {json_data['data'][0]['availableCoins']}
        '''
        send_message_telegramm(message)

        now = datetime.now()
        current_time = now.strftime('%H:%M:%S')
        print('Время =', current_time)
        if not chat_list:
            print('''Подписчики бота не найдены,
                  выполни команду /start внутри своего бота''')

        print('Запрос выполнен!')
        print('totalCoins: ', json_data['data'][0]['totalCoins'])
        print('limitCoins: ', json_data['data'][0]['limitCoins'])
        print('balanceCoins: ', json_data['data'][0]['balanceCoins'])
        print('availableCoins: ', json_data['data'][0]['availableCoins'], '\n')

    else:
        print(f': {str(json_data)}')
        send_message_telegramm(message=f': {str(json_data)}')
        raise RetryTask(
            'Повтор попытки в случае не известного кода ответа')


# Перейдем на страницу входа в Telegram
def get_page(url, driver):
    try:
        driver.get(url)
    except MaxRetryError:
        message = '''Произошла ошибка MaxRetryError:
            Вероятно поблема с автоизацией
            необходимо заново заполнить .env новыми значениями'''
        print(message)
        send_message_telegramm(message)
        driver.quit()
        updater.stop()
        raise open_webpage.retry(countdown=delay_seconds)

    except TimeoutException:
        message = '''Ошибка: Время ожидания истекло. 
              Страница не загружена за отведенное время.'''
        print(message)
        driver.quit()
        updater.stop()
        raise open_webpage.retry(countdown=delay_seconds)

    except MaxRetriesExceededError:
        message = '''Количество попыток 
        первичного открытия страницы превысило значение 20'''
        send_message_telegramm(message)
        driver.quit()
        updater.stop()
        sys.exit()

    except Exception as e:
        message = f'Exeption: {str(e)}'
        send_message_telegramm(message)
        driver.quit()
        updater.stop()
        raise open_webpage.retry(countdown=delay_seconds)

    time.sleep(5)


@shared_task(bind=True, max_retries=5, delay_seconds=delay_seconds)
def open_webpage(self):

    updater.dispatcher.add_handler(
        MessageHandler(Filters.text, bot_initialize))
    updater.start_polling()

    # Проверка установки переменных окружения
    if not AUTH and not TELEGRAM_TOKEN:
        message = 'API Keys не найдены в переменных окружения.'
        print(message)
        send_message_telegramm(message)
        sys.exit()

    # Опции chromedriver
    chrome_options = Options()
    chrome_options.add_experimental_option('detach', True)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)

    url = 'https://web.telegram.org/k/#@notcoin_bot'
    get_page(url, driver)

    # Предварительно данные надо получить из localStorage веб версии телеграмм
    # localStorage.removeItem('tt-global-state')
    # JSON.stringify(localStorage)
    # Значение необходимо определить в параметре AUTH='' в .env файле

    # Установка переменной окружения в браузер
    set_localstorage_script = f'''
        var data = {AUTH};
        for (var key in data) {{
            localStorage.setItem(key, JSON.parse(data[key]));
        }}
    '''
    driver.execute_script(set_localstorage_script)

    time.sleep(5)
    driver.refresh()
    time.sleep(5)

    get_page(url, driver)

    # Ожидание появления элемента кнопки Play
    timeout = 20
    try:
        element_present = EC.element_to_be_clickable(
            (By.PARTIAL_LINK_TEXT, 'Play'))
        phone_button = WebDriverWait(driver, timeout).until(element_present)
        phone_button.click()
    except NoSuchElementException:
        message = 'Кнопка Play не найдена'
        send_message_telegramm(message)
        print(message)
        driver.quit()

    # Ожидание появления элемента кнопки Launch
    timeout = 20
    try:
        element_present = EC.element_to_be_clickable((
            By.XPATH, '//button[.//span[text()="Launch"]]'))
        phone_button = WebDriverWait(driver, timeout).until(element_present)
        phone_button.click()
    except NoSuchElementException:
        message = 'Launch button not found'
        send_message_telegramm(message)
        print(message)
        driver.quit()

    time.sleep(10)

    iframe_pattern = re.compile(r'<iframe[^>]*>.*?</iframe>', re.DOTALL)
    matches = iframe_pattern.search(driver.page_source)

    if matches:
        src_value = matches.group()
        webapp = re.compile(
            r'user.*(?=tgWebAppVersion=7.0)', re.IGNORECASE)
        webapp_val = webapp.search(src_value)
        webapp = webapp_val[0].replace('&amp;', '')
        driver.quit()
    else:
        message = 'Значения webapp не получены'
        send_message_telegramm(message)
        driver.quit()
        print('Совпадения не найдены')
        updater.stop()
        raise self.retry(countdown=delay_seconds)

    # Параметры запроса для получение JWT Токена
    payload = {'webAppData': unquote(webapp)}

    # Выполнение POST-запроса на поулчение JWT токена авторизации
    try:
        response = requests.post(
            'https://clicker-api.joincommunity.xyz/auth/webapp-session/',
            data=payload)
    except Exception as e:
        send_message_telegramm(
            message=f'''Ошибка при получении
            JWT токена задача будет перезапущена {e}''')
        updater.stop()
        raise self.retry(countdown=delay_seconds)

    if response.status_code == 201:
        json_data = response.json()
        accessToken = json_data['data']['accessToken']
        print('accessToken: ', accessToken)
        max_attempts = 10
        current_attempt = 1
        while current_attempt <= max_attempts:
            try:
                click(webapp, accessToken)
                time.sleep(delay_seconds)
                current_attempt = 1
                open_webpage.max_retries = 5
            except TelegrammLoginError:
                current_attempt = 10
                driver.quit()
                send_message_telegramm(
                    message=f'''Завершеение процесса
                    в связи со сбросом авторизации telegram
                    количесво попыток max_retry {open_webpage.request.retries}''')
                updater.stop()
                sys.exit()

            except TelegrammIdentityError:
                current_attempt += 1
                driver.quit()
                time.sleep(delay_seconds)
                send_message_telegramm(
                    message=f'''Перезапуск проверки подлинности
                    количесво попыток max_retry {open_webpage.request.retries}''')
                updater.stop()
                raise self.retry(countdown=delay_seconds)

            except RetryTask:
                current_attempt += 1
                driver.quit()
                time.sleep(delay_seconds)
                send_message_telegramm(
                    message=f'''Повтор попытки
                    в случае не известного кода ответа
                    количесво попыток max_retry {open_webpage.request.retries}
                    ''')
                updater.stop()
                raise self.retry(countdown=delay_seconds)

            except Exception as e:
                current_attempt += 1
                print(f'An exception occurred: {str(e)}')
                driver.quit()
                time.sleep(delay_seconds)
                send_message_telegramm(
                    message=f'''Перезапуск после неизвестной
                    ошибки общий Exeption {str(e)}
                    количесво попыток max_retry {open_webpage.request.retries}
                    ''')
                updater.stop()
                raise self.retry(countdown=delay_seconds)


open_webpage.apply_async(args=[])
