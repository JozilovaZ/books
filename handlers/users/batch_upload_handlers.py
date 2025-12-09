"""
BATCH UPLOAD - Ko'plab kitob qo'shish funksiyasi
Bu handler admin_handler.py ga qo'shilishi kerak
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
from loader import dp,book_db

# Keyboardlarni import qilish
from keyboards.default.admin_keyboards import (
    batch_upload_menu, continue_or_finish,
    categories_inline_keyboard, books_management_menu
)


# =================== BATCH UPLOAD STATES ===================

class BatchUploadState(StatesGroup):
    """Ko'plab kitob qo'shish uchun state'lar"""
    waiting_for_category = State()
    waiting_for_files = State()
    collecting_books = State()
    waiting_for_title = State()
    waiting_for_author = State()
    waiting_for_narrator = State()
    waiting_for_description = State()


# =================== BATCH UPLOAD HANDLER ===================

@dp.message_handler(Text(equals="📥 Ko'plab kitob qo'shish"))
async def start_batch_upload(message: types.Message, state: FSMContext):
    """Ko'plab kitob qo'shishni boshlash"""

    main_categories = book_db.get_main_categories()

    if not main_categories:
        await message.answer(
            "⚠️ <b>Avval kategoriya qo'shing!</b>",
            reply_markup=books_management_menu()
        )
        return

    keyboard = categories_inline_keyboard(main_categories, action_prefix="batch_main_cat")

    await state.update_data(books_batch=[])  # Bo'sh list yaratish

    await message.answer(
        "📥 <b>Ko'plab kitob qo'shish</b>\n\n"
        "Bu rejimda siz bir necha kitobni ketma-ket qo'shishingiz mumkin.\n\n"
        "📁 Birinchi, barcha kitoblar uchun kategoriyani tanlang:",
        reply_markup=keyboard
    )
    await BatchUploadState.waiting_for_category.set()


@dp.callback_query_handler(lambda c: c.data.startswith("batch_main_cat:"), state=BatchUploadState.waiting_for_category)
async def process_batch_category(callback: types.CallbackQuery, state: FSMContext):
    """Kategoriya tanlash"""
    main_cat_id = int(callback.data.split(":")[1])
    main_cat = book_db.get_category_by_id(main_cat_id)

    subcats = book_db.get_subcategories(main_cat_id)

    if subcats:
        keyboard = categories_inline_keyboard(subcats, action_prefix="batch_sub_cat")
        keyboard.row(types.InlineKeyboardButton(
            f"📁 {main_cat[1]} ga qo'shish",
            callback_data=f"batch_cat_selected:{main_cat_id}"
        ))

        await callback.message.edit_text(
            f"📁 <b>{main_cat[1]}</b>\n\n"
            f"📂 Subkategoriyani tanlang yoki asosiy kategoriyaga qo'shing:",
            reply_markup=keyboard
        )
    else:
        await state.update_data(category_id=main_cat_id)
        await callback.message.edit_text(
            f"✅ Kategoriya: <b>{main_cat[1]}</b>"
        )

        await callback.message.answer(
            "📤 <b>Endi kitoblarni yuklashni boshlang!</b>\n\n"
            "📕 PDF yoki 🎧 Audio fayllarni yuboring.\n"
            "Bir necha faylni ketma-ket yuborishingiz mumkin.\n\n"
            "💡 <i>Har bir fayldan keyin ma'lumotlarni to'ldirasiz.</i>",
            reply_markup=batch_upload_menu()
        )
        await BatchUploadState.collecting_books.set()

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("batch_sub_cat:"), state=BatchUploadState.waiting_for_category)
async def process_batch_subcategory(callback: types.CallbackQuery, state: FSMContext):
    """Subkategoriya tanlash"""
    sub_cat_id = int(callback.data.split(":")[1])
    sub_cat = book_db.get_category_by_id(sub_cat_id)

    await state.update_data(category_id=sub_cat_id)

    path = book_db.get_category_path(sub_cat_id)

    await callback.message.edit_text(
        f"✅ Kategoriya: <b>{path}</b>"
    )

    await callback.message.answer(
        "📤 <b>Endi kitoblarni yuklashni boshlang!</b>\n\n"
        "📕 PDF yoki 🎧 Audio fayllarni yuboring.\n"
        "Bir necha faylni ketma-ket yuborishingiz mumkin.\n\n"
        "💡 <i>Har bir fayldan keyin ma'lumotlarni to'ldirasiz.</i>",
        reply_markup=batch_upload_menu()
    )
    await BatchUploadState.collecting_books.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("batch_cat_selected:"),
                           state=BatchUploadState.waiting_for_category)
async def process_batch_direct_category(callback: types.CallbackQuery, state: FSMContext):
    """To'g'ridan-to'g'ri kategoriya tanlash"""
    cat_id = int(callback.data.split(":")[1])
    cat = book_db.get_category_by_id(cat_id)

    await state.update_data(category_id=cat_id)

    await callback.message.edit_text(
        f"✅ Kategoriya: <b>{cat[1]}</b>"
    )

    await callback.message.answer(
        "📤 <b>Endi kitoblarni yuklashni boshlang!</b>\n\n"
        "📕 PDF yoki 🎧 Audio fayllarni yuboring.\n"
        "Bir necha faylni ketma-ket yuborishingiz mumkin.\n\n"
        "💡 <i>Har bir fayldan keyin ma'lumotlarni to'ldirasiz.</i>",
        reply_markup=batch_upload_menu()
    )
    await BatchUploadState.collecting_books.set()
    await callback.answer()


# =================== FAYLLARNI QABUL QILISH ===================

@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.AUDIO],
                    state=BatchUploadState.collecting_books)
async def collect_book_file(message: types.Message, state: FSMContext):
    """Har bir faylni qabul qilish"""
    file_id = None
    file_size = None
    file_name = None
    file_type = None
    duration = None

    # PDF
    if message.document and message.document.mime_type == 'application/pdf':
        file_id = message.document.file_id
        file_size = message.document.file_size
        file_name = message.document.file_name
        file_type = 'pdf'

    # Audio
    elif message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size
        file_name = message.audio.file_name or message.audio.title or "Audio kitob"
        duration = message.audio.duration
        file_type = 'audio'

    # Audio document
    elif message.document and message.document.mime_type in ['audio/mpeg', 'audio/mp3', 'audio/m4a', 'audio/ogg']:
        file_id = message.document.file_id
        file_size = message.document.file_size
        file_name = message.document.file_name
        file_type = 'audio'

    else:
        await message.answer(
            "⚠️ <b>Noto'g'ri fayl turi!</b>\n\n"
            "Iltimos, PDF yoki Audio fayl yuboring."
        )
        return

    # Hozirgi faylni temporary saqlash
    await state.update_data(
        current_file={
            'file_id': file_id,
            'file_size': file_size,
            'file_name': file_name,
            'file_type': file_type,
            'duration': duration
        }
    )

    emoji = "📕" if file_type == 'pdf' else "🎧"
    type_name = "PDF" if file_type == 'pdf' else "Audio"

    await message.answer(
        f"✅ <b>{type_name} fayl yuklandi!</b>\n"
        f"{emoji} {file_name}\n\n"
        f"📝 Kitob nomini kiriting:",
        reply_markup=batch_upload_menu()
    )
    await BatchUploadState.waiting_for_title.set()


@dp.message_handler(state=BatchUploadState.waiting_for_title)
async def collect_book_title(message: types.Message, state: FSMContext):
    """Kitob nomini qabul qilish"""
    if message.text in ["✅ Yakunlash va saqlash", "❌ Bekor qilish", "📋 Qo'shilganlarni ko'rish"]:
        await handle_batch_menu_actions(message, state)
        return

    title = message.text.strip()
    data = await state.get_data()
    current_file = data['current_file']
    current_file['title'] = title

    await state.update_data(current_file=current_file)

    await message.answer(
        "✍️ <b>Muallif nomini kiriting:</b>\n"
        "<i>Yoki 'O'tkazib yuborish' yuboring</i>",
        reply_markup=batch_upload_menu()
    )
    await BatchUploadState.waiting_for_author.set()


@dp.message_handler(state=BatchUploadState.waiting_for_author)
async def collect_book_author(message: types.Message, state: FSMContext):
    """Muallif nomini qabul qilish"""
    if message.text in ["✅ Yakunlash va saqlash", "❌ Bekor qilish", "📋 Qo'shilganlarni ko'rish"]:
        await handle_batch_menu_actions(message, state)
        return

    author = None if message.text.lower() in ["o'tkazib yuborish", "skip"] else message.text.strip()
    data = await state.get_data()
    current_file = data['current_file']
    current_file['author'] = author

    await state.update_data(current_file=current_file)

    # Agar audio bo'lsa - hikoyachi
    if current_file['file_type'] == 'audio':
        await message.answer(
            "🎙 <b>Hikoyachi nomini kiriting:</b>\n"
            "<i>Yoki 'O'tkazib yuborish' yuboring</i>",
            reply_markup=batch_upload_menu()
        )
        await BatchUploadState.waiting_for_narrator.set()
    else:
        await message.answer(
            "📝 <b>Qisqacha tavsif kiriting:</b>\n"
            "<i>Yoki 'O'tkazib yuborish' yuboring</i>",
            reply_markup=batch_upload_menu()
        )
        await BatchUploadState.waiting_for_description.set()


@dp.message_handler(state=BatchUploadState.waiting_for_narrator)
async def collect_book_narrator(message: types.Message, state: FSMContext):
    """Hikoyachi nomini qabul qilish"""
    if message.text in ["✅ Yakunlash va saqlash", "❌ Bekor qilish", "📋 Qo'shilganlarni ko'rish"]:
        await handle_batch_menu_actions(message, state)
        return

    narrator = None if message.text.lower() in ["o'tkazib yuborish", "skip"] else message.text.strip()
    data = await state.get_data()
    current_file = data['current_file']
    current_file['narrator'] = narrator

    await state.update_data(current_file=current_file)

    await message.answer(
        "📝 <b>Qisqacha tavsif kiriting:</b>\n"
        "<i>Yoki 'O'tkazib yuborish' yuboring</i>",
        reply_markup=batch_upload_menu()
    )
    await BatchUploadState.waiting_for_description.set()


@dp.message_handler(state=BatchUploadState.waiting_for_description)
async def collect_book_description(message: types.Message, state: FSMContext):
    """Tavsifni qabul qilish va kitobni listga qo'shish"""
    if message.text in ["✅ Yakunlash va saqlash", "❌ Bekor qilish", "📋 Qo'shilganlarni ko'rish"]:
        await handle_batch_menu_actions(message, state)
        return

    description = None if message.text.lower() in ["o'tkazib yuborish", "skip"] else message.text.strip()

    data = await state.get_data()
    current_file = data['current_file']
    current_file['description'] = description

    # Kitobni batch listga qo'shish
    books_batch = data.get('books_batch', [])
    books_batch.append(current_file)

    await state.update_data(books_batch=books_batch, current_file=None)

    emoji = "📕" if current_file['file_type'] == 'pdf' else "🎧"

    await message.answer(
        f"✅ <b>Kitob ro'yxatga qo'shildi!</b>\n\n"
        f"{emoji} <b>{current_file['title']}</b>\n"
        f"✍️ {current_file.get('author') or 'Muallif yoq'}\n\n"
        f"📊 <b>Jami qo'shildi:</b> {len(books_batch)} ta kitob\n\n"
        f"Yana kitob qo'shasizmi yoki yakunlaysizmi?",
        reply_markup=continue_or_finish()
    )
    await BatchUploadState.collecting_books.set()

    # =================== MENU ACTIONS ===================

    @ dp.message_handler(Text(equals="➕ Yana qo'shish"), state=BatchUploadState.collecting_books)
    async def continue_batch_upload(message: types.Message, state: FSMContext):
        """Yana kitob qo'shish"""
        data = await state.get_data()
        books_count = len(data.get('books_batch', []))

        await message.answer(
            f"📤 <b>Davom etamiz!</b>\n\n"
            f"📊 Hozircha: {books_count} ta kitob\n\n"
            f"Keyingi faylni yuboring:",
            reply_markup=batch_upload_menu()
        )

    @dp.message_handler(Text(equals="✅ Yakunlash"), state=BatchUploadState.collecting_books)
    async def finish_batch_upload(message: types.Message, state: FSMContext):
        """Batch uploadni yakunlash va saqlash"""
        data = await state.get_data()
        books_batch = data.get('books_batch', [])
        category_id = data.get('category_id')

        if not books_batch:
            await message.answer(
                "⚠️ Hech qanday kitob qo'shilmagan!",
                reply_markup=books_management_menu()
            )
            await state.finish()
            return

        user = user_db.select_user(telegram_id=message.from_user.id)

        success_count = 0
        error_count = 0

        await message.answer(
            f"⏳ <b>{len(books_batch)} ta kitob saqlanmoqda...</b>"
        )

        for book_data in books_batch:
            try:
                book_db.add_book(
                    title=book_data['title'],
                    file_id=book_data['file_id'],
                    category_id=category_id,
                    uploaded_by=user[0],
                    file_type=book_data['file_type'],
                    author=book_data.get('author'),
                    narrator=book_data.get('narrator'),
                    description=book_data.get('description'),
                    duration=book_data.get('duration'),
                    file_size=book_data.get('file_size')
                )
                success_count += 1
                logging.info(f"Batch book added: {book_data['title']}")
            except Exception as e:
                error_count += 1
                logging.error(f"Error adding batch book: {e}")

        category_path = book_db.get_category_path(category_id)

        result_text = (
            f"✅ <b>Batch upload yakunlandi!</b>\n\n"
            f"📁 <b>Kategoriya:</b> {category_path}\n"
            f"✅ <b>Muvaffaqiyatli:</b> {success_count} ta\n"
        )

        if error_count > 0:
            result_text += f"❌ <b>Xatoliklar:</b> {error_count} ta\n"

        await message.answer(result_text, reply_markup=books_management_menu())
        await state.finish()

    @dp.message_handler(Text(equals="📋 Qo'shilganlarni ko'rish"), state=BatchUploadState)
    async def show_batch_books(message: types.Message, state: FSMContext):
        """Qo'shilgan kitoblarni ko'rsatish"""
        data = await state.get_data()
        books_batch = data.get('books_batch', [])

        if not books_batch:
            await message.answer("📭 Hozircha kitoblar qo'shilmagan.")
            return

        text = f"📋 <b>Qo'shilgan kitoblar ({len(books_batch)} ta):</b>\n\n"

        for i, book in enumerate(books_batch, 1):
            emoji = "📕" if book['file_type'] == 'pdf' else "🎧"
            text += f"{i}. {emoji} <b>{book['title']}</b>\n"
            if book.get('author'):
                text += f"   ✍️ {book['author']}\n"
            if book.get('narrator'):
                text += f"   🎙 {book['narrator']}\n"
            text += "\n"

        await message.answer(text)

    async def handle_batch_menu_actions(message: types.Message, state: FSMContext):
        """Batch menyu tugmalarini qayta ishlash"""
        if message.text == "❌ Bekor qilish":
            await state.finish()
            await message.answer("❌ Batch upload bekor qilindi", reply_markup=books_management_menu())

        elif message.text == "✅ Yakunlash va saqlash":
            await finish_batch_upload(message, state)

        elif message.text == "📋 Qo'shilganlarni ko'rish":
            await show_batch_books(message, state)