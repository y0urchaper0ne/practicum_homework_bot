import logging
import os
import sys
import time
import telegram
import requests
from http import HTTPStatus

from dotenv import load_dotenv
from exceptions import ApiResponseCodeError

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


def send_message(bot, message):
    """Отправляет статус домашней работы пользователю."""
    logging.info('Отправляю сообщение в Телеграм')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(
            f'Ошибка отправки статуса в telegram: {error}'
        )
    else:
        logging.debug('Статус отправлен в telegram')


def get_api_answer(current_timestamp):
    """Получает данные о домашней работы из эндпоинта."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise ApiResponseCodeError(
                'Ответ API не был получен.'
                f'Статус-код: {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Данный эндпоинт недоступен: {error}')


def check_response(response):
    """Проверка наличия домашней работы в ответе API."""
    if not isinstance(response, dict):
        raise TypeError(f'Неверный тип данных {response}, вместо "dict"')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа: homework')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа: current_date')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError('Homeworks не является списком')
    return homework


def parse_status(homework):
    """Получение текущего статуса домашней работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.error('Отсутствие ожидаемых ключей homework_name в ответе API')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Неизвестный статус домашней работы - {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности необходимых для работы переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Описана основная логика работы программы."""
    check = check_tokens()
    if not check:
        logging.critical('Не найдены переменные окружения')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    send_message(bot, 'Старт')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if not homework:
                current_timestamp = response['current_date']
                logging.info('Сработал time.sleep при пустом списке')
            else:
                message = parse_status(homework[0])
                send_message(bot, message)
                logging.info('Сообщение успешно отправлено')
            current_timestamp = homework.get('current_date', current_timestamp)
        except Exception as error:
            logger.error(f'Сбой отправки сообщения: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        else:
            logging.info('Программа работает без сбоев')
        finally:
            time.sleep(RETRY_PERIOD)



if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.FileHandler('main.log', 'w', 'utf-8')],
        format='%(asctime)s, %(levelname)s,'
            ' %(message)s'
    )
    logger = logging.getLogger(__name__)
    main()
