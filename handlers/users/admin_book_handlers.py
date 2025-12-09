"""
Admin Book Handlers - Professional Admin Panel
==============================================
Xususiyatlar:
- Yangi BookDatabase bilan ishlaydi (dataclass)
- Yangi keyboards bilan ishlaydi
- Pagination support
- Soft delete / restore
- FileType enum
- Error handling
- Type hints
- Clean code (DRY)
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from typing import Optional, List, Union
import logging
import re

from loader import dp, user_db, book_db, bot
from data.config import ADMINS

# Database imports
from utils.db_api.book_database import (
    Book, Category, PaginatedResult,
    FileType, Statistics
)

# Keyboard imports
from keyboards.default.admin_keyboards import (
    # Reply keyboards
    admin_main_menu, admin_category_menu, admin_book_menu,
    admin_cancel_btn, admin_skip_btn, admin_done_btn,
    admin_back_btn, admin_confirm_reply_btn,
    # Inline keyboards
    adm_categories_kb, adm_subcategories_kb, adm_parent_select_kb,
    adm_books_kb, adm_books_paginated_kb, adm_book_actions_kb,
    adm_confirm_kb, adm_book_edit_kb, adm_category_edit_kb,
    adm_file_type_kb, adm_deleted_items_kb, adm_bulk_upload_kb,
    adm_category_actions_kb, adm_stats_kb,
    # Helpers
    AdminEmoji, AdminCallbackParser, truncate_text
)

logger = logging.getLogger(__name__)


# =================== STATES ===================

class AdminCategoryState(StatesGroup):
    """Kategoriya state'lari"""
    select_parent = State()
    enter_name = State()
    enter_description = State()
    edit_name = State()
    edit_description = State()
    edit_parent = State()


class AdminBookState(StatesGroup):
    """Bitta kitob qo'shish"""
    select_category = State()
    select_subcategory = State()
    upload_file = State()
    enter_title = State()
    enter_author = State()
    enter_narrator = State()
    enter_description = State()


class AdminBulkState(StatesGroup):
    """Bulk yuklash"""
    select_category = State()
    select_subcategory = State()
    uploading = State()


class AdminSearchState(StatesGroup):
    """Qidiruv"""
    enter_query = State()


class AdminEditBookState(StatesGroup):
    """Kitob tahrirlash"""
    edit_title = State()
    edit_author = State()
    edit_narrator = State()
    edit_description = State()
    edit_category = State()
    edit_file = State()


# =================== CONSTANTS ===================

BOOKS_PER_PAGE = 15
SEARCH_RESULTS_LIMIT = 20


# =================== HELPERS ===================

async def is_admin(user_id: int) -> bool:
    """Admin tekshirish"""
    # Config dagi ADMINS ro'yxatidan tekshirish
    if user_id in ADMINS:
        return True

    # Database dan tekshirish
    user = user_db.select_user(telegram_id=user_id)
    if user:
        # user[0] = id (database id)
        return user_db.check_if_admin(user_id=user[0])
    return False


def get_user_db_id(telegram_id: int) -> Optional[int]:
    """Telegram ID dan database ID olish"""
    user = user_db.select_user(telegram_id=telegram_id)
    return user[0] if user else None


def format_book_info(book: Book, detailed: bool = False) -> str:
    """Kitob ma'lumotlarini formatlash"""
    emoji = AdminEmoji.BOOK_PDF if book.file_type == FileType.PDF else AdminEmoji.BOOK_AUDIO

    text = f"{emoji} <b>{book.title}</b>\n\n"
    text += f"✍️ Muallif: {book.author or '—'}\n"

    if book.file_type == FileType.AUDIO:
        text += f"🎙 Hikoyachi: {book.narrator or '—'}\n"
        text += f"⏱ Davomiylik: {book.duration_formatted or '—'}\n"

    text += f"📁 Kategoriya: {book.category_name or '—'}\n"
    text += f"📦 Hajmi: {book.file_size_formatted or '—'}\n"
    text += f"📥 Yuklab olishlar: {book.download_count}\n"

    if detailed and book.description:
        text += f"\n📄 <i>{truncate_text(book.description, 200)}</i>"

    return text


def format_category_info(category: Category, book_count: int = 0) -> str:
    """Kategoriya ma'lumotlarini formatlash"""
    text = f"📁 <b>{category.name}</b>\n\n"
    text += f"📄 Tavsif: {category.description or '—'}\n"
    text += f"📚 Kitoblar: {book_count} ta\n"

    if category.parent_id:
        path = book_db.get_category_path(category.id)
        text += f"📂 Yo'l: {path}\n"

    return text


def parse_caption(caption: str, file_name: str = None) -> dict:
    """Caption'dan ma'lumot olish"""
    result = {'title': None, 'author': None, 'narrator': None, 'description': None}

    if not caption:
        if file_name:
            result['title'] = re.sub(r'\.(pdf|mp3|m4a|m4b|ogg|wav|flac)$', '', file_name, flags=re.IGNORECASE).strip()
        return result

    caption = caption.strip()

    if '\n' in caption:
        lines = caption.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^(kitob|nom|title)\s*:', line, re.IGNORECASE):
                result['title'] = re.sub(r'^(kitob|nom|title)\s*:\s*', '', line, flags=re.IGNORECASE)
            elif re.match(r'^(muallif|author|yozuvchi)\s*:', line, re.IGNORECASE):
                result['author'] = re.sub(r'^(muallif|author|yozuvchi)\s*:\s*', '', line, flags=re.IGNORECASE)
            elif re.match(r'^(hikoyachi|narrator)\s*:', line, re.IGNORECASE):
                result['narrator'] = re.sub(r'^(hikoyachi|narrator)\s*:\s*', '', line, flags=re.IGNORECASE)
            elif re.match(r'^(tavsif|description)\s*:', line, re.IGNORECASE):
                result['description'] = re.sub(r'^(tavsif|description)\s*:\s*', '', line, flags=re.IGNORECASE)
            elif not result['title']:
                result['title'] = line
    elif '|' in caption:
        parts = [p.strip() for p in caption.split('|')]
        if len(parts) >= 1 and parts[0]:
            result['title'] = parts[0]
        if len(parts) >= 2 and parts[1]:
            result['author'] = parts[1]
        if len(parts) >= 3 and parts[2]:
            result['narrator'] = parts[2]
    else:
        result['title'] = caption

    if not result['title'] and file_name:
        result['title'] = re.sub(r'\.(pdf|mp3|m4a|m4b|ogg|wav|flac)$', '', file_name, flags=re.IGNORECASE).strip()

    return result


def extract_file_data(message: types.Message) -> Optional[dict]:
    """Fayldan ma'lumot olish"""
    if message.document:
        mime = message.document.mime_type or ''
        if mime == 'application/pdf':
            return {
                'file_id': message.document.file_id,
                'file_size': message.document.file_size,
                'file_name': message.document.file_name or "Document.pdf",
                'file_type': FileType.PDF,
                'duration': None
            }
        if mime.startswith('audio/'):
            return {
                'file_id': message.document.file_id,
                'file_size': message.document.file_size,
                'file_name': message.document.file_name or "Audio",
                'file_type': FileType.AUDIO,
                'duration': None
            }

    if message.audio:
        return {
            'file_id': message.audio.file_id,
            'file_size': message.audio.file_size,
            'file_name': message.audio.file_name or message.audio.title or "Audio",
            'file_type': FileType.AUDIO,
            'duration': message.audio.duration
        }

    return None


async def send_book_file(message: types.Message, book: Book, caption: str = None) -> bool:
    """Kitob faylini yuborish"""
    try:
        if caption is None:
            emoji = AdminEmoji.BOOK_PDF if book.file_type == FileType.PDF else AdminEmoji.BOOK_AUDIO
            caption = f"{emoji} {book.title}"

        if book.file_type == FileType.PDF:
            await message.answer_document(document=book.file_id, caption=caption)
        else:
            await message.answer_audio(audio=book.file_id, caption=caption, duration=book.duration, title=book.title,
                                       performer=book.author)
        return True
    except Exception as e:
        logger.error(f"Error sending book file: {e}")
        return False


# =================== MAIN MENU ===================

@dp.message_handler(commands="admin")
async def admin_panel(message: types.Message):
    """Admin panel"""
    if not await is_admin(message.from_user.id):
        await message.answer("🚫 Sizda ruxsat yo'q!")
        return

    stats = book_db.get_statistics()

    text = (
        f"👨‍💼 <b>Admin Panel</b>\n\n"
        f"📁 Kategoriyalar: {stats.total_categories}\n"
        f"📖 Kitoblar: {stats.total_books}\n"
        f"├─ {AdminEmoji.BOOK_PDF} PDF: {stats.pdf_books}\n"
        f"└─ {AdminEmoji.BOOK_AUDIO} Audio: {stats.audio_books}\n"
        f"📥 Jami yuklab olishlar: {stats.total_downloads}\n"
    )

    if stats.deleted_books > 0 or stats.deleted_categories > 0:
        text += f"\n🗑 O'chirilgan: {stats.deleted_books} kitob, {stats.deleted_categories} kategoriya"

    await message.answer(text, reply_markup=admin_main_menu())


@dp.message_handler(Text(equals=f"{AdminEmoji.BACK} Admin menyu"))
async def back_to_admin_menu(message: types.Message, state: FSMContext):
    """Admin menyuga qaytish"""
    if not await is_admin(message.from_user.id):
        return

    current = await state.get_state()
    if current:
        await state.finish()

    await message.answer("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_main_menu())


@dp.message_handler(Text(equals=f"{AdminEmoji.HOME} Bosh menyu"))
async def go_home(message: types.Message, state: FSMContext):
    """Bosh menyuga"""
    current = await state.get_state()
    if current:
        await state.finish()

    from keyboards.default.user_keyboards import user_main_menu
    await message.answer("🏠 Bosh menyu", reply_markup=user_main_menu())


# =================== KATEGORIYALAR BO'LIMI ===================

@dp.message_handler(Text(equals="🗂 Kategoriyalar boshqaruvi"))
async def categories_section(message: types.Message):
    """Kategoriyalar bo'limi"""
    if not await is_admin(message.from_user.id):
        return
    await message.answer("📁 <b>Kategoriyalar boshqaruvi</b>", reply_markup=admin_category_menu())


@dp.message_handler(Text(equals=f"{AdminEmoji.ADD} Kategoriya"))
async def add_category_start(message: types.Message, state: FSMContext):
    """Kategoriya qo'shish"""
    if not await is_admin(message.from_user.id):
        return

    main_cats = book_db.get_main_categories()

    if main_cats:
        keyboard = adm_parent_select_kb(main_cats, allow_root=True)
        await message.answer(
            f"{AdminEmoji.ADD} <b>Yangi kategoriya</b>\n\n"
            "Subkategoriya bo'lsa — asosiy kategoriyani tanlang.\n"
            "Yoki 'Asosiy kategoriya' tugmasini bosing:",
            reply_markup=keyboard
        )
        await AdminCategoryState.select_parent.set()
    else:
        await state.update_data(parent_id=None)
        await message.answer("📝 <b>Kategoriya nomini kiriting:</b>", reply_markup=admin_cancel_btn())
        await AdminCategoryState.enter_name.set()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_parent:"), state=AdminCategoryState.select_parent)
async def category_parent_selected(callback: types.CallbackQuery, state: FSMContext):
    """Parent tanlandi"""
    parent_id = AdminCallbackParser.get_int_param(callback.data, 0)

    if parent_id == 0:
        parent_id = None
        await callback.message.edit_text(f"📁 <b>Asosiy kategoriya yaratiladi</b>")
    else:
        parent = book_db.get_category_by_id(parent_id)
        if parent:
            await callback.message.edit_text(f"📂 <b>'{parent.name}'</b> ichiga subkategoriya")

    await state.update_data(parent_id=parent_id)
    await callback.message.answer("📝 <b>Kategoriya nomini kiriting:</b>", reply_markup=admin_cancel_btn())
    await AdminCategoryState.enter_name.set()
    await callback.answer()


@dp.message_handler(state=AdminCategoryState.enter_name)
async def category_name_entered(message: types.Message, state: FSMContext):
    """Kategoriya nomi kiritildi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_category_menu())
        return

    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("⚠️ Nom 2-100 belgi oralig'ida bo'lsin:")
        return

    data = await state.get_data()
    existing = book_db.get_category_by_name(name, data.get('parent_id'))
    if existing:
        await message.answer("⚠️ Bu nom allaqachon mavjud! Boshqa nom kiriting:")
        return

    await state.update_data(cat_name=name)
    await message.answer("📄 <b>Tavsif kiriting:</b>\n<i>(Yoki o'tkazib yuboring)</i>", reply_markup=admin_skip_btn())
    await AdminCategoryState.enter_description.set()


@dp.message_handler(state=AdminCategoryState.enter_description)
async def category_desc_entered(message: types.Message, state: FSMContext):
    """Kategoriya tavsifi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_category_menu())
        return

    description = None
    if message.text != f"{AdminEmoji.SKIP} O'tkazish":
        description = message.text.strip()[:500]

    data = await state.get_data()
    user_id = get_user_db_id(message.from_user.id)

    if not user_id:
        await message.answer("❌ Foydalanuvchi topilmadi!", reply_markup=admin_category_menu())
        await state.finish()
        return

    try:
        cat_id = book_db.add_category(
            name=data['cat_name'],
            created_by=user_id,
            description=description,
            parent_id=data.get('parent_id')
        )
        path = book_db.get_category_path(cat_id)
        await message.answer(f"✅ <b>Kategoriya qo'shildi!</b>\n\n📁 {path}\n📄 {description or '—'}",
                             reply_markup=admin_category_menu())
        logger.info(f"Category added: {data['cat_name']} by user {message.from_user.id}")
    except ValueError as e:
        await message.answer(f"⚠️ {e}", reply_markup=admin_category_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}", reply_markup=admin_category_menu())
        logger.error(f"Error adding category: {e}")

    await state.finish()


@dp.message_handler(Text(equals=f"{AdminEmoji.LIST} Ro'yxat"))
async def list_categories(message: types.Message):
    """Kategoriyalar ro'yxati"""
    if not await is_admin(message.from_user.id):
        return

    categories = book_db.get_categories_with_book_count()
    main_cats = [c for c in categories if c.parent_id is None]

    if not main_cats:
        await message.answer("📂 Kategoriyalar yo'q.", reply_markup=admin_category_menu())
        return

    text = "📚 <b>Kategoriyalar:</b>\n\n"
    for i, cat in enumerate(main_cats, 1):
        text += f"{i}. 📁 <b>{cat.name}</b> — {cat.book_count} ta\n"
        if cat.description:
            text += f"   <i>{truncate_text(cat.description, 50)}</i>\n"
        subcats = [c for c in categories if c.parent_id == cat.id]
        for sub in subcats:
            text += f"   └─ 📂 {sub.name} — {sub.book_count} ta\n"
        text += "\n"

    await message.answer(text, reply_markup=admin_category_menu())


# =================== KITOBLAR BO'LIMI ===================

@dp.message_handler(Text(equals="📚 Kitoblar boshqaruvi"))
async def books_section(message: types.Message):
    """Kitoblar bo'limi"""
    if not await is_admin(message.from_user.id):
        return
    await message.answer("📖 <b>Kitoblar boshqaruvi</b>", reply_markup=admin_book_menu())


@dp.message_handler(Text(equals=f"{AdminEmoji.UPLOAD} Kitob yuklash"))
async def add_book_start(message: types.Message, state: FSMContext):
    """Bitta kitob qo'shish"""
    if not await is_admin(message.from_user.id):
        return

    main_cats = book_db.get_main_categories()
    if not main_cats:
        await message.answer("⚠️ Avval kategoriya qo'shing!", reply_markup=admin_book_menu())
        return

    keyboard = adm_categories_kb(main_cats, prefix="adm_add_cat", back_callback="adm_back:book_menu")
    await message.answer("📁 <b>Kategoriyani tanlang:</b>", reply_markup=keyboard)
    await AdminBookState.select_category.set()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_add_cat:"), state=AdminBookState.select_category)
async def add_book_category(callback: types.CallbackQuery, state: FSMContext):
    """Kategoriya tanlandi"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    subcats = book_db.get_subcategories(cat_id)

    if subcats:
        keyboard = adm_subcategories_kb(subcats, parent_id=cat_id, prefix="adm_add_sub", allow_direct=True)
        await callback.message.edit_text(f"📁 <b>{category.name}</b>\n\nSubkategoriyani tanlang:", reply_markup=keyboard)
        await state.update_data(parent_cat_id=cat_id)
        await AdminBookState.select_subcategory.set()
    else:
        await state.update_data(category_id=cat_id, category_name=category.name)
        await callback.message.edit_text(f"✅ Kategoriya: <b>{category.name}</b>")
        await callback.message.answer(
            f"📤 <b>Faylni yuklang:</b>\n• {AdminEmoji.BOOK_PDF} PDF\n• {AdminEmoji.BOOK_AUDIO} Audio",
            reply_markup=admin_cancel_btn()
        )
        await AdminBookState.upload_file.set()

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_add_sub:"), state=AdminBookState.select_subcategory)
async def add_book_subcategory(callback: types.CallbackQuery, state: FSMContext):
    """Subkategoriya tanlandi"""
    sub_id = AdminCallbackParser.get_int_param(callback.data, 0)
    subcategory = book_db.get_category_by_id(sub_id)

    if not subcategory:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    path = book_db.get_category_path(sub_id)
    await state.update_data(category_id=sub_id, category_name=path)
    await callback.message.edit_text(f"✅ Kategoriya: <b>{path}</b>")
    await callback.message.answer(
        f"📤 <b>Faylni yuklang:</b>\n• {AdminEmoji.BOOK_PDF} PDF\n• {AdminEmoji.BOOK_AUDIO} Audio",
        reply_markup=admin_cancel_btn()
    )
    await AdminBookState.upload_file.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_add_sub_direct:"), state=AdminBookState.select_subcategory)
async def add_book_direct_category(callback: types.CallbackQuery, state: FSMContext):
    """To'g'ridan-to'g'ri kategoriyaga"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    await state.update_data(category_id=cat_id, category_name=category.name)
    await callback.message.edit_text(f"✅ Kategoriya: <b>{category.name}</b>")
    await callback.message.answer(
        f"📤 <b>Faylni yuklang:</b>\n• {AdminEmoji.BOOK_PDF} PDF\n• {AdminEmoji.BOOK_AUDIO} Audio",
        reply_markup=admin_cancel_btn()
    )
    await AdminBookState.upload_file.set()
    await callback.answer()


@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.AUDIO],
                    state=AdminBookState.upload_file)
async def add_book_file(message: types.Message, state: FSMContext):
    """Fayl yuklandi"""
    file_data = extract_file_data(message)

    if not file_data:
        await message.answer("⚠️ Faqat PDF yoki Audio fayl yuboring!")
        return

    existing = book_db.get_book_by_file_id(file_data['file_id'])
    if existing:
        await message.answer(f"⚠️ Bu fayl allaqachon mavjud!\n📖 {existing.title}")
        return

    await state.update_data(**file_data)
    emoji = AdminEmoji.BOOK_PDF if file_data['file_type'] == FileType.PDF else AdminEmoji.BOOK_AUDIO

    await message.answer(
        f"✅ <b>Fayl qabul qilindi!</b>\n{emoji} {file_data['file_name']}\n\n📝 <b>Kitob nomini kiriting:</b>",
        reply_markup=admin_cancel_btn())
    await AdminBookState.enter_title.set()


@dp.message_handler(state=AdminBookState.enter_title)
async def add_book_title(message: types.Message, state: FSMContext):
    """Kitob nomi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    title = message.text.strip()
    if len(title) < 2 or len(title) > 255:
        await message.answer("⚠️ Nom 2-255 belgi oralig'ida bo'lsin:")
        return

    await state.update_data(title=title)
    await message.answer("✍️ <b>Muallif:</b>", reply_markup=admin_skip_btn())
    await AdminBookState.enter_author.set()


@dp.message_handler(state=AdminBookState.enter_author)
async def add_book_author(message: types.Message, state: FSMContext):
    """Muallif"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    author = None
    if message.text != f"{AdminEmoji.SKIP} O'tkazish":
        author = message.text.strip()[:100]

    await state.update_data(author=author)
    data = await state.get_data()

    if data['file_type'] == FileType.AUDIO:
        await message.answer("🎙 <b>Hikoyachi:</b>", reply_markup=admin_skip_btn())
        await AdminBookState.enter_narrator.set()
    else:
        await message.answer("📄 <b>Tavsif:</b>", reply_markup=admin_skip_btn())
        await AdminBookState.enter_description.set()


@dp.message_handler(state=AdminBookState.enter_narrator)
async def add_book_narrator(message: types.Message, state: FSMContext):
    """Hikoyachi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    narrator = None
    if message.text != f"{AdminEmoji.SKIP} O'tkazish":
        narrator = message.text.strip()[:100]

    await state.update_data(narrator=narrator)
    await message.answer("📄 <b>Tavsif:</b>", reply_markup=admin_skip_btn())
    await AdminBookState.enter_description.set()


@dp.message_handler(state=AdminBookState.enter_description)
async def add_book_description(message: types.Message, state: FSMContext):
    """Tavsif va saqlash"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    description = None
    if message.text != f"{AdminEmoji.SKIP} O'tkazish":
        description = message.text.strip()[:1000]

    data = await state.get_data()
    user_id = get_user_db_id(message.from_user.id)

    if not user_id:
        await message.answer("❌ Foydalanuvchi topilmadi!", reply_markup=admin_book_menu())
        await state.finish()
        return

    try:
        book_id = book_db.add_book(
            title=data['title'],
            file_id=data['file_id'],
            category_id=data['category_id'],
            uploaded_by=user_id,
            file_type=data['file_type'],
            author=data.get('author'),
            narrator=data.get('narrator'),
            description=description,
            duration=data.get('duration'),
            file_size=data.get('file_size')
        )

        emoji = AdminEmoji.BOOK_PDF if data['file_type'] == FileType.PDF else AdminEmoji.BOOK_AUDIO
        await message.answer(
            f"✅ <b>Kitob qo'shildi!</b>\n\n{emoji} {data['title']}\n✍️ {data.get('author') or '—'}\n📁 {data['category_name']}",
            reply_markup=admin_book_menu()
        )
        logger.info(f"Book added: {data['title']} (ID: {book_id})")
    except ValueError as e:
        await message.answer(f"⚠️ {e}", reply_markup=admin_book_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}", reply_markup=admin_book_menu())
        logger.error(f"Error adding book: {e}")

    await state.finish()


# =================== BULK YUKLASH ===================

@dp.message_handler(Text(equals=f"{AdminEmoji.BULK} Bulk yuklash"))
async def bulk_upload_start(message: types.Message, state: FSMContext):
    """Bulk yuklashni boshlash"""
    if not await is_admin(message.from_user.id):
        return

    main_cats = book_db.get_main_categories()
    if not main_cats:
        await message.answer("⚠️ Avval kategoriya qo'shing!", reply_markup=admin_book_menu())
        return

    keyboard = adm_categories_kb(main_cats, prefix="adm_bulk_cat", back_callback="adm_back:book_menu")
    await message.answer(f"📦 <b>Bulk yuklash</b>\n\n📁 Kategoriyani tanlang:", reply_markup=keyboard)
    await AdminBulkState.select_category.set()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_bulk_cat:"), state=AdminBulkState.select_category)
async def bulk_category_selected(callback: types.CallbackQuery, state: FSMContext):
    """Bulk uchun kategoriya"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    subcats = book_db.get_subcategories(cat_id)

    if subcats:
        keyboard = adm_subcategories_kb(subcats, parent_id=cat_id, prefix="adm_bulk_sub", allow_direct=True)
        await callback.message.edit_text(f"📁 <b>{category.name}</b>\n\nSubkategoriyani tanlang:", reply_markup=keyboard)
        await state.update_data(parent_cat_id=cat_id)
        await AdminBulkState.select_subcategory.set()
    else:
        await state.update_data(category_id=cat_id, category_name=category.name, books_queue=[], errors=[])
        await callback.message.edit_text(f"✅ Kategoriya: <b>{category.name}</b>")
        await _send_bulk_instructions(callback.message)
        await AdminBulkState.uploading.set()

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_bulk_sub:"), state=AdminBulkState.select_subcategory)
async def bulk_subcategory_selected(callback: types.CallbackQuery, state: FSMContext):
    """Bulk uchun subkategoriya"""
    sub_id = AdminCallbackParser.get_int_param(callback.data, 0)
    subcategory = book_db.get_category_by_id(sub_id)

    if not subcategory:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    path = book_db.get_category_path(sub_id)
    await state.update_data(category_id=sub_id, category_name=path, books_queue=[], errors=[])
    await callback.message.edit_text(f"✅ Kategoriya: <b>{path}</b>")
    await _send_bulk_instructions(callback.message)
    await AdminBulkState.uploading.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_bulk_sub_direct:"), state=AdminBulkState.select_subcategory)
async def bulk_direct_category(callback: types.CallbackQuery, state: FSMContext):
    """Bulk uchun asosiy kategoriyaga"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    await state.update_data(category_id=cat_id, category_name=category.name, books_queue=[], errors=[])
    await callback.message.edit_text(f"✅ Kategoriya: <b>{category.name}</b>")
    await _send_bulk_instructions(callback.message)
    await AdminBulkState.uploading.set()
    await callback.answer()


async def _send_bulk_instructions(message: types.Message):
    """Bulk yuklash ko'rsatmalari"""
    await message.answer(
        f"📤 <b>Fayllarni yuboring!</b>\n\n"
        f"• {AdminEmoji.BOOK_PDF} PDF yoki {AdminEmoji.BOOK_AUDIO} Audio\n"
        f"• Caption'dan ma'lumot olinadi\n"
        f"• Tugatgach '{AdminEmoji.DONE} Tugatish' bosing\n\n"
        f"<b>Caption formatlari:</b>\n"
        f"<code>Kitob nomi | Muallif</code>\n"
        f"<code>Kitob nomi | Muallif | Hikoyachi</code>",
        reply_markup=admin_done_btn()
    )


@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.AUDIO], state=AdminBulkState.uploading)
async def bulk_receive_file(message: types.Message, state: FSMContext):
    """Bulk - fayl qabul qilish"""
    file_data = extract_file_data(message)
    if not file_data:
        return

    existing = book_db.get_book_by_file_id(file_data['file_id'])
    if existing:
        data = await state.get_data()
        errors = data.get('errors', [])
        errors.append(f"Dublikat: {existing.title}")
        await state.update_data(errors=errors)
        await message.reply(f"⚠️ Dublikat! <i>{existing.title}</i>")
        return

    caption = message.caption
    if not caption and message.audio:
        caption = message.audio.title

    parsed = parse_caption(caption, file_data['file_name'])

    book_info = {
        'file_id': file_data['file_id'],
        'file_type': file_data['file_type'],
        'file_size': file_data['file_size'],
        'duration': file_data['duration'],
        'title': parsed['title'] or file_data['file_name'],
        'author': parsed['author'],
        'narrator': parsed['narrator'],
        'description': parsed['description']
    }

    data = await state.get_data()
    queue = data.get('books_queue', [])
    queue.append(book_info)
    await state.update_data(books_queue=queue)

    emoji = AdminEmoji.BOOK_PDF if file_data['file_type'] == FileType.PDF else AdminEmoji.BOOK_AUDIO
    await message.reply(
        f"✅ #{len(queue)} {emoji} <b>{truncate_text(book_info['title'], 40)}</b>\n✍️ {book_info['author'] or '—'}")


@dp.message_handler(Text(equals=f"{AdminEmoji.DONE} Tugatish"), state=AdminBulkState.uploading)
async def bulk_finish(message: types.Message, state: FSMContext):
    """Bulk yuklashni tugatish"""
    data = await state.get_data()
    queue = data.get('books_queue', [])
    errors = data.get('errors', [])

    if not queue:
        await message.answer("⚠️ Hech qanday fayl yuklanmadi!", reply_markup=admin_book_menu())
        await state.finish()
        return

    user_id = get_user_db_id(message.from_user.id)
    if not user_id:
        await message.answer("❌ Foydalanuvchi topilmadi!", reply_markup=admin_book_menu())
        await state.finish()
        return

    category_id = data['category_id']
    progress_msg = await message.answer(f"⏳ Yuklanmoqda... 0/{len(queue)}")

    books_list = []
    for book in queue:
        books_list.append((
            book['title'], book['file_id'], book['file_type'].value, category_id,
            book['author'], book['narrator'], book['description'],
            book['duration'], book['file_size'], user_id
        ))

    try:
        added_count, error_count = book_db.add_books_bulk(books_list)
        await progress_msg.delete()

        pdf_count = len([b for b in queue if b['file_type'] == FileType.PDF])
        audio_count = len([b for b in queue if b['file_type'] == FileType.AUDIO])

        text = f"🎉 <b>Bulk yuklash tugadi!</b>\n\n✅ Qo'shildi: <b>{added_count}</b> ta kitob\n"
        if error_count > 0:
            text += f"❌ Xatolar: {error_count}\n"
        text += f"\n{AdminEmoji.BOOK_PDF} PDF: {pdf_count}\n{AdminEmoji.BOOK_AUDIO} Audio: {audio_count}\n📁 Kategoriya: {data['category_name']}"

        if errors:
            text += f"\n\n⚠️ <b>Xatolar:</b>\n" + "\n".join(f"• {e}" for e in errors[:5])

        await message.answer(text, reply_markup=admin_book_menu())
        logger.info(f"Bulk upload: {added_count} books to category {category_id}")
    except Exception as e:
        await progress_msg.delete()
        await message.answer(f"❌ Xatolik: {e}", reply_markup=admin_book_menu())
        logger.error(f"Bulk upload error: {e}")

    await state.finish()


# =================== KITOBLAR RO'YXATI ===================

@dp.message_handler(Text(equals=f"{AdminEmoji.LIST} Kitoblar"))
async def list_books(message: types.Message):
    """Kitoblar ro'yxati"""
    if not await is_admin(message.from_user.id):
        return

    categories = book_db.get_categories_with_book_count()
    main_cats = [c for c in categories if c.parent_id is None]

    if not main_cats:
        await message.answer("📂 Kategoriyalar yo'q.", reply_markup=admin_book_menu())
        return

    keyboard = adm_categories_kb(main_cats, prefix="adm_list_cat", show_book_count=True,
                                 back_callback="adm_back:book_menu")
    await message.answer("📁 <b>Kategoriyani tanlang:</b>", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("adm_list_cat:"))
async def list_books_category(callback: types.CallbackQuery):
    """Kategoriya bo'yicha"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    subcats = book_db.get_subcategories(cat_id)

    if subcats:
        subcats_with_count = book_db.get_categories_with_book_count()
        subcats_filtered = [c for c in subcats_with_count if c.parent_id == cat_id]
        keyboard = adm_subcategories_kb(subcats_filtered, parent_id=cat_id, prefix="adm_list_sub", allow_direct=True)
        await callback.message.edit_text(f"📁 <b>{category.name}</b>\n\nSubkategoriyani tanlang:", reply_markup=keyboard)
    else:
        pdf_count = book_db.count_books_by_category(cat_id, FileType.PDF)
        audio_count = book_db.count_books_by_category(cat_id, FileType.AUDIO)

        if pdf_count == 0 and audio_count == 0:
            await callback.message.edit_text(f"📂 <b>{category.name}</b> — kitoblar yo'q.")
        else:
            keyboard = adm_file_type_kb(cat_id, pdf_count=pdf_count, audio_count=audio_count, show_all=True)
            await callback.message.edit_text(
                f"📁 <b>{category.name}</b>\n\n{AdminEmoji.BOOK_PDF} PDF: {pdf_count}\n{AdminEmoji.BOOK_AUDIO} Audio: {audio_count}",
                reply_markup=keyboard
            )
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_type:"))
async def list_books_by_type(callback: types.CallbackQuery):
    """Tur bo'yicha kitoblar"""
    parts = callback.data.split(":")
    file_type_str = parts[1]
    cat_id = int(parts[2])

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO if file_type_str == "audio" else None

    result = book_db.get_books(category_id=cat_id, file_type=file_type, page=1, per_page=BOOKS_PER_PAGE)

    if not result.items:
        await callback.message.edit_text("📂 Kitoblar yo'q.")
        await callback.answer()
        return

    keyboard = adm_books_paginated_kb(result, prefix="adm_book", back_callback=f"adm_back:type:{cat_id}",
                                      category_id=cat_id, file_type=file_type_str)
    path = book_db.get_category_path(cat_id)

    await callback.message.edit_text(f"📂 <b>{path}</b>\n📚 {result.total} ta kitob", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_pg:"))
async def books_pagination(callback: types.CallbackQuery):
    """Pagination"""
    parts = callback.data.split(":")
    page = int(parts[1])
    cat_id = int(parts[2]) if parts[2] != "0" else None
    file_type_str = parts[3] if len(parts) > 3 else "all"

    file_type = FileType.PDF if file_type_str == "pdf" else FileType.AUDIO if file_type_str == "audio" else None

    result = book_db.get_books(category_id=cat_id, file_type=file_type, page=page, per_page=BOOKS_PER_PAGE)
    keyboard = adm_books_paginated_kb(result, prefix="adm_book", back_callback=f"adm_back:type:{cat_id or 0}",
                                      category_id=cat_id, file_type=file_type_str)

    await callback.message.edit_text(f"📖 Sahifa: {page}/{result.total_pages}", reply_markup=keyboard)
    await callback.answer()


# =================== KITOB TAFSILOTLARI ===================

@dp.callback_query_handler(lambda c: c.data.startswith("adm_book:") and not c.data.startswith("adm_book_"))
async def show_book_admin(callback: types.CallbackQuery):
    """Kitob tafsilotlari"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    text = format_book_info(book, detailed=True)
    keyboard = adm_book_actions_kb(book)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_view_book:"))
async def view_book_file(callback: types.CallbackQuery):
    """Faylni ko'rish"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    success = await send_book_file(callback.message, book)
    await callback.answer("✅ Yuborildi" if success else "❌ Xatolik", show_alert=not success)


@dp.callback_query_handler(lambda c: c.data.startswith("adm_edit_book:"))
async def edit_book_menu(callback: types.CallbackQuery):
    """Tahrirlash menyusi"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    await callback.message.edit_text(f"✏️ <b>Tahrirlash:</b> {book.title}\n\nNimani o'zgartirasiz?",
                                     reply_markup=adm_book_edit_kb(book))
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_edit_title:"))
async def edit_book_title_start(callback: types.CallbackQuery, state: FSMContext):
    """Nom tahrirlash"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    await state.update_data(edit_book_id=book_id, old_value=book.title)
    await callback.message.edit_text(f"📝 <b>Hozirgi nom:</b> {book.title}\n\nYangi nomni kiriting:")
    await callback.message.answer("Yangi nom:", reply_markup=admin_cancel_btn())
    await AdminEditBookState.edit_title.set()
    await callback.answer()


@dp.message_handler(state=AdminEditBookState.edit_title)
async def edit_book_title_done(message: types.Message, state: FSMContext):
    """Nom yangilandi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    new_title = message.text.strip()
    if len(new_title) < 2 or len(new_title) > 255:
        await message.answer("⚠️ Nom 2-255 belgi oralig'ida bo'lsin:")
        return

    data = await state.get_data()
    try:
        book_db.update_book(data['edit_book_id'], title=new_title)
        await message.answer(f"✅ Nom yangilandi!\n<s>{data['old_value']}</s> → <b>{new_title}</b>",
                             reply_markup=admin_book_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}", reply_markup=admin_book_menu())
    await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_edit_author:"))
async def edit_book_author_start(callback: types.CallbackQuery, state: FSMContext):
    """Muallif tahrirlash"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    await state.update_data(edit_book_id=book_id)
    await callback.message.edit_text(f"✍️ <b>Hozirgi muallif:</b> {book.author or '—'}\n\nYangi muallifni kiriting:")
    await callback.message.answer("Yangi muallif:", reply_markup=admin_cancel_btn())
    await AdminEditBookState.edit_author.set()
    await callback.answer()


@dp.message_handler(state=AdminEditBookState.edit_author)
async def edit_book_author_done(message: types.Message, state: FSMContext):
    """Muallif yangilandi"""
    if message.text == f"{AdminEmoji.CANCEL} Bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_book_menu())
        return

    data = await state.get_data()
    try:
        book_db.update_book(data['edit_book_id'], author=message.text.strip()[:100])
        await message.answer("✅ Muallif yangilandi!", reply_markup=admin_book_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}", reply_markup=admin_book_menu())
    await state.finish()


# =================== O'CHIRISH VA TASDIQLASH ===================

@dp.message_handler(Text(equals=f"{AdminEmoji.DELETE} O'chirish"))
async def delete_book_start(message: types.Message):
    """Kitob o'chirish"""
    if not await is_admin(message.from_user.id):
        return

    categories = book_db.get_categories_with_book_count()
    main_cats = [c for c in categories if c.parent_id is None]

    if not main_cats:
        await message.answer("📂 Kategoriyalar yo'q.", reply_markup=admin_book_menu())
        return

    keyboard = adm_categories_kb(main_cats, prefix="adm_delb_cat", show_book_count=True,
                                 back_callback="adm_back:book_menu")
    await message.answer("🗑 <b>Kategoriyani tanlang:</b>", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("adm_delb_cat:"))
async def delete_book_category(callback: types.CallbackQuery):
    """O'chirish uchun kategoriya"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    result = book_db.get_books(category_id=cat_id, page=1, per_page=BOOKS_PER_PAGE)

    if not result.items:
        await callback.message.edit_text("📂 Bu kategoriyada kitoblar yo'q.")
        await callback.answer()
        return

    keyboard = adm_books_paginated_kb(result, prefix="adm_del_book", back_callback="adm_back:book_menu",
                                      category_id=cat_id)
    await callback.message.edit_text("🗑 <b>O'chirish uchun kitobni tanlang:</b>", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_del_book:"))
async def delete_book_confirm(callback: types.CallbackQuery):
    """Tasdiqlash"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    emoji = AdminEmoji.BOOK_PDF if book.file_type == FileType.PDF else AdminEmoji.BOOK_AUDIO
    await callback.message.edit_text(
        f"⚠️ <b>Rostdan o'chirasizmi?</b>\n\n{emoji} {book.title}\n✍️ {book.author or '—'}\n📥 {book.download_count} marta yuklangan",
        reply_markup=adm_confirm_kb("del_book", book_id)
    )
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_del_cat:"))
async def delete_category_confirm(callback: types.CallbackQuery):
    """Kategoriya o'chirishni tasdiqlash"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    category = book_db.get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    book_count = book_db.count_books_by_category(cat_id)
    await callback.message.edit_text(
        f"⚠️ <b>Rostdan o'chirasizmi?</b>\n\n📁 {category.name}\n📖 {book_count} ta kitob ham o'chiriladi!",
        reply_markup=adm_confirm_kb("del_cat", cat_id)
    )
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_restore_book:"))
async def restore_book(callback: types.CallbackQuery):
    """Qayta tiklash"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    try:
        book_db.restore_book(book_id)
        await callback.message.edit_text("✅ Kitob qayta tiklandi!")
        logger.info(f"Book restored: {book_id}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik: {e}")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_restore_cat:"))
async def restore_category(callback: types.CallbackQuery):
    """Kategoriyani qayta tiklash"""
    cat_id = AdminCallbackParser.get_int_param(callback.data, 0)
    try:
        book_db.restore_category(cat_id)
        await callback.message.edit_text("✅ Kategoriya qayta tiklandi!")
        logger.info(f"Category restored: {cat_id}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik: {e}")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_yes:"))
async def confirm_yes(callback: types.CallbackQuery):
    """Ha - tasdiqlash"""
    parts = callback.data.replace("adm_yes:", "").split(":")
    action = parts[0]
    item_id = int(parts[1]) if len(parts) > 1 else None

    try:
        if action == "del_cat" and item_id:
            category = book_db.get_category_by_id(item_id)
            book_db.delete_category(item_id, hard_delete=False)
            await callback.message.edit_text(f"✅ <b>{category.name}</b> o'chirildi!\n<i>Qayta tiklash mumkin</i>")
            logger.info(f"Category soft deleted: {category.name}")

        elif action == "del_book" and item_id:
            book = book_db.get_book_by_id(item_id)
            book_db.delete_book(item_id, hard_delete=False)
            await callback.message.edit_text(f"✅ <b>{book.title}</b> o'chirildi!\n<i>Qayta tiklash mumkin</i>")
            logger.info(f"Book soft deleted: {book.title}")

        elif action == "hard_del_book" and item_id:
            book = book_db.get_book_by_id(item_id)
            book_db.delete_book(item_id, hard_delete=True)
            await callback.message.edit_text(f"🗑 <b>{book.title}</b> butunlay o'chirildi!")
            logger.info(f"Book hard deleted: {book.title}")

        elif action == "hard_del_cat" and item_id:
            category = book_db.get_category_by_id(item_id)
            book_db.delete_category(item_id, hard_delete=True)
            await callback.message.edit_text(f"🗑 <b>{category.name}</b> butunlay o'chirildi!")
            logger.info(f"Category hard deleted: {category.name}")

        elif action == "purge_all":
            result = book_db.purge_deleted(days_old=0)
            await callback.message.edit_text(
                f"🗑 <b>Tozalash tugadi!</b>\n\n📖 Kitoblar: {result['books']}\n📁 Kategoriyalar: {result['categories']}")
            logger.info(f"Purge completed: {result}")

        else:
            await callback.message.edit_text("❌ Noma'lum amal")

    except Exception as e:
        await callback.message.edit_text(f"❌ Xatolik: {e}")
        logger.error(f"Confirm action error: {e}")

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_no:"))
async def confirm_no(callback: types.CallbackQuery):
    """Yo'q - bekor"""
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.answer()


# =================== O'CHIRILGANLAR ===================

@dp.message_handler(Text(equals=f"{AdminEmoji.TRASH} O'chirilganlar"))
async def deleted_items_section(message: types.Message):
    """O'chirilganlar"""
    if not await is_admin(message.from_user.id):
        return

    counts = book_db.get_deleted_items_count()
    keyboard = adm_deleted_items_kb(books_count=counts['books'], categories_count=counts['categories'])
    await message.answer(
        f"🗑 <b>O'chirilgan elementlar</b>\n\n📖 Kitoblar: {counts['books']}\n📁 Kategoriyalar: {counts['categories']}",
        reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("adm_deleted:"))
async def show_deleted_items(callback: types.CallbackQuery):
    """O'chirilganlarni ko'rsatish"""
    item_type = AdminCallbackParser.get_param(callback.data, 0)

    if item_type == "books":
        result = book_db.get_deleted_books(page=1, per_page=BOOKS_PER_PAGE)
        if not result.items:
            await callback.message.edit_text("✨ O'chirilgan kitoblar yo'q.")
        else:
            keyboard = adm_books_paginated_kb(result, prefix="adm_del_item_book", back_callback="adm_back:deleted")
            await callback.message.edit_text(f"🗑 <b>O'chirilgan kitoblar:</b> {result.total} ta", reply_markup=keyboard)

    elif item_type == "categories":
        categories = book_db.get_all_categories(include_deleted=True)
        deleted_cats = [c for c in categories if c.is_deleted]
        if not deleted_cats:
            await callback.message.edit_text("✨ O'chirilgan kategoriyalar yo'q.")
        else:
            keyboard = adm_categories_kb(deleted_cats, prefix="adm_del_item_cat", back_callback="adm_back:deleted")
            await callback.message.edit_text(f"🗑 <b>O'chirilgan kategoriyalar:</b> {len(deleted_cats)} ta",
                                             reply_markup=keyboard)

    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_del_item_book:"))
async def show_deleted_book(callback: types.CallbackQuery):
    """O'chirilgan kitob"""
    book_id = AdminCallbackParser.get_int_param(callback.data, 0)
    book = book_db.get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    text = format_book_info(book, detailed=True)
    keyboard = adm_book_actions_kb(book, show_restore=True)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "adm_purge_all")
async def purge_all_confirm(callback: types.CallbackQuery):
    """Hammasini tozalash"""
    await callback.message.edit_text(
        f"⚠️ <b>DIQQAT!</b>\n\nBarcha o'chirilgan elementlar butunlay o'chiriladi!\nQaytarib bo'lmaydi!",
        reply_markup=adm_confirm_kb("purge_all", confirm_text="O'chirish", cancel_text="Bekor")
    )
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("adm_stats:"))
async def stats_details(callback: types.CallbackQuery):
    """Statistika tafsilotlari"""
    stat_type = AdminCallbackParser.get_param(callback.data, 0)

    if stat_type == "refresh":
        book_db.clear_cache()
        await callback.answer("🔄 Yangilandi!")
        stats = book_db.get_statistics()
        text = f"📊 <b>Statistika</b> (yangilandi)\n\n📁 Kategoriyalar: {stats.total_categories}\n📖 Kitoblar: {stats.total_books}\n📥 Yuklab olishlar: {stats.total_downloads}"
        await callback.message.edit_text(text, reply_markup=adm_stats_kb())

    elif stat_type == "books":
        categories = book_db.get_categories_with_book_count()
        text = "📖 <b>Kategoriyalar bo'yicha:</b>\n\n"
        for cat in categories[:20]:
            if cat.book_count > 0:
                text += f"📁 {cat.name}: {cat.book_count} ta\n"
        await callback.message.edit_text(text, reply_markup=adm_stats_kb())

    elif stat_type == "downloads":
        popular = book_db.get_popular_books(20)
        text = "📥 <b>Eng ko'p yuklangan:</b>\n\n"
        for i, book in enumerate(popular, 1):
            emoji = AdminEmoji.BOOK_PDF if book.file_type == FileType.PDF else AdminEmoji.BOOK_AUDIO
            text += f"{i}. {emoji} {truncate_text(book.title, 30)} — {book.download_count}\n"
        await callback.message.edit_text(text, reply_markup=adm_stats_kb())

    await callback.answer()


# =================== BACK HANDLERS ===================

@dp.callback_query_handler(lambda c: c.data.startswith("adm_back:"))
async def admin_back_handler(callback: types.CallbackQuery, state: FSMContext):
    """Orqaga"""
    target = AdminCallbackParser.get_param(callback.data, 0)

    current = await state.get_state()
    if current:
        await state.finish()

    if target == "main":
        await callback.message.delete()
        await callback.message.answer("👨‍💼 <b>Admin Panel</b>", reply_markup=admin_main_menu())

    elif target == "categories":
        categories = book_db.get_categories_with_book_count()
        main_cats = [c for c in categories if c.parent_id is None]
        if main_cats:
            keyboard = adm_categories_kb(main_cats, prefix="adm_list_cat", show_book_count=True,
                                         back_callback="adm_back:main")
            await callback.message.edit_text("📁 <b>Kategoriyalar:</b>", reply_markup=keyboard)
        else:
            await callback.message.edit_text("📂 Kategoriyalar yo'q.")

    elif target == "book_menu":
        await callback.message.delete()
        await callback.message.answer("📖 <b>Kitoblar</b>", reply_markup=admin_book_menu())

    elif target == "cat_menu":
        await callback.message.delete()
        await callback.message.answer("📁 <b>Kategoriyalar</b>", reply_markup=admin_category_menu())

    elif target == "deleted":
        counts = book_db.get_deleted_items_count()
        keyboard = adm_deleted_items_kb(books_count=counts['books'], categories_count=counts['categories'])
        await callback.message.edit_text("🗑 <b>O'chirilgan elementlar</b>", reply_markup=keyboard)

    elif target.startswith("type:"):
        cat_id = int(target.split(":")[1]) if ":" in target else None
        if cat_id:
            category = book_db.get_category_by_id(cat_id)
            if category:
                pdf_count = book_db.count_books_by_category(cat_id, FileType.PDF)
                audio_count = book_db.count_books_by_category(cat_id, FileType.AUDIO)
                keyboard = adm_file_type_kb(cat_id, pdf_count, audio_count)
                await callback.message.edit_text(f"📁 <b>{category.name}</b>\n\nTurni tanlang:", reply_markup=keyboard)

    await callback.answer()


# =================== CANCEL HANDLER ===================

@dp.message_handler(Text(equals=f"{AdminEmoji.CANCEL} Bekor"), state="*")
async def cancel_any(message: types.Message, state: FSMContext):
    """Bekor qilish"""
    current = await state.get_state()
    if current:
        await state.finish()
    await message.answer("❌ Bekor qilindi", reply_markup=admin_main_menu())


# =================== EMPTY CALLBACKS ===================

@dp.callback_query_handler(lambda c: c.data in ["adm_empty", "adm_page_info", "current_page"])
async def empty_callback(callback: types.CallbackQuery):
    """Bo'sh callback"""
    await callback.answer()