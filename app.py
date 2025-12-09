from aiogram import executor

from loader import dp, user_db, group_db,channel_db,cache_db,book_db
import middlewares, filters, handlers
from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands


async def on_startup(dispatcher):
    # Birlamchi komandalar (/start va /help)
    await set_default_commands(dispatcher)

    # Bot ishga tushganda bazani yaratamiz
    try:
        user_db.create_table_users()
        group_db.create_table_groups()
        channel_db.create_table_channels()
        cache_db.create_table_cache()
        cache_db.create_table_request_stats()
        book_db.create_tables()

    except Exception as err:
        print(f"Error while creating tables: {err}")

    # Bot ishga tushgani haqida adminga xabar berish
    await on_startup_notify(dispatcher)


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup)
