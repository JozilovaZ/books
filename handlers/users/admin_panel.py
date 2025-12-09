from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging

from data.config import ADMINS
from loader import dp, user_db
from keyboards.default.default_keyboard import menu_ichki_admin, menu_admin


# =================== STATE'LAR ===================

class AdminStates(StatesGroup):
    AddAdmin = State()
    RemoveAdmin = State()


# =================== YORDAMCHI FUNKSIYALAR ===================

async def check_super_admin_permission(telegram_id: int):
    """Super admin huquqini tekshirish"""
    logging.info(f"Checking super admin permission for telegram_id: {telegram_id}")
    return telegram_id in ADMINS


async def check_admin_permission(telegram_id: int):
    """Admin huquqini tekshirish"""
    logging.info(f"Checking admin permission for telegram_id: {telegram_id}")
    user = user_db.select_user(telegram_id=telegram_id)
    if not user:
        logging.info(f"No user found with telegram_id {telegram_id}")
        return False
    user_id = user[0]  # Users jadvalidagi id (user_id)
    admin = user_db.check_if_admin(user_id=user_id)
    logging.info(f"Admin check result for user_id {user_id}: {admin}")
    return admin


# =================== ORTGA QAYTISH ===================

@dp.message_handler(Text("🔙 Ortga qaytish"))
async def back_handler(message: types.Message):
    """Bosh sahifaga qaytish"""
    telegram_id = message.from_user.id

    if await check_super_admin_permission(telegram_id) or await check_admin_permission(telegram_id):
        await message.answer(
            "🏠 <b>Bosh sahifa</b>\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=menu_admin
        )


# =================== ADMIN PANEL ===================

@dp.message_handler(commands="panel")
async def control_panel(message: types.Message):
    """Admin panelga kirish"""
    telegram_id = message.from_user.id
    logging.info(f"User {telegram_id} is trying to access the admin panel.")

    if await check_super_admin_permission(telegram_id) or await check_admin_permission(telegram_id):
        admin_name = message.from_user.first_name
        await message.answer(
            f"🎛 <b>Boshqaruv paneli</b>\n\n"
            f"Salom, <b>{admin_name}</b>! 👋\n"
            f"Tizim boshqaruviga xush kelibsiz.\n\n"
            f"💼 Sizning huquqlaringiz:\n"
            f"{'⭐️ Super Administrator' if telegram_id in ADMINS else '🔰 Administrator'}\n\n"
            f"Kerakli bo'limni tanlang:",
            reply_markup=menu_admin
        )
        logging.info(f"Admin {telegram_id} accessed the control panel")
    else:
        await message.reply(
            "🚫 <b>Kirish rad etildi!</b>\n\n"
            "Sizda bu bo'limga kirish huquqi yo'q.\n"
            "Faqat adminlar uchun mavjud."
        )
        logging.warning(f"Unauthorized access attempt by {telegram_id}")


# =================== ADMINLAR BOSHQARUVI ===================

@dp.message_handler(Text(equals="👥 Adminlar boshqaruvi"))
async def admin_control_menu(message: types.Message):
    """Adminlar boshqaruvi menyusi"""
    telegram_id = message.from_user.id
    logging.info(f"User {telegram_id} is trying to access admin control menu.")

    if not await check_super_admin_permission(telegram_id):
        await message.reply(
            "⚠️ <b>Ruxsat berilmadi</b>\n\n"
            "Bu bo'lim faqat <b>Super Adminlar</b> uchun.\n"
            "Siz oddiy admin sifatida bu amalni bajara olmaysiz."
        )
        logging.warning(f"Non-super admin {telegram_id} tried to access admin control")
        return

    # Hozirgi adminlar soni
    admins = user_db.get_all_admins()
    admin_count = len(admins) + len(ADMINS)  # DB + ADMINS ro'yxati

    await message.answer(
        "🛡 <b>Adminlar boshqaruvi</b>\n\n"
        f"👤 Hozirgi adminlar: <b>{admin_count}</b> ta\n\n"
        "Bu bo'limda siz:\n"
        "• Yangi admin tayinlashingiz\n"
        "• Adminlarni o'chirishingiz\n"
        "• Barcha adminlarni ko'rishingiz mumkin\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=menu_ichki_admin
    )


# =================== ADMIN QO'SHISH ===================

@dp.message_handler(Text(equals="➕ Admin qo'shish"))
async def add_admin(message: types.Message):
    """Admin qo'shishni boshlash"""
    telegram_id = message.from_user.id
    logging.info(f"User {telegram_id} is trying to add a new admin.")

    if not await check_super_admin_permission(telegram_id):
        await message.reply(
            "⚠️ <b>Ruxsat berilmadi</b>\n\n"
            "Faqat Super Adminlar yangi admin tayinlay oladi."
        )
        return

    await message.answer(
        "➕ <b>Yangi admin tayinlash</b>\n\n"
        "Yangi admin bo'lishi kerak bo'lgan shaxsning\n"
        "<b>Telegram ID</b> raqamini yuboring.\n\n"
        "💡 <i>ID ni qanday topish mumkin:\n"
        "Shaxsdan @userinfobot ga /start yuborishni so'rang</i>"
    )
    await AdminStates.AddAdmin.set()


@dp.message_handler(state=AdminStates.AddAdmin)
async def process_admin_add(message: types.Message, state: FSMContext):
    """Admin qo'shish - ID ni qayta ishlash"""

    if not message.text.isdigit():
        await message.answer(
            "❗️ <b>Noto'g'ri format</b>\n\n"
            "Telegram ID faqat <b>raqamlardan</b> iborat bo'lishi kerak.\n\n"
            "Masalan: <code>123456789</code>\n\n"
            "Qaytadan kiriting:"
        )
        return

    admin_telegram_id = int(message.text)
    logging.info(f"Adding admin with Telegram ID: {admin_telegram_id}")
    user = user_db.select_user(telegram_id=admin_telegram_id)

    if not user:
        await message.answer(
            "🔍 <b>Foydalanuvchi topilmadi</b>\n\n"
            "Bu ID egasi hali botdan foydalanmagan.\n\n"
            "✅ <b>Hal qilish:</b>\n"
            "1. Foydalanuvchidan botga /start yuborishni so'rang\n"
            "2. Keyin qaytadan ID ni yuboring"
        )
        await state.finish()
        logging.warning(f"User {admin_telegram_id} not found in database")
        return

    user_id = user[0]  # Users jadvalidagi user_id

    # Admin ekanligini tekshirish
    if user_db.check_if_admin(user_id=user_id):
        await message.answer(
            "ℹ️ <b>Admin allaqachon mavjud</b>\n\n"
            f"@{user[2]} allaqachon admin huquqiga ega.\n\n"
            "Boshqa ID kiriting yoki /panel orqali qaytib keting."
        )
        await state.finish()
        logging.info(f"User {admin_telegram_id} is already an admin")
        return

    # Admin qo'shish
    user_db.add_admin(user_id=user_id, name=user[2])  # user[2] - username
    logging.info(f"Admin added: Telegram ID {user[1]}, Name {user[2]}")

    await message.answer(
        "✅ <b>Admin muvaffaqiyatli tayinlandi!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> @{user[2]}\n"
        f"🆔 <b>ID:</b> <code>{user[1]}</code>\n"
        f"🔰 <b>Lavozim:</b> Administrator\n\n"
        f"Endi @{user[2]} admin panel imkoniyatlaridan foydalana oladi."
    )
    await state.finish()


# =================== ADMIN O'CHIRISH ===================

@dp.message_handler(Text(equals="❌ Adminni o'chirish"))
async def remove_admin(message: types.Message):
    """Admin o'chirishni boshlash"""
    telegram_id = message.from_user.id
    logging.info(f"User {telegram_id} is trying to remove an admin.")

    if not await check_super_admin_permission(telegram_id):
        await message.reply(
            "⚠️ <b>Ruxsat berilmadi</b>\n\n"
            "Faqat Super Adminlar adminlarni lavozimdan ozod qila oladi."
        )
        return

    await message.answer(
        "🗑 <b>Adminni lavozimdan ozod qilish</b>\n\n"
        "Lavozimdan ozod qilmoqchi bo'lgan adminning\n"
        "<b>Telegram ID</b> raqamini yuboring.\n\n"
        "⚠️ <i>Super Adminlarni o'chirib bo'lmaydi!</i>"
    )
    await AdminStates.RemoveAdmin.set()


@dp.message_handler(state=AdminStates.RemoveAdmin)
async def process_admin_remove(message: types.Message, state: FSMContext):
    """Admin o'chirish - ID ni qayta ishlash"""

    if not message.text.isdigit():
        await message.answer(
            "❗️ <b>Noto'g'ri format</b>\n\n"
            "Telegram ID faqat <b>raqamlardan</b> iborat bo'lishi kerak.\n\n"
            "Qaytadan kiriting:"
        )
        return

    admin_telegram_id = int(message.text)
    logging.info(f"Removing admin with Telegram ID: {admin_telegram_id}")
    user = user_db.select_user(telegram_id=admin_telegram_id)

    if not user:
        await message.answer(
            "🔍 <b>Foydalanuvchi topilmadi</b>\n\n"
            "Bu ID tizimda mavjud emas.\n\n"
            "ID ni to'g'ri kiritganingizga ishonch hosil qiling."
        )
        await state.finish()
        return

    user_id = user[0]  # Users jadvalidagi user_id

    # Admin ekanligini tekshirish
    if not user_db.check_if_admin(user_id=user_id):
        await message.answer(
            "ℹ️ <b>Admin emas</b>\n\n"
            f"@{user[2]} admin lavozimiga ega emas.\n\n"
            "Faqat adminlar o'chirilishi mumkin."
        )
        await state.finish()
        return

    # Super adminni o'chirishga urinishni oldini olish
    if admin_telegram_id in ADMINS:
        await message.answer(
            "🛡 <b>Himoyalangan admin</b>\n\n"
            f"@{user[2]} <b>Super Admin</b> hisoblanadi.\n\n"
            "⚠️ Super Adminlarni lavozimdan ozod qilib bo'lmaydi!\n"
            "Ular config faylida belgilangan."
        )
        await state.finish()
        logging.warning(f"Attempt to remove super admin {admin_telegram_id}")
        return

    # Adminni o'chirish
    user_db.remove_admin(user_id=user_id)
    logging.info(f"Admin removed: Telegram ID {user[1]}, Name {user[2]}")

    await message.answer(
        "✅ <b>Admin lavozimdan ozod qilindi</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> @{user[2]}\n"
        f"🆔 <b>ID:</b> <code>{user[1]}</code>\n\n"
        f"@{user[2]} endi oddiy foydalanuvchi sifatida davom etadi."
    )
    await state.finish()


# =================== ADMINLAR RO'YXATI ===================

@dp.message_handler(Text(equals="👥 Barcha adminlar"))
async def list_all_admins(message: types.Message):
    """Barcha adminlar ro'yxatini ko'rsatish"""
    telegram_id = message.from_user.id
    logging.info(f"User {telegram_id} is requesting the admin list.")

    if not await check_super_admin_permission(telegram_id) and not await check_admin_permission(telegram_id):
        await message.reply(
            "🚫 <b>Kirish rad etildi</b>\n\n"
            "Bu ma'lumotni faqat adminlar ko'rishi mumkin."
        )
        return

    # Admins jadvalidan barcha adminlarni olish
    admins = user_db.get_all_admins()
    logging.info(f"Fetched admin list: {admins}")

    admin_list = []
    super_admin_count = 0
    regular_admin_count = 0

    # Database'dagi adminlar
    if admins:
        for admin in admins:
            is_super = admin['telegram_id'] in ADMINS

            if is_super:
                super_admin_count += 1
                badge = "⭐️"
                role = "Super Admin"
            else:
                regular_admin_count += 1
                badge = "🔰"
                role = "Admin"

            admin_list.append(
                f"{badge} <b>{admin['name']}</b>\n"
                f"    🆔 <code>{admin['telegram_id']}</code>\n"
                f"    💼 {role}"
            )

    # Config'dagi Super adminlar (agar DB'da yo'q bo'lsa)
    for admin_id in ADMINS:
        if not any(admin['telegram_id'] == admin_id for admin in admins):
            super_admin_count += 1
            admin_list.append(
                f"⭐️ <b>Super Admin</b>\n"
                f"    🆔 <code>{admin_id}</code>\n"
                f"    💼 Super Admin"
            )

    # Javob matnini shakllantirish
    if admin_list:
        total_admins = super_admin_count + regular_admin_count

        header = (
            "👥 <b>ADMINLAR RO'YXATI</b>\n\n"
            f"📊 <b>Umumiy statistika:</b>\n"
            f"├ Jami adminlar: <b>{total_admins}</b>\n"
            f"├ Super Adminlar: <b>{super_admin_count}</b> ta\n"
            f"└ Oddiy Adminlar: <b>{regular_admin_count}</b> ta\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
        )

        full_list = "\n\n".join(admin_list)

        footer = (
            "\n\n━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 <b>Eslatma:</b>\n"
            "⭐️ - Super Admin (to'liq huquqlar)\n"
            "🔰 - Admin (cheklangan huquqlar)"
        )

        await message.answer(header + full_list + footer)
    else:
        await message.answer(
            "📋 <b>Adminlar ro'yxati</b>\n\n"
            "❌ Hozircha tizimda adminlar yo'q.\n\n"
            "Super Adminlar config faylida belgilanadi."
        )


# =================== XATOLIKLARNI TUTISH ===================

@dp.errors_handler()
async def errors_handler(update, exception):
    """Global xatoliklarni tutish"""
    logging.error(f"Update: {update} \nError: {exception}")
    return True