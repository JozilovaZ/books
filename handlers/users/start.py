"""
User Book Handlers - Professional User Panel
=============================================
Xususiyatlar:
- Yangi BookDatabase bilan ishlaydi (dataclass)
- Yangi keyboards bilan ishlaydi
- Pagination support
- FileType enum
- FTS Search
- Error handling
- Rate limiting ready
- Type hints
- Clean code
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text, CommandStart
from aiogram.dispatcher.filters.state import State, StatesGroup
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from loader import dp, bot, book_db, user_db

# Database imports
from utils.db_api.book_database import (
    Book, Category, PaginatedResult,
    FileType, Statistics
)

# Keyboard imports
from keyboards.default.user_keyboards import (
    # Reply keyboards
    user_main_menu, back_button, cancel_button, back_and_home,
    # Inline keyboards
    categories_keyboard, subcategories_keyboard,
    book_type_keyboard, books_paginated_keyboard, book_detail_keyboard,
    search_type_keyboard, search_results_keyboard,
    popular_keyboard, popular_books_keyboard, recent_books_keyboard,
    close_keyboard,
    # Helpers
    Emoji, CallbackParser, truncate_text, get_book_emoji
)

logger = logging.getLogger(__name__)


# =================== STATES ===================

class SearchState(StatesGroup):
    """Qidiruv holatlari"""
    waiting_query = State()


# =================== CONSTANTS ===================

BOOKS_PER_PAGE = 15
SEARCH_RESULTS_LIMIT = 30
POPULAR_LIMIT = 20
RECENT_LIMIT = 20


# =================== HELPERS ===================

def format_book_info(book: Book, show_category: bool = True) -> str:
    """Kitob ma'lumotlarini formatlash"""
    emoji = get_book_emoji(book.file_type)

    text = f"{emoji} <b>{book.title}</b>\n\n"

    if book.author:
        text += f"✍️ <b>Muallif:</b> {book.author}\n"

    if book.file_type == FileType.AUDIO:
        if book.narrator:
            text += f"🎙 <b>Hikoyachi:</b> {book.narrator}\n"
        if book.duration_formatted:
            text += f"⏱ <b>Davomiylik:</b> {book.duration_formatted}\n"

    if show_category and book.category_name:
        text += f"📁 <b>Kategoriya:</b> {book.category_name}\n"

    if book.file_size_formatted:
        text += f"📦 <b>Hajmi:</b> {book.file_size_formatted}\n"

    text += f"📥 <b>Yuklab olishlar:</b> {book.download_count}\n"

    if book.description:
        desc = truncate_text(book.description, 300)
        text += f"\n📄 <i>{desc}</i>"

    return text


def format_statistics(stats: Statistics) -> str:
    """Statistikani formatlash"""
    return (
        f"📊 <b>Kutubxona statistikasi</b>\n\n"
        f"📁 <b>Kategoriyalar:</b> {stats.total_categories}\n"
        f"├─ Asosiy: {stats.main_categories}\n"
        f"└─ Sub: {stats.total_categories - stats.main_categories}\n\n"
        f"📚 <b>Kitoblar:</b> {stats.total_books}\n"
        f"├─ {Emoji.BOOK_PDF} PDF: {stats.pdf_books}\n"
        f"└─ {Emoji.BOOK_AUDIO} Audio: {stats.audio_books}\n\n"
        f"📥 <b>Jami yuklab olishlar:</b> {stats.total_downloads}"
    )


async def send_book_file(message: types.Message, book: Book) -> bool:
    """Kitob faylini yuborish"""
    try:
        emoji = get_book_emoji(book.file_type)
        caption = f"{emoji} <b>{book.title}</b>"

        if book.author:
            caption += f"\n✍️ {book.author}"

        if book.file_type == FileType.AUDIO:
            if book.narrator:
                caption += f"\n🎙 {book.narrator}"

            await message.answer_audio(
                audio=book.file_id,
                caption=caption,
                duration=book.duration,
                title=book.title,
                performer=book.author
            )
        else:
            await message.answer_document(
                document=book.file_id,
                caption=caption
            )

        # Download count ni oshirish
        book_db.increment_download_count(book.id)
        logger.info(f"Book downloaded: {book.title} (ID: {book.id})")
        return True

    except Exception as e:
        logger.error(f"Error sending book file: {e}")
        return False


async def send_book_file_callback(callback: types.CallbackQuery, book: Book) -> bool:
    """Kitob faylini callback orqali yuborish"""
    try:
        emoji = get_book_emoji(book.file_type)
        caption = f"{emoji} <b>{book.title}</b>"

        if book.author:
            caption += f"\n✍️ {book.author}"

        if book.file_type == FileType.AUDIO:
            if book.narrator:
                caption += f"\n🎙 {book.narrator}"

            await callback.message.answer_audio(
                audio=book.file_id,
                caption=caption,
                duration=book.duration,
                title=book.title,
                performer=book.author
            )
        else:
            await callback.message.answer_document(
                document=book.file_id,
                caption=caption
            )

        # Download count ni oshirish
        book_db.increment_download_count(book.id)
        logger.info(f"Book downloaded: {book.title} (ID: {book.id})")
        return True

    except Exception as e:
        logger.error(f"Error sending book file: {e}")
        return False



# =================== SEARCH CACHE ===================
# Oddiy cache (production da Redis ishlatiladi)
_search_cache: Dict[int, Dict[str, Any]] = {}
_search_id_counter = 0


def cache_search(query: str, user_id: int) -> int:
    """Qidiruv so'rovini cache qilish"""
    global _search_id_counter
    _search_id_counter += 1

    _search_cache[_search_id_counter] = {
        'query': query,
        'user_id': user_id,
        'timestamp': datetime.now()
    }

    # Eski cache larni tozalash (100 dan ortiq bo'lsa)
    if len(_search_cache) > 100:
        oldest_keys = sorted(_search_cache.keys())[:50]
        for key in oldest_keys:
            del _search_cache[key]

    return _search_id_counter


def get_cached_search(search_id: int) -> Optional[str]:
    """Cache dan qidiruv so'rovini olish"""
    if search_id in _search_cache:
        return _search_cache[search_id]['query']
    return None


# =================== START & MAIN MENU ===================

@dp.message_handler(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """Start buyrug'i"""
    # State ni tozalash
    current = await state.get_state()
    if current:
        await state.finish()

    # Foydalanuvchini ro'yxatdan o'tkazish
    user = user_db.select_user(telegram_id=message.from_user.id)
    if not user:
        try:
            user_db.add_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username
            )
            logger.info(f"New user registered: {message.from_user.id}")
        except Exception as e:
            logger.error(f"Error registering user: {e}")

    # Salomlashish
    stats = book_db.get_statistics()

    text = (
        f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
        f"📚 <b>Kutubxona botiga xush kelibsiz!</b>\n\n"
        f"📖 Kitoblar: <b>{stats.total_books}</b>\n"
        f"├─ {Emoji.BOOK_PDF} PDF: {stats.pdf_books}\n"
        f"└─ {Emoji.BOOK_AUDIO} Audio: {stats.audio_books}\n\n"
        f"Quyidagi menyudan foydalaning:"
    )

    await message.answer(text, reply_markup=user_main_menu())


@dp.message_handler(Text(equals=f"{Emoji.HOME} Bosh menyu"))
async def go_home(message: types.Message, state: FSMContext):
    """Bosh menyuga qaytish"""
    current = await state.get_state()
    if current:
        await state.finish()

    await message.answer("🏠 <b>Bosh menyu</b>", reply_markup=user_main_menu())


@dp.message_handler(Text(equals=f"{Emoji.BACK} Orqaga"))
async def go_back(message: types.Message, state: FSMContext):
    """Orqaga (state ni tozalash)"""
    current = await state.get_state()
    if current:
        await state.finish()
        await message.answer("🏠 <b>Bosh menyu</b>", reply_markup=user_main_menu())
    else:
        await message.answer("🏠 <b>Bosh menyu</b>", reply_markup=user_main_menu())


# =================== KATEGORIYALAR ===================

@dp.message_handler(Text(equals=f"{Emoji.FOLDER} Kategoriyalar"))
async def show_categories(message: types.Message):
    """Kategoriyalarni ko'rsatish"""
    categories = book_db.get_categories_with_book_count()
    main_cats = [c for c in categories if c.parent_id is None]

    if not main_cats:
        await message.answer(
            "📭 <b>Kategoriyalar mavjud emas</b>\n\n"
            "Tez orada kitoblar qo'shiladi!",
            reply_markup=user_main_menu()
        )
        return

    text = "📚 <b>Kategoriyalar</b>\n\nQaysi kategoriyadan kitob izlaysiz?"
    keyboard = categories_keyboard(main_cats, prefix="u_cat", show_book_count=True)

    await message.answer(text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("u_cat:"))
async def category_selected(callback: types.CallbackQuery):
    """Kategoriya tanlandi"""
    cat_id = CallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    # Subkategoriyalar bor-yo'qligini tekshirish
    subcats = book_db.get_subcategories(cat_id)

    if subcats:
        # Subkategoriyalarni ko'rsatish
        subcats_with_count = book_db.get_categories_with_book_count()
        subcats_filtered = [c for c in subcats_with_count if c.parent_id == cat_id]

        keyboard = subcategories_keyboard(
            subcats_filtered,
            parent_id=cat_id,
            show_book_count=True
        )

        await callback.message.edit_text(
            f"📂 <b>{category.name}</b>\n\nSubkategoriyani tanlang:",
            reply_markup=keyboard
        )
    else:
        # Kitob turini tanlash
        pdf_count = book_db.count_books_by_category(cat_id, FileType.PDF)
        audio_count = book_db.count_books_by_category(cat_id, FileType.AUDIO)

        keyboard = book_type_keyboard(
            cat_id,
            pdf_count=pdf_count,
            audio_count=audio_count,
            back_callback="u_back:categories"
        )

        await callback.message.edit_text(
            f"📁 <b>{category.name}</b>\n\n"
            f"{Emoji.BOOK_PDF} PDF: {pdf_count} ta\n"
            f"{Emoji.BOOK_AUDIO} Audio: {audio_count} ta\n\n"
            f"Turni tanlang:",
            reply_markup=keyboard
        )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_subcat:"))
async def subcategory_selected(callback: types.CallbackQuery):
    """Subkategoriya tanlandi"""
    sub_id = CallbackParser.get_int_param(callback.data, 0)
    subcategory = book_db.get_category_by_id(sub_id)

    if not subcategory:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    # Kitob turini tanlash
    pdf_count = book_db.count_books_by_category(sub_id, FileType.PDF)
    audio_count = book_db.count_books_by_category(sub_id, FileType.AUDIO)

    path = book_db.get_category_path(sub_id)

    keyboard = book_type_keyboard(
        sub_id,
        pdf_count=pdf_count,
        audio_count=audio_count,
        back_callback=f"u_cat:{subcategory.parent_id}"
    )

    await callback.message.edit_text(
        f"📂 <b>{path}</b>\n\n"
        f"{Emoji.BOOK_PDF} PDF: {pdf_count} ta\n"
        f"{Emoji.BOOK_AUDIO} Audio: {audio_count} ta\n\n"
        f"Turni tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_type:"))
async def book_type_selected(callback: types.CallbackQuery):
    """Kitob turi tanlandi (pdf/audio)"""
    parts = callback.data.split(":")
    file_type_str = parts[1]
    cat_id = int(parts[2])

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO

    # Kitoblarni olish
    result = book_db.get_books(
        category_id=cat_id,
        file_type=file_type,
        page=1,
        per_page=BOOKS_PER_PAGE
    )

    if not result.items:
        await callback.message.edit_text(
            "📭 Bu kategoriyada kitoblar yo'q.",
            reply_markup=book_type_keyboard(cat_id, 0, 0, "back:categories")
        )
        await callback.answer()
        return

    category = book_db.get_category_by_id(cat_id)
    path = book_db.get_category_path(cat_id) if category else "Kategoriya"
    emoji = Emoji.BOOK_PDF if file_type == FileType.PDF else Emoji.BOOK_AUDIO

    keyboard = books_paginated_keyboard(
        result,
        back_callback=f"u_backtype:{cat_id}",
        category_id=cat_id,
        file_type=file_type_str
    )

    await callback.message.edit_text(
        f"{emoji} <b>{path}</b>\n\n"
        f"📚 {result.total} ta kitob topildi.\n"
        f"Yuklab olish uchun tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_pg:"))
async def books_pagination(callback: types.CallbackQuery):
    """Kitoblar pagination"""
    parts = callback.data.split(":")
    page = int(parts[1])
    cat_id = int(parts[2]) if parts[2] != "0" else None
    file_type_str = parts[3] if len(parts) > 3 else "all"

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO if file_type_str == "audio" else None

    result = book_db.get_books(
        category_id=cat_id,
        file_type=file_type,
        page=page,
        per_page=BOOKS_PER_PAGE
    )

    keyboard = books_paginated_keyboard(
        result,
        back_callback=f"u_backtype:{cat_id or 0}",
        category_id=cat_id,
        file_type=file_type_str
    )

    emoji = Emoji.BOOK_PDF if file_type == FileType.PDF else Emoji.BOOK_AUDIO if file_type == FileType.AUDIO else "📚"

    await callback.message.edit_text(
        f"{emoji} Sahifa: {page}/{result.total_pages}\n"
        f"📚 Jami: {result.total} ta",
        reply_markup=keyboard
    )

    await callback.answer()


# =================== KITOB YUKLAB OLISH ===================

@dp.callback_query_handler(lambda c: c.data.startswith("u_dl:"))
async def download_book(callback: types.CallbackQuery):
    """Kitobni yuklab olish"""
    book_id = CallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Kitob topilmadi!", show_alert=True)
        return

    await callback.answer("📥 Yuklanmoqda...")

    success = await send_book_file_callback(callback, book)

    if not success:
        await callback.message.answer(
            "❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."
        )


@dp.callback_query_handler(lambda c: c.data.startswith("u_book:"))
async def show_book_detail(callback: types.CallbackQuery):
    """Kitob tafsilotlari"""
    book_id = CallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Kitob topilmadi!", show_alert=True)
        return

    text = format_book_info(book)
    keyboard = book_detail_keyboard(book)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# =================== QIDIRUV ===================

@dp.message_handler(Text(equals=f"{Emoji.SEARCH} Qidirish"))
async def search_start(message: types.Message, state: FSMContext):
    """Qidiruvni boshlash"""
    await message.answer(
        f"🔍 <b>Qidiruv</b>\n\n"
        f"Kitob nomi, muallif yoki hikoyachi ismini kiriting:\n\n"
        f"<i>Masalan: Python, Alisher Navoiy, audio kitoblar...</i>",
        reply_markup=cancel_button()
    )
    await SearchState.waiting_query.set()


@dp.message_handler(Text(equals=f"{Emoji.CANCEL} Bekor qilish"), state=SearchState.waiting_query)
async def search_cancel(message: types.Message, state: FSMContext):
    """Qidiruvni bekor qilish"""
    await state.finish()
    await message.answer("❌ Qidiruv bekor qilindi", reply_markup=user_main_menu())


@dp.message_handler(state=SearchState.waiting_query)
async def search_process(message: types.Message, state: FSMContext):
    """Qidiruv so'rovini qayta ishlash"""
    query = message.text.strip()

    if len(query) < 2:
        await message.answer(
            "⚠️ Kamida 2 ta belgi kiriting!",
            reply_markup=cancel_button()
        )
        return

    if len(query) > 100:
        query = query[:100]

    # Cache qilish
    search_id = cache_search(query, message.from_user.id)

    # PDF va Audio natijalarni alohida hisoblash
    pdf_result = book_db.search_books(query, file_type=FileType.PDF, page=1, per_page=1)
    audio_result = book_db.search_books(query, file_type=FileType.AUDIO, page=1, per_page=1)

    total = pdf_result.total + audio_result.total

    if total == 0:
        await message.answer(
            f"😔 <b>Hech narsa topilmadi</b>\n\n"
            f"<i>\"{truncate_text(query, 50)}\"</i> bo'yicha natija yo'q.\n\n"
            f"Boshqa so'z bilan qidirib ko'ring.",
            reply_markup=user_main_menu()
        )
        await state.finish()
        return

    keyboard = search_type_keyboard(
        pdf_count=pdf_result.total,
        audio_count=audio_result.total,
        search_id=search_id
    )

    await message.answer(
        f"🔍 <b>Qidiruv natijalari</b>\n\n"
        f"<i>\"{truncate_text(query, 50)}\"</i> bo'yicha {total} ta natija.\n\n"
        f"Turni tanlang:",
        reply_markup=keyboard
    )

    await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("u_stype:"))
async def search_type_selected(callback: types.CallbackQuery):
    """Qidiruv natijasi turi tanlandi"""
    parts = callback.data.split(":")
    file_type_str = parts[1]
    search_id = int(parts[2])

    query = get_cached_search(search_id)
    if not query:
        await callback.answer("⚠️ Qidiruv muddati tugadi. Qaytadan qidiring.", show_alert=True)
        return

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO

    result = book_db.search_books(
        query,
        file_type=file_type,
        page=1,
        per_page=BOOKS_PER_PAGE
    )

    if not result.items:
        await callback.message.edit_text("😔 Natijalar topilmadi.")
        await callback.answer()
        return

    emoji = Emoji.BOOK_PDF if file_type == FileType.PDF else Emoji.BOOK_AUDIO

    keyboard = search_results_keyboard(
        result.items,
        page=1,
        total_pages=result.total_pages,
        search_id=search_id,
        file_type=file_type_str
    )

    await callback.message.edit_text(
        f"{emoji} <b>Qidiruv natijalari</b>\n\n"
        f"<i>\"{truncate_text(query, 40)}\"</i>\n"
        f"📚 {result.total} ta topildi\n\n"
        f"Yuklab olish uchun tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_sp:"))
async def search_pagination(callback: types.CallbackQuery):
    """Qidiruv natijalari pagination"""
    parts = callback.data.split(":")
    page = int(parts[1])
    search_id = int(parts[2])
    file_type_str = parts[3]

    query = get_cached_search(search_id)
    if not query:
        await callback.answer("⚠️ Qidiruv muddati tugadi. Qaytadan qidiring.", show_alert=True)
        return

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO

    result = book_db.search_books(
        query,
        file_type=file_type,
        page=page,
        per_page=BOOKS_PER_PAGE
    )

    keyboard = search_results_keyboard(
        result.items,
        page=page,
        total_pages=result.total_pages,
        search_id=search_id,
        file_type=file_type_str
    )

    emoji = Emoji.BOOK_PDF if file_type == FileType.PDF else Emoji.BOOK_AUDIO

    await callback.message.edit_text(
        f"{emoji} <b>Qidiruv</b> | Sahifa {page}/{result.total_pages}\n"
        f"📚 Jami: {result.total} ta",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_sback:"))
async def search_back_to_types(callback: types.CallbackQuery):
    """Qidiruv turi tanlash sahifasiga qaytish"""
    search_id = CallbackParser.get_int_param(callback.data, 0)

    query = get_cached_search(search_id)
    if not query:
        await callback.answer("⚠️ Qidiruv muddati tugadi.", show_alert=True)
        await callback.message.delete()
        return

    # Qayta hisoblash
    pdf_result = book_db.search_books(query, file_type=FileType.PDF, page=1, per_page=1)
    audio_result = book_db.search_books(query, file_type=FileType.AUDIO, page=1, per_page=1)

    keyboard = search_type_keyboard(
        pdf_count=pdf_result.total,
        audio_count=audio_result.total,
        search_id=search_id
    )

    await callback.message.edit_text(
        f"🔍 <b>Qidiruv natijalari</b>\n\n"
        f"<i>\"{truncate_text(query, 50)}\"</i>\n\n"
        f"Turni tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


# =================== MASHHUR KITOBLAR ===================

@dp.message_handler(Text(equals=f"{Emoji.FIRE} Mashhurlar"))
async def show_popular(message: types.Message):
    """Mashhur kitoblar"""
    pdf_count = book_db.count_books(file_type=FileType.PDF.value)
    audio_count = book_db.count_books(file_type=FileType.AUDIO.value)

    if pdf_count == 0 and audio_count == 0:
        await message.answer(
            "📭 <b>Kitoblar mavjud emas</b>",
            reply_markup=user_main_menu()
        )
        return

    keyboard = popular_keyboard(pdf_count=pdf_count, audio_count=audio_count)

    await message.answer(
        f"🔥 <b>Mashhur kitoblar</b>\n\n"
        f"Eng ko'p yuklab olingan kitoblar.\n"
        f"Turni tanlang:",
        reply_markup=keyboard
    )


@dp.callback_query_handler(lambda c: c.data.startswith("u_popular:"))
async def popular_type_selected(callback: types.CallbackQuery):
    """Mashhur kitoblar turi"""
    file_type_str = CallbackParser.get_param(callback.data, 0)
    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO

    books = book_db.get_popular_books(limit=POPULAR_LIMIT, file_type=file_type)

    if not books:
        await callback.message.edit_text("📭 Kitoblar topilmadi.")
        await callback.answer()
        return

    emoji = Emoji.BOOK_PDF if file_type == FileType.PDF else Emoji.BOOK_AUDIO

    keyboard = popular_books_keyboard(books, file_type_str)

    await callback.message.edit_text(
        f"{emoji} <b>TOP-{len(books)} Mashhur kitoblar</b>\n\n"
        f"Yuklab olish uchun tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


# =================== YANGI KITOBLAR ===================

@dp.message_handler(Text(equals=f"{Emoji.NEW} Yangilar"))
async def show_recent(message: types.Message):
    """Yangi qo'shilgan kitoblar"""
    books = book_db.get_recent_books(limit=RECENT_LIMIT)

    if not books:
        await message.answer(
            "📭 <b>Yangi kitoblar yo'q</b>",
            reply_markup=user_main_menu()
        )
        return

    keyboard = recent_books_keyboard(books)

    await message.answer(
        f"🆕 <b>Yangi qo'shilgan kitoblar</b>\n\n"
        f"So'nggi {len(books)} ta kitob.\n"
        f"Yuklab olish uchun tanlang:",
        reply_markup=keyboard
    )


# =================== STATISTIKA ===================

@dp.message_handler(Text(equals=f"{Emoji.STATS} Statistika"))
async def show_statistics(message: types.Message):
    """Statistikani ko'rsatish"""
    stats = book_db.get_statistics()

    # Foydalanuvchilar soni
    try:
        users_count = user_db.count_users()
        users_text = f"\n\n👥 <b>Foydalanuvchilar:</b> {users_count}"
    except:
        users_text = ""

    text = format_statistics(stats) + users_text

    # TOP 5 kitoblar
    popular = book_db.get_popular_books(5)
    if popular:
        text += "\n\n⭐️ <b>TOP-5 kitoblar:</b>\n"
        for i, book in enumerate(popular, 1):
            emoji = get_book_emoji(book.file_type)
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {emoji} {truncate_text(book.title, 25)} — {book.download_count}\n"

    await message.answer(text, reply_markup=close_keyboard())


# =================== YORDAM ===================

@dp.message_handler(Text(equals=f"{Emoji.HELP} Yordam"))
async def show_help(message: types.Message):
    """Yordam"""
    text = (
        f"ℹ️ <b>Yordam</b>\n\n"
        f"<b>Bot imkoniyatlari:</b>\n\n"
        f"📁 <b>Kategoriyalar</b> — Kitoblarni kategoriyalar bo'yicha ko'rish\n\n"
        f"🔍 <b>Qidirish</b> — Kitob nomi, muallif yoki hikoyachi bo'yicha qidirish\n\n"
        f"🔥 <b>Mashhurlar</b> — Eng ko'p yuklangan kitoblar\n\n"
        f"🆕 <b>Yangilar</b> — So'nggi qo'shilgan kitoblar\n\n"
        f"📊 <b>Statistika</b> — Kutubxona statistikasi\n\n"
        f"<b>Qanday foydalanish:</b>\n"
        f"1. Kategoriya tanlang\n"
        f"2. PDF yoki Audio ni tanlang\n"
        f"3. Kitobni bosing — avtomatik yuklanadi!\n\n"
        f"<b>Savol va takliflar uchun:</b>\n"
        f"@hasanjozilov"
    )

    await message.answer(text, reply_markup=close_keyboard())


# =================== BACK HANDLERS ===================

@dp.callback_query_handler(lambda c: c.data.startswith("u_back:"))
async def back_handler(callback: types.CallbackQuery):
    """Orqaga navigatsiya"""
    target = CallbackParser.get_param(callback.data, 0)

    if target == "main":
        await callback.message.delete()
        await callback.message.answer("🏠 <b>Bosh menyu</b>", reply_markup=user_main_menu())

    elif target == "categories":
        categories = book_db.get_categories_with_book_count()
        main_cats = [c for c in categories if c.parent_id is None]

        keyboard = categories_keyboard(main_cats, prefix="u_cat", show_book_count=True)
        await callback.message.edit_text(
            "📚 <b>Kategoriyalar</b>\n\nQaysi kategoriyadan kitob izlaysiz?",
            reply_markup=keyboard
        )

    elif target == "popular":
        pdf_count = book_db.count_books(file_type=FileType.PDF.value)
        audio_count = book_db.count_books(file_type=FileType.AUDIO.value)

        keyboard = popular_keyboard(pdf_count=pdf_count, audio_count=audio_count)
        await callback.message.edit_text(
            f"🔥 <b>Mashhur kitoblar</b>\n\nTurni tanlang:",
            reply_markup=keyboard
        )

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("u_backtype:"))
async def back_to_type(callback: types.CallbackQuery):
    """Tur tanlash sahifasiga qaytish"""
    cat_id = CallbackParser.get_int_param(callback.data, 0)

    if cat_id == 0:
        # Bosh menyuga
        await callback.message.delete()
        await callback.message.answer("🏠 <b>Bosh menyu</b>", reply_markup=user_main_menu())
        return

    category = book_db.get_category_by_id(cat_id)
    if not category:
        await callback.answer("❌ Kategoriya topilmadi!", show_alert=True)
        return

    pdf_count = book_db.count_books_by_category(cat_id, FileType.PDF)
    audio_count = book_db.count_books_by_category(cat_id, FileType.AUDIO)

    path = book_db.get_category_path(cat_id)

    # Orqaga callback ni aniqlash
    if category.parent_id:
        back_callback = f"cat:{category.parent_id}"
    else:
        back_callback = "back:categories"

    keyboard = book_type_keyboard(
        cat_id,
        pdf_count=pdf_count,
        audio_count=audio_count,
        back_callback=back_callback
    )

    await callback.message.edit_text(
        f"📁 <b>{path}</b>\n\n"
        f"{Emoji.BOOK_PDF} PDF: {pdf_count} ta\n"
        f"{Emoji.BOOK_AUDIO} Audio: {audio_count} ta\n\n"
        f"Turni tanlang:",
        reply_markup=keyboard
    )

    await callback.answer()


# =================== EMPTY & CLOSE ===================

@dp.callback_query_handler(lambda c: c.data in ["u_empty", "u_page_info"])
async def empty_callback(callback: types.CallbackQuery):
    """Bo'sh callback"""
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "u_close")
async def close_callback(callback: types.CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()


# =================== UNKNOWN MESSAGE ===================

@dp.message_handler()
async def unknown_message(message: types.Message, state: FSMContext):
    """Noma'lum xabar"""
    current = await state.get_state()

    if current:
        # State ichida - e'tiborsiz qoldirish
        return

    await message.answer(
        "🤔 Tushunmadim.\n\n"
        "Quyidagi menyudan foydalaning:",
        reply_markup=user_main_menu()
    )