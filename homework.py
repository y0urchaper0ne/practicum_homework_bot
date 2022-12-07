import logging
import os
import sys
import time
import telegram
import requests
from http import HTTPStatus

from dotenv import load_dotenv 
from exceptions import ServerCodeError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s, %(levelname)s,'
           ' %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет статус домашней работы пользователю"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logger.error(
            f'Ошибка отправки статуса в telegram: {error}'
        )
    else:
        logger.debug('Статус отправлен в telegram')



def get_api_answer(current_timestamp):
    """Получает данные о домашней работы из эндпоинта"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise ServerCodeError('Ответ API не был получен')
        else: 
            return response.json()
    except requests.RequestException as error:
        logger.error(f'Данный эндпоинт недоступен: {error}')


def check_response(response):
    """Проверка наличия домашней работы в ответе API"""
    # try:
    #     homeworks = response['homeworks']
    # except KeyError as error:
    #     logger.error(f'Нет данных по ключу homeworks: {error}')
    #     raise KeyError('Нет данных по ключу homeworks')
    # if not isinstance(response[homeworks], list):
    #     logger.error('Тип запроса - не список')
    #     raise TypeError('В ответе API пришел не список')
    # return homeworks

    if not isinstance(response, dict):
        raise TypeError(f'Неверный тип данных {response}, вместо "dict"')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('В ответе API нету подходящих ключей')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError('Homeworks не является списком')
    return homework


def parse_status(homework):
    """Получение текущего статуса домашней работы"""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.error('Отсутствие ожидаемых ключей в отмете API')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неизвестный статус домашней работы - {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности необходимых для работы переменных окружения"""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Описана основная логика работы программы"""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    check = check_tokens()
    if not check:
        logger.critical('Не найдены переменные окружения')
        sys.exit()
    send_message(bot, 'Старт')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if not homework:
                current_timestamp = response['current_date']
                logger.info('Сработал time.sleep при пустом списке')
                time.sleep(RETRY_PERIOD)
            else:
                message = parse_status(homework[0])
                send_message(bot, message)
                logger.info('Сообщение успешно отправлено')
            current_timestamp = homework.get('current_date',current_timestamp)    
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logger.critical(f'Сбой отправки сообщения: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        else:
            logger.info('Программа работает без сбоев')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
