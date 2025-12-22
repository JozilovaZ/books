import datetime
import asyncio
import logging
from data.config import ADMINS
from loader import bot, dp, user_db
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, RetryAfter, Unauthorized

# Loglarni sozlash (xatolarni terminalda ko'rish uchun)
logger = logging.getLogger(__name__)

advertisements = []


class ReklamaTuriState(StatesGroup):
    tur = State()
    vaqt = State()
    time_value = State()
    content = State()
    buttons = State()


class Advertisement:
    def __init__(self, ad_id, message, ad_type, keyboard=None, send_time=None, creator_id=None):
        self.ad_id = ad_id
        self.message = message
        self.ad_type = ad_type
        self.keyboard = keyboard
        self.send_time = send_time
        self.creator_id = creator_id
        self.running = False
        self.paused = False
        self.sent_count = 0
        self.failed_count = 0
        self.total_users = 0
        self.current_message = None
        self.task = None

    async def start(self):
        self.running = True
        if self.send_time:
            delay = (self.send_time - datetime.datetime.now()).total_seconds()
            if delay > 0:
                await asyncio.sleep(delay)

        # Foydalanuvchilarni olish
        users = user_db.select_all_users()
        self.total_users = len(users)

        # Adminni xabardor qilish
        try:
            self.current_message = await bot.send_message(
                chat_id=self.creator_id,
                text=f"🚀 Reklama #{self.ad_id} yuborish boshlandi...",
                reply_markup=get_status_keyboard(self.ad_id)
            )
        except Exception as e:
            logger.error(f"Admin xabari yuborilmadi: {e}")

        for user in users:
            if not self.running: break
            while self.paused:
                await asyncio.sleep(1)
                if not self.running: break

            try:
                # user[1] - bazangizda telegram_id ekanligini tekshiring
                # Odatda user[1] yoki user[0] bo'ladi
                user_id = user[1]

                await send_advertisement_to_user(user_id, self)
                self.sent_count += 1
            except (BotBlocked, ChatNotFound, Unauthorized):
                self.failed_count += 1
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)
                # Retrydan keyin qayta urinish
                await send_advertisement_to_user(user_id, self)
                self.sent_count += 1
            except Exception as e:
                self.failed_count += 1
                logger.error(f"User {user_id} error: {e}")

            # Bot API bloklanmasligi uchun
            await asyncio.sleep(0.05)

            # Har 20 ta xabarda statusni yangilash (Telegram limitiga tushmaslik uchun)
            if (self.sent_count + self.failed_count) % 20 == 0:
                await self.update_status_message()

        self.running = False
        await self.update_status_message(finished=True)

    async def pause(self):
        self.paused = True
        await self.update_status_message()

    async def resume(self):
        self.paused = False
        await self.update_status_message()

    async def stop(self):
        self.running = False
        await self.update_status_message(stopped=True)

    async def update_status_message(self, finished=False, stopped=False):
        status = "✅ Yakunlandi" if finished else (
            "🛑 To'xtatildi" if stopped else ("⏸ Pauza" if self.paused else "🔄 Davom etmoqda"))
        if self.current_message:
            try:
                await self.current_message.edit_text(
                    text=f"📋 <b>Reklama #{self.ad_id}</b>\n\n✅ Yuborildi: {self.sent_count}\n❌ Xatolik: {self.failed_count}\n📊 Jami: {self.total_users}\n\n<b>Status:</b> {status}",
                    reply_markup=None if finished or stopped else get_status_keyboard(self.ad_id, self.paused),
                    parse_mode="HTML"
                )
            except Exception:
                pass


async def send_advertisement_to_user(chat_id, ad: Advertisement):
    msg = ad.message
    kb = ad.keyboard
    # Captionni xavfsiz olish
    caption = msg.caption if msg.caption else (msg.text if msg.text else "")

    if ad.ad_type == 'ad_type_forward':
        await bot.forward_message(chat_id=chat_id, from_chat_id=msg.chat.id, message_id=msg.message_id)
    else:
        # Barcha turlar uchun (Tugmali yoki Any kontent)
        if msg.content_type == types.ContentType.TEXT:
            await bot.send_message(chat_id, text=caption, reply_markup=kb)
        elif msg.content_type == types.ContentType.PHOTO:
            await bot.send_photo(chat_id, photo=msg.photo[-1].file_id, caption=caption, reply_markup=kb)
        elif msg.content_type == types.ContentType.VIDEO:
            await bot.send_video(chat_id, video=msg.video.file_id, caption=caption, reply_markup=kb)
        elif msg.content_type == types.ContentType.DOCUMENT:
            await bot.send_document(chat_id, document=msg.document.file_id, caption=caption, reply_markup=kb)
        elif msg.content_type == types.ContentType.AUDIO:
            await bot.send_audio(chat_id, audio=msg.audio.file_id, caption=caption, reply_markup=kb)
        elif msg.content_type == types.ContentType.ANIMATION:
            await bot.send_animation(chat_id, animation=msg.animation.file_id, caption=caption, reply_markup=kb)


# --- Handlers ---

@dp.message_handler(commands="reklom")
@dp.message_handler(Text("📣 Reklama"))
async def reklama_handler(message: types.Message):
    if message.from_user.id in ADMINS:  # Bu yerda o'zingizni admin tekshiruvingizni ishlating
        await ReklamaTuriState.tur.set()
        await message.answer("🎯 Reklama turini tanlang:", reply_markup=get_ad_type_keyboard())
    else:
        await message.reply("Sizda ruxsat yo'q.")


@dp.callback_query_handler(lambda c: c.data in ["ad_type_text", "ad_type_forward", "ad_type_button", "ad_type_any"],
                           state=ReklamaTuriState.tur)
async def handle_ad_type(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(ad_type=callback.data)
    await ReklamaTuriState.vaqt.set()
    await callback.message.edit_text("⏳ Vaqtni tanlang:", reply_markup=get_time_keyboard())


@dp.callback_query_handler(lambda c: c.data in ["send_now", "send_later"], state=ReklamaTuriState.vaqt)
async def handle_send_time(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(send_time=callback.data)
    if callback.data == "send_later":
        await ReklamaTuriState.time_value.set()
        await callback.message.edit_text("🕒 Vaqtni kiriting (Masalan: 18:30):")
    else:
        await ReklamaTuriState.content.set()
        await callback.message.edit_text("📥 Reklama kontentini yuboring (Rasm, Matn, Video va h.k.):",
                                         reply_markup=get_cancel_keyboard())


@dp.message_handler(state=ReklamaTuriState.time_value)
async def handle_time_input(message: types.Message, state: FSMContext):
    try:
        t = datetime.datetime.strptime(message.text.strip(), '%H:%M')
        now = datetime.datetime.now()
        send_time = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if send_time < now: send_time += datetime.timedelta(days=1)
        await state.update_data(send_time_value=send_time)
        await ReklamaTuriState.content.set()
        await message.reply("📥 Kontentni yuboring:", reply_markup=get_cancel_keyboard())
    except ValueError:
        await message.reply("❌ Xato! Vaqtni 18:30 formatida yozing.")


@dp.message_handler(state=ReklamaTuriState.content, content_types=types.ContentType.ANY)
async def rek_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get('ad_type') == 'ad_type_button':
        await state.update_data(ad_content=message)
        await ReklamaTuriState.buttons.set()
        await message.answer("🔗 Tugmalarni kiriting:\nFormat: <code>Nom - URL, Nom2 - URL2</code>", parse_mode="HTML")
    else:
        await state.update_data(ad_content=message)
        await message.answer("❓ Reklamani tasdiqlaysizmi?", reply_markup=get_confirm_keyboard())


@dp.message_handler(state=ReklamaTuriState.buttons)
async def handle_buttons_input(message: types.Message, state: FSMContext):
    try:
        kb = types.InlineKeyboardMarkup(row_width=1)
        for b in message.text.split(','):
            txt, url = b.strip().split('-')
            kb.add(types.InlineKeyboardButton(text=txt.strip(), url=url.strip()))
        await state.update_data(keyboard=kb)
        await message.answer("✅ Tugmalar tayyor. Tasdiqlaysizmi?", reply_markup=get_confirm_keyboard())
    except:
        await message.reply("❌ Noto'g'ri format. Qayta yuboring.")


@dp.callback_query_handler(lambda c: c.data == "confirm_ad", state='*')
async def confirm_ad(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ad_id = len(advertisements) + 1
    ad = Advertisement(
        ad_id=ad_id,
        message=data.get('ad_content'),
        ad_type=data.get('ad_type'),
        keyboard=data.get('keyboard'),
        send_time=data.get('send_time_value') if data.get('send_time') == 'send_later' else None,
        creator_id=callback.from_user.id
    )
    advertisements.append(ad)
    await state.finish()
    await callback.message.edit_text(f"✅ Reklama #{ad_id} navbatga qo'shildi.")
    ad.task = asyncio.create_task(ad.start())


@dp.callback_query_handler(lambda c: c.data == "cancel_ad", state='*')
async def cancel_ad(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("❌ Bekor qilindi.")


# Boshqarish tugmalari uchun handlerlar
@dp.callback_query_handler(lambda c: c.data.startswith(("pause_ad_", "resume_ad_", "stop_ad_")))
async def manage_ad(callback: types.CallbackQuery):
    action, _, ad_id = callback.data.split("_")
    ad = next((a for a in advertisements if a.ad_id == int(ad_id)), None)
    if ad:
        if action == "pause":
            await ad.pause()
        elif action == "resume":
            await ad.resume()
        elif action == "stop":
            await ad.stop()
        await callback.answer("Amal bajarildi")
    else:
        await callback.answer("Reklama topilmadi", show_alert=True)


# --- Keyboards ---
def get_ad_type_keyboard():
    return types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton("📝 Matn", callback_data="ad_type_text"),
        types.InlineKeyboardButton("⏩ Forward", callback_data="ad_type_forward"),
        types.InlineKeyboardButton("🔘 Tugmali", callback_data="ad_type_button"),
        types.InlineKeyboardButton("📦 Any", callback_data="ad_type_any")
    )


def get_time_keyboard():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🚀 Hozir", callback_data="send_now"),
        types.InlineKeyboardButton("🕒 Keyinroq", callback_data="send_later")
    )


def get_confirm_keyboard():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("✅ HA", callback_data="confirm_ad"),
        types.InlineKeyboardButton("❌ YO'Q", callback_data="cancel_ad")
    )


def get_cancel_keyboard():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))


def get_status_keyboard(ad_id, paused=False):
    kb = types.InlineKeyboardMarkup()
    if paused:
        kb.add(types.InlineKeyboardButton("▶️ Davom etish", callback_data=f"resume_ad_{ad_id}"))
    else:
        kb.add(types.InlineKeyboardButton("⏸ Pauza", callback_data=f"pause_ad_{ad_id}"))
    kb.add(types.InlineKeyboardButton("🛑 To'xtatish", callback_data=f"stop_ad_{ad_id}"))
    return kb