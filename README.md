1. Скачать chromedriver в зависимости от OS и положить в директорию проекта  
2. Установить зависимости из requirements.txt  
3. Запустить worker celery (run_worker.py), запустить задачу celery (run_tasks.py)  
4. Определимть переменные окружения в .env  
   AUTH - данные из localStorage из web telegramm    
   Выполнить команты в консоли браузера chrome  
   Предварительно данные надо получить из localStorage веб версии телеграмм  
   `localStorage.removeItem('tt-global-state')`  
   `JSON.stringify(localStorage)`

   TELEGRAM_TOKEN - токен телеграмм бота для отправки информации по статистике майнинга  
