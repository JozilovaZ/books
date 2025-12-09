"""
KITOBNI TAHRIRLASH FUNKSIYASI
Bu handler admin_handler.py ga qo'shilishi kerak
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging


# =================== EDIT STATES ===================

class EditBookState(StatesGroup):
    """Kitobni tahrirlash uchun state'lar"""
    waiting_for_new_title = State()
    waiting_for_new_author = State()
    waiting_for_new_narrator = State()
    waiting_for_new_description = State()
    waiting_for_new_category = State()
    waiting_for_new_file = State()


# =================== KITOBNI TANLASH VA KO'RISH ===================

@dp.message_handler(Text(equals="✏️ Kitobni tahrirlash"))
async def start_edit_book_selection(message: types.Message):
    """Tahrirlanadigan kitobni tanlash"""
    if not await check_admin_permission(message.from_user.id):
        return

    categories = book_db.get_main_categories()

    if not categories:
        await message.answer(
            "📂 Avval kitob qo'shing!",
            reply_markup=books_management_menu()
        )
        return

    keyboard = categories_inline_keyboard(categories, action_prefix="edit_select_cat")

    await message.answer(
        "✏️ <b>Kitobni tahrirlash</b>\n\n"
        "Avval kategoriyani tanlang:",
        reply_markup=keyboard
    )


@dp.callback_query_handler(lambda c: c.data.startswith("edit_select_cat:"))
async def select_category_for_edit(callback: types.CallbackQuery):
    """Kategoriya bo'yicha kitoblarni ko'rsatish"""
    cat_id = int(callback.data.split(":")[1])
    books = book_db.get_books_by_category(cat_id, include_subcategories=True)

    if not books:
        await callback.message.edit_text("📂 Bu kategoriyada kitoblar yo'q!")
        await callback.answer()
        return

    keyboard = books_inline_keyboard(
        books,
        action_prefix="edit_book_view",
        row_width=1,
        back_callback="back_to_edit_cats"
    )

    await callback.message.edit_text(
        "✏️ <b>Tahrirlanadigan kitobni tanlang:</b>",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("edit_book_view:"))
async def view_book_for_edit(callback: types.CallbackQuery):
    """Kitob tafsilotlari va tahrirlash tugmalari"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.message.edit_text("❌ Kitob topilmadi!")
        await callback.answer()
        return

    emoji = "📕" if book[3] == 'pdf' else "🎧"

    text = f"✏️ <b>Tahrirlash: {book[1]}</b>\n\n"
    text += f"{emoji} <b>Hozirgi ma'lumotlar:</b>\n\n"
    text += f"📖 <b>Nom:</b> {book[1]}\n"
    text += f"✍️ <b>Muallif:</b> {book[4] or 'Yo\'q'}\n"

    if book[5]:
        text += f"🎙 <b>Hikoyachi:</b> {book[5]}\n"

    text += f"📁 <b>Kategoriya:</b> {book[-1]}\n"

    if book[9]:
        text += f"📦 <b>Hajmi:</b> {format_file_size(book[9])}\n"

    if book[8]:
        text += f"⏱ <b>Davomiyligi:</b> {format_duration(book[8])}\n"

    text += f"📥 <b>Yuklanishlar:</b> {book[10]} marta\n"

    if book[7]:
        text += f"\n📝 <b>Tavsif:</b>\n<i>{book[7][:200]}...</i>\n"

    text += "\n<b>Nimani o'zgartirmoqchisiz?</b>"

    keyboard = edit_book_menu(book_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# =================== NOMINI O'ZGARTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_title:"))
async def edit_book_title_start(callback: types.CallbackQuery, state: FSMContext):
    """Kitob nomini o'zgartirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id)

    await callback.message.edit_text(
        f"📝 <b>Yangi nomini kiriting:</b>\n\n"
        f"Hozirgi: <i>{book[1]}</i>"
    )

    await callback.message.answer(
        "Yangi nomini yuboring:",
        reply_markup=cancel_button()
    )

    await EditBookState.waiting_for_new_title.set()
    await callback.answer()


@dp.message_handler(state=EditBookState.waiting_for_new_title)
async def edit_book_title_save(message: types.Message, state: FSMContext):
    """Yangi nomini saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=books_management_menu())
        return

    new_title = message.text.strip()
    data = await state.get_data()
    book_id = data['edit_book_id']

    try:
        book_db.update_book_title(book_id, new_title)

        await message.answer(
            f"✅ <b>Kitob nomi yangilandi!</b>\n\n"
            f"📖 Yangi nom: <b>{new_title}</b>",
            reply_markup=books_management_menu()
        )
        logging.info(f"Book title updated: ID {book_id} -> {new_title}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book title: {e}")

    await state.finish()


# =================== MUALLIFNI O'ZGARTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_author:"))
async def edit_book_author_start(callback: types.CallbackQuery, state: FSMContext):
    """Muallif nomini o'zgartirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id)

    await callback.message.edit_text(
        f"✍️ <b>Yangi muallif nomini kiriting:</b>\n\n"
        f"Hozirgi: <i>{book[4] or 'Yo\'q'}</i>"
    )

    await callback.message.answer(
        "Yangi muallif nomini yuboring:",
        reply_markup=skip_button()
    )

    await EditBookState.waiting_for_new_author.set()
    await callback.answer()


@dp.message_handler(state=EditBookState.waiting_for_new_author)
async def edit_book_author_save(message: types.Message, state: FSMContext):
    """Yangi muallifni saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=books_management_menu())
        return

    new_author = None if message.text == "⏭ O'tkazib yuborish" else message.text.strip()
    data = await state.get_data()
    book_id = data['edit_book_id']

    try:
        book_db.update_book_author(book_id, new_author)

        await message.answer(
            f"✅ <b>Muallif yangilandi!</b>\n\n"
            f"✍️ Yangi muallif: <b>{new_author or 'Yo\'q'}</b>",
            reply_markup=books_management_menu()
        )
        logging.info(f"Book author updated: ID {book_id}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book author: {e}")

    await state.finish()


# =================== HIKOYACHINI O'ZGARTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_narrator:"))
async def edit_book_narrator_start(callback: types.CallbackQuery, state: FSMContext):
    """Hikoyachi nomini o'zgartirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id)

    await callback.message.edit_text(
        f"🎙 <b>Yangi hikoyachi nomini kiriting:</b>\n\n"
        f"Hozirgi: <i>{book[5] or 'Yo\'q'}</i>"
    )

    await callback.message.answer(
        "Yangi hikoyachi nomini yuboring:",
        reply_markup=skip_button()
    )

    await EditBookState.waiting_for_new_narrator.set()
    await callback.answer()


@dp.message_handler(state=EditBookState.waiting_for_new_narrator)
async def edit_book_narrator_save(message: types.Message, state: FSMContext):
    """Yangi hikoyachini saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=books_management_menu())
        return

    new_narrator = None if message.text == "⏭ O'tkazib yuborish" else message.text.strip()
    data = await state.get_data()
    book_id = data['edit_book_id']

    try:
        book_db.update_book_narrator(book_id, new_narrator)

        await message.answer(
            f"✅ <b>Hikoyachi yangilandi!</b>\n\n"
            f"🎙 Yangi hikoyachi: <b>{new_narrator or 'Yo\'q'}</b>",
            reply_markup=books_management_menu()
        )
        logging.info(f"Book narrator updated: ID {book_id}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book narrator: {e}")

    await state.finish()


# =================== TAVSIFNI O'ZGARTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_description:"))
async def edit_book_description_start(callback: types.CallbackQuery, state: FSMContext):
    """Tavsifni o'zgartirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id)

    current_desc = book[7] or "Tavsif yo'q"
    preview = current_desc[:200] + "..." if len(current_desc) > 200 else current_desc

    await callback.message.edit_text(
        f"📝 <b>Yangi tavsifni kiriting:</b>\n\n"
        f"Hozirgi tavsif:\n<i>{preview}</i>"
    )

    await callback.message.answer(
        "Yangi tavsifni yuboring:",
        reply_markup=skip_button()
    )

    await EditBookState.waiting_for_new_description.set()
    await callback.answer()


@dp.message_handler(state=EditBookState.waiting_for_new_description)
async def edit_book_description_save(message: types.Message, state: FSMContext):
    """Yangi tavsifni saqlash"""
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=books_management_menu())
        return

    new_description = None if message.text == "⏭ O'tkazib yuborish" else message.text.strip()
    data = await state.get_data()
    book_id = data['edit_book_id']

    try:
        book_db.update_book_description(book_id, new_description)

        await message.answer(
            f"✅ <b>Tavsif yangilandi!</b>",
            reply_markup=books_management_menu()
        )
        logging.info(f"Book description updated: ID {book_id}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book description: {e}")

    await state.finish()


# =================== KATEGORIYANI O'ZGARTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_category:"))
async def edit_book_category_start(callback: types.CallbackQuery, state: FSMContext):
    """Kategoriyani o'zgartirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id)

    categories = book_db.get_main_categories()
    keyboard = categories_inline_keyboard(categories, action_prefix="edit_new_cat")

    await callback.message.edit_text(
        f"📁 <b>Yangi kategoriyani tanlang:</b>\n\n"
        f"Hozirgi: <i>{book[-1]}</i>",
        reply_markup=keyboard
    )
    await EditBookState.waiting_for_new_category.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("edit_new_cat:"), state=EditBookState.waiting_for_new_category)
async def edit_book_category_save(callback: types.CallbackQuery, state: FSMContext):
    """Yangi kategoriyani saqlash"""
    new_cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    book_id = data['edit_book_id']

    # Subkategoriyalar bormi tekshirish
    subcats = book_db.get_subcategories(new_cat_id)

    if subcats:
        # Subkategoriya tanlash
        keyboard = categories_inline_keyboard(subcats, action_prefix="edit_new_subcat")

        new_cat = book_db.get_category_by_id(new_cat_id)
        keyboard.row(types.InlineKeyboardButton(
            f"📁 {new_cat[1]} ga qo'shish",
            callback_data=f"edit_cat_save:{new_cat_id}"
        ))

        await callback.message.edit_text(
            f"📂 Subkategoriyani tanlang:",
            reply_markup=keyboard
        )
    else:
        # To'g'ridan-to'g'ri saqlash
        await save_book_category(callback, book_id, new_cat_id, state)


@dp.callback_query_handler(lambda c: c.data.startswith("edit_new_subcat:"),
                           state=EditBookState.waiting_for_new_category)
async def edit_book_subcategory_select(callback: types.CallbackQuery, state: FSMContext):
    """Subkategoriya tanlash"""
    sub_cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    book_id = data['edit_book_id']

    await save_book_category(callback, book_id, sub_cat_id, state)


@dp.callback_query_handler(lambda c: c.data.startswith("edit_cat_save:"), state=EditBookState.waiting_for_new_category)
async def edit_book_direct_category_save(callback: types.CallbackQuery, state: FSMContext):
    """To'g'ridan-to'g'ri kategoriyaga saqlash"""
    cat_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    book_id = data['edit_book_id']

    await save_book_category(callback, book_id, cat_id, state)


async def save_book_category(callback: types.CallbackQuery, book_id: int, new_cat_id: int, state: FSMContext):
    """Kategoriyani yangilash"""
    try:
        book_db.update_book_category(book_id, new_cat_id)

        new_cat_path = book_db.get_category_path(new_cat_id)

        await callback.message.edit_text(
            f"✅ <b>Kategoriya yangilandi!</b>\n\n"
            f"📁 Yangi kategoriya: <b>{new_cat_path}</b>"
        )

        await callback.message.answer(
            "✅ O'zgarishlar saqlandi",
            reply_markup=books_management_menu()
        )

        logging.info(f"Book category updated: ID {book_id} -> Cat {new_cat_id}")
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book category: {e}")

    await state.finish()
    await callback.answer()


# =================== FAYLNI ALMASHTIRISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("edit_file:"))
async def edit_book_file_start(callback: types.CallbackQuery, state: FSMContext):
    """Faylni almashtirish"""
    book_id = int(callback.data.split(":")[1])
    book = book_db.get_book_by_id(book_id)

    await state.update_data(edit_book_id=book_id, old_file_type=book[3])

    await callback.message.edit_text(
        f"📎 <b>Yangi faylni yuklang:</b>\n\n"
        f"Eski fayl turi: {book[3].upper()}\n\n"
        f"⚠️ <i>Eski fayl o'chiriladi va yangi fayl qo'shiladi.</i>"
    )

    await callback.message.answer(
        "Yangi PDF yoki Audio faylni yuboring:",
        reply_markup=cancel_button()
    )

    await EditBookState.waiting_for_new_file.set()
    await callback.answer()


@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.AUDIO],
                    state=EditBookState.waiting_for_new_file)
async def edit_book_file_save(message: types.Message, state: FSMContext):
    """Yangi faylni saqlash"""
    file_id = None
    file_size = None
    file_type = None
    duration = None

    # PDF
    if message.document and message.document.mime_type == 'application/pdf':
        file_id = message.document.file_id
        file_size = message.document.file_size
        file_type = 'pdf'

    # Audio
    elif message.audio:
        file_id = message.audio.file_id
        file_size = message.audio.file_size
        duration = message.audio.duration
        file_type = 'audio'

    # Audio document
    elif message.document and message.document.mime_type in ['audio/mpeg', 'audio/mp3', 'audio/m4a', 'audio/ogg']:
        file_id = message.document.file_id
        file_size = message.document.file_size
        file_type = 'audio'

    else:
        await message.answer("⚠️ Noto'g'ri fayl turi!")
        return

    data = await state.get_data()
    book_id = data['edit_book_id']

    try:
        book_db.update_book_file(book_id, file_id, file_type, file_size, duration)

        emoji = "📕" if file_type == 'pdf' else "🎧"

        await message.answer(
            f"✅ <b>Fayl almashtirildi!</b>\n\n"
            f"{emoji} Yangi fayl yuklandi",
            reply_markup=books_management_menu()
        )
        logging.info(f"Book file updated: ID {book_id}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=books_management_menu())
        logging.error(f"Error updating book file: {e}")

    await state.finish()


