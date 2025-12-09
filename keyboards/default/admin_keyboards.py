"""
Admin Keyboards - Professional Admin Panel Klaviaturalari
==========================================================
Xususiyatlar:
- Dataclass bilan ishlaydi (Book, Category)
- Pagination support
- FileType enum
- Callback data validation
- Empty state handling
- DRY principle
- Soft delete support
- sekin sekin
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from typing import List, Optional, Union

# Type imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.db_api.book_database import Book, Category, PaginatedResult, FileType


# =================== CONSTANTS ===================

class AdminEmoji:
    """Admin panel emoji konstantalari"""
    # Kategoriyalar
    FOLDER = "📁"
    FOLDER_OPEN = "📂"
    ADD_FOLDER = "📁➕"

    # Kitoblar
    BOOK = "📖"
    BOOK_PDF = "📕"
    BOOK_AUDIO = "🎧"
    BOOKS = "📚"

    # Amallar
    ADD = "➕"
    EDIT = "✏️"
    DELETE = "🗑"
    VIEW = "👁"
    UPLOAD = "📤"
    DOWNLOAD = "📥"

    # Navigatsiya
    BACK = "🔙"
    HOME = "🏠"
    CANCEL = "🚫"
    SKIP = "⏩"
    DONE = "✅"

    # Status
    YES = "✅"
    NO = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"

    # Pagination
    NEXT = "➡️"
    PREV = "⬅️"

    # Boshqa
    STATS = "📊"
    SEARCH = "🔍"
    LIST = "📋"
    BULK = "📦"
    RESTORE = "♻️"
    TRASH = "🗑"


# Callback data max length
MAX_CALLBACK_LENGTH = 64


# =================== HELPER FUNCTIONS ===================

def truncate_text(text: str, max_length: int = 30, suffix: str = "...") -> str:
    """Matnni qisqartirish"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_callback(callback: str) -> str:
    """Callback data xavfsizligini tekshirish"""
    if len(callback.encode('utf-8')) > MAX_CALLBACK_LENGTH:
        raise ValueError(f"Callback too long: {len(callback.encode('utf-8'))} bytes")
    return callback


def get_book_emoji(file_type) -> str:
    """Kitob turi uchun emoji"""
    file_type_str = file_type.value if hasattr(file_type, 'value') else str(file_type)
    return AdminEmoji.BOOK_PDF if file_type_str == "pdf" else AdminEmoji.BOOK_AUDIO


def build_grid_keyboard(
        buttons: List[InlineKeyboardButton],
        row_width: int = 2,
        footer_buttons: List[InlineKeyboardButton] = None
) -> InlineKeyboardMarkup:
    """Grid shaklidagi keyboard yaratish"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)

    for i in range(0, len(buttons), row_width):
        row = buttons[i:i + row_width]
        keyboard.row(*row)

    if footer_buttons:
        for btn in footer_buttons:
            keyboard.row(btn)

    return keyboard


# =================== REPLY KEYBOARDS ===================

def admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin asosiy menyu"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"🗂 Kategoriyalar boshqaruvi"),
        KeyboardButton(f"📚 Kitoblar boshqaruvi")
    )
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.STATS} Statistika"),
        KeyboardButton(f"{AdminEmoji.SEARCH} Qidirish")
    )
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.TRASH} O'chirilganlar"),
        KeyboardButton(f"{AdminEmoji.HOME} Bosh menyu")
    )
    return keyboard


def admin_category_menu() -> ReplyKeyboardMarkup:
    """Kategoriyalar menyusi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.ADD} Kategoriya"),
        KeyboardButton(f"{AdminEmoji.LIST} Ro'yxat")
    )
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.EDIT} Tahrirlash"),
        KeyboardButton(f"{AdminEmoji.DELETE} O'chirish")
    )
    keyboard.add(KeyboardButton(f"{AdminEmoji.BACK} Admin menyu"))
    return keyboard


def admin_book_menu() -> ReplyKeyboardMarkup:
    """Kitoblar menyusi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.UPLOAD} Kitob yuklash"),
        KeyboardButton(f"{AdminEmoji.BULK} Bulk yuklash")
    )
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.LIST} Kitoblar"),
        KeyboardButton(f"{AdminEmoji.DELETE} O'chirish")
    )
    keyboard.add(KeyboardButton(f"{AdminEmoji.BACK} Admin menyu"))
    return keyboard


def admin_cancel_btn() -> ReplyKeyboardMarkup:
    """Bekor qilish"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(f"{AdminEmoji.CANCEL} Bekor"))
    return keyboard


def admin_skip_btn() -> ReplyKeyboardMarkup:
    """O'tkazib yuborish + Bekor"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.SKIP} O'tkazish"),
        KeyboardButton(f"{AdminEmoji.CANCEL} Bekor")
    )
    return keyboard


def admin_done_btn() -> ReplyKeyboardMarkup:
    """Tugatish + Bekor"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.DONE} Tugatish"),
        KeyboardButton(f"{AdminEmoji.CANCEL} Bekor")
    )
    return keyboard


def admin_confirm_reply_btn() -> ReplyKeyboardMarkup:
    """Tasdiqlash reply keyboard"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{AdminEmoji.YES} Ha"),
        KeyboardButton(f"{AdminEmoji.NO} Yo'q")
    )
    return keyboard


def admin_back_btn(text: str = "Admin menyu") -> ReplyKeyboardMarkup:
    """Orqaga tugmasi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(f"{AdminEmoji.BACK} {text}"))
    return keyboard


# =================== INLINE KEYBOARDS ===================

def adm_categories_kb(
        categories: List["Category"],
        prefix: str = "adm_cat",
        show_book_count: bool = False,
        back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Admin kategoriyalar keyboard

    Args:
        categories: Category dataclass lari
        prefix: Callback prefix (adm_cat, adm_del_cat, adm_edit_cat, adm_bulk_cat)
        show_book_count: Kitoblar sonini ko'rsatish
        back_callback: Orqaga tugmasi callback
    """
    # Bo'sh holat
    if not categories:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "📭 Kategoriyalar mavjud emas",
                callback_data="adm_empty"
            )
        )
        if back_callback:
            keyboard.add(
                InlineKeyboardButton(
                    f"{AdminEmoji.BACK} Orqaga",
                    callback_data=back_callback
                )
            )
        return keyboard

    buttons = []
    for cat in categories:
        # Dataclass dan olish
        cat_id = cat.id
        cat_name = cat.name
        book_count = getattr(cat, 'book_count', 0)

        # Text
        if show_book_count and book_count > 0:
            text = f"{AdminEmoji.FOLDER} {cat_name} ({book_count})"
        else:
            text = f"{AdminEmoji.FOLDER} {cat_name}"

        text = truncate_text(text, 28)

        buttons.append(
            InlineKeyboardButton(
                text,
                callback_data=safe_callback(f"{prefix}:{cat_id}")
            )
        )

    # Footer
    footer = []
    if back_callback:
        footer.append(
            InlineKeyboardButton(
                f"{AdminEmoji.BACK} Orqaga",
                callback_data=back_callback
            )
        )

    return build_grid_keyboard(buttons, row_width=2, footer_buttons=footer)


def adm_subcategories_kb(
        subcategories: List["Category"],
        parent_id: int,
        prefix: str = "adm_sub",
        allow_direct: bool = True
) -> InlineKeyboardMarkup:
    """
    Admin subkategoriyalar keyboard

    Args:
        subcategories: Subkategoriyalar ro'yxati
        parent_id: Parent kategoriya ID
        prefix: Callback prefix
        allow_direct: Asosiy kategoriyaga qo'shish imkoniyati
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Subkategoriyalar
    buttons = []
    for sub in subcategories:
        sub_id = sub.id
        sub_name = sub.name
        book_count = getattr(sub, 'book_count', 0)

        text = f"{AdminEmoji.FOLDER_OPEN} {sub_name}"
        if book_count > 0:
            text += f" ({book_count})"
        text = truncate_text(text, 28)

        buttons.append(
            InlineKeyboardButton(
                text,
                callback_data=safe_callback(f"{prefix}:{sub_id}")
            )
        )

    # Grid
    for i in range(0, len(buttons), 2):
        row = buttons[i:i + 2]
        keyboard.row(*row)

    # Asosiy kategoriyaga to'g'ridan-to'g'ri qo'shish
    if allow_direct:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.FOLDER} Shu kategoriyaga",
                callback_data=safe_callback(f"{prefix}_direct:{parent_id}")
            )
        )

    # Orqaga
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Kategoriyalar",
            callback_data="adm_back:categories"
        )
    )

    return keyboard


def adm_parent_select_kb(
        categories: List["Category"],
        allow_root: bool = True,
        current_parent_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """
    Parent kategoriya tanlash keyboard

    Args:
        categories: Asosiy kategoriyalar
        allow_root: Asosiy (root) kategoriya bo'lishi mumkinmi
        current_parent_id: Hozirgi parent (exclude qilish uchun)
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    if not categories:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Kategoriyalar yo'q",
                callback_data="adm_empty"
            )
        )
        if allow_root:
            keyboard.add(
                InlineKeyboardButton(
                    f"{AdminEmoji.FOLDER} Asosiy kategoriya",
                    callback_data="adm_parent:0"
                )
            )
        return keyboard

    buttons = []
    for cat in categories:
        # O'zini exclude qilish
        if current_parent_id and cat.id == current_parent_id:
            continue

        text = truncate_text(f"{AdminEmoji.FOLDER} {cat.name}", 28)
        buttons.append(
            InlineKeyboardButton(
                text,
                callback_data=safe_callback(f"adm_parent:{cat.id}")
            )
        )

    # Grid
    for i in range(0, len(buttons), 2):
        row = buttons[i:i + 2]
        keyboard.row(*row)

    # Asosiy kategoriya
    if allow_root:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.FOLDER} Asosiy kategoriya (root)",
                callback_data="adm_parent:0"
            )
        )

    return keyboard


def adm_books_kb(
        books: List["Book"],
        prefix: str = "adm_book",
        page: int = 1,
        total_pages: int = 1,
        back_callback: str = "adm_back:books",
        category_id: Optional[int] = None,
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Admin kitoblar keyboard (pagination bilan)

    Args:
        books: Book dataclass lari
        prefix: Callback prefix
        page: Hozirgi sahifa
        total_pages: Jami sahifalar
        back_callback: Orqaga tugmasi
        category_id: Kategoriya ID (pagination uchun)
        file_type: Fayl turi (pagination uchun)
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Bo'sh holat
    if not books:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Kitoblar topilmadi",
                callback_data="adm_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BACK} Orqaga",
                callback_data=back_callback
            )
        )
        return keyboard

    # Kitoblar
    for book in books:
        emoji = get_book_emoji(book.file_type)
        display_title = truncate_text(book.title, 32)

        # Download count ko'rsatish
        dl_count = book.download_count
        if dl_count > 0:
            text = f"{emoji} {display_title} ({dl_count})"
        else:
            text = f"{emoji} {display_title}"

        keyboard.add(
            InlineKeyboardButton(
                text,
                callback_data=safe_callback(f"{prefix}:{book.id}")
            )
        )

    # Pagination
    if total_pages > 1:
        pagination_row = []

        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{AdminEmoji.PREV}",
                    callback_data=safe_callback(f"adm_pg:{page - 1}:{category_id or 0}:{file_type or 'all'}")
                )
            )

        pagination_row.append(
            InlineKeyboardButton(
                f"· {page}/{total_pages} ·",
                callback_data="adm_page_info"
            )
        )

        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{AdminEmoji.NEXT}",
                    callback_data=safe_callback(f"adm_pg:{page + 1}:{category_id or 0}:{file_type or 'all'}")
                )
            )

        keyboard.row(*pagination_row)

    # Orqaga
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data=back_callback
        )
    )

    return keyboard


def adm_books_paginated_kb(
        paginated_result: "PaginatedResult",
        prefix: str = "adm_book",
        back_callback: str = "adm_back:books",
        category_id: Optional[int] = None,
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """PaginatedResult bilan keyboard"""
    return adm_books_kb(
        books=paginated_result.items,
        prefix=prefix,
        page=paginated_result.page,
        total_pages=paginated_result.total_pages,
        back_callback=back_callback,
        category_id=category_id,
        file_type=file_type
    )


def adm_book_actions_kb(
        book: "Book",
        show_restore: bool = False
) -> InlineKeyboardMarkup:
    """
    Kitob ustida amallar

    Args:
        book: Book dataclass
        show_restore: Qayta tiklash tugmasini ko'rsatish (soft deleted uchun)
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    book_id = book.id

    if show_restore or book.is_deleted:
        # O'chirilgan kitob uchun
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.RESTORE} Qayta tiklash",
                callback_data=safe_callback(f"adm_restore_book:{book_id}")
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.DELETE} Butunlay o'chirish",
                callback_data=safe_callback(f"adm_hard_del_book:{book_id}")
            )
        )
    else:
        # Oddiy kitob uchun
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.EDIT} Tahrir",
                callback_data=safe_callback(f"adm_edit_book:{book_id}")
            ),
            InlineKeyboardButton(
                f"{AdminEmoji.DELETE} O'chirish",
                callback_data=safe_callback(f"adm_del_book:{book_id}")
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.VIEW} Ko'rish",
                callback_data=safe_callback(f"adm_view_book:{book_id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data="adm_back:books"
        )
    )

    return keyboard


def adm_book_edit_kb(book: "Book") -> InlineKeyboardMarkup:
    """
    Kitobni tahrirlash keyboard

    Args:
        book: Book dataclass
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    book_id = book.id

    # Asosiy maydonlar
    keyboard.add(
        InlineKeyboardButton(
            "📝 Nom",
            callback_data=safe_callback(f"adm_edit_title:{book_id}")
        ),
        InlineKeyboardButton(
            "✍️ Muallif",
            callback_data=safe_callback(f"adm_edit_author:{book_id}")
        )
    )

    # Audio uchun narrator
    file_type_str = book.file_type.value if hasattr(book.file_type, 'value') else str(book.file_type)
    if file_type_str == "audio":
        keyboard.add(
            InlineKeyboardButton(
                "🎙 Hikoyachi",
                callback_data=safe_callback(f"adm_edit_narrator:{book_id}")
            ),
            InlineKeyboardButton(
                "📄 Tavsif",
                callback_data=safe_callback(f"adm_edit_desc:{book_id}")
            )
        )
    else:
        keyboard.add(
            InlineKeyboardButton(
                "📄 Tavsif",
                callback_data=safe_callback(f"adm_edit_desc:{book_id}")
            )
        )

    # Kategoriya
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.FOLDER} Kategoriya",
            callback_data=safe_callback(f"adm_edit_bookcat:{book_id}")
        )
    )

    # Fayl almashtirish
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.UPLOAD} Faylni almashtirish",
            callback_data=safe_callback(f"adm_edit_file:{book_id}")
        )
    )

    # Orqaga
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data=safe_callback(f"adm_book:{book_id}")
        )
    )

    return keyboard


def adm_category_edit_kb(category: "Category") -> InlineKeyboardMarkup:
    """
    Kategoriyani tahrirlash keyboard

    Args:
        category: Category dataclass
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    cat_id = category.id

    keyboard.add(
        InlineKeyboardButton(
            "📝 Nom",
            callback_data=safe_callback(f"adm_cat_name:{cat_id}")
        ),
        InlineKeyboardButton(
            "📄 Tavsif",
            callback_data=safe_callback(f"adm_cat_desc:{cat_id}")
        )
    )

    # Parent o'zgartirish (agar subkategoriya bo'lsa)
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.FOLDER} Parent",
            callback_data=safe_callback(f"adm_cat_parent:{cat_id}")
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data="adm_back:cat_list"
        )
    )

    return keyboard


def adm_category_actions_kb(
        category: "Category",
        show_restore: bool = False
) -> InlineKeyboardMarkup:
    """
    Kategoriya ustida amallar

    Args:
        category: Category dataclass
        show_restore: Qayta tiklash ko'rsatish
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    cat_id = category.id

    if show_restore or category.is_deleted:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.RESTORE} Qayta tiklash",
                callback_data=safe_callback(f"adm_restore_cat:{cat_id}")
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.DELETE} Butunlay o'chirish",
                callback_data=safe_callback(f"adm_hard_del_cat:{cat_id}")
            )
        )
    else:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.EDIT} Tahrirlash",
                callback_data=safe_callback(f"adm_edit_cat:{cat_id}")
            ),
            InlineKeyboardButton(
                f"{AdminEmoji.DELETE} O'chirish",
                callback_data=safe_callback(f"adm_del_cat:{cat_id}")
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BOOKS} Kitoblarni ko'rish",
                callback_data=safe_callback(f"adm_cat_books:{cat_id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data="adm_back:categories"
        )
    )

    return keyboard


def adm_confirm_kb(
        action: str,
        item_id: Optional[int] = None,
        confirm_text: str = "Ha",
        cancel_text: str = "Yo'q"
) -> InlineKeyboardMarkup:
    """
    Tasdiqlash keyboard

    Args:
        action: Amal nomi (delete_cat, delete_book, hard_delete, etc.)
        item_id: Element ID
        confirm_text: Tasdiqlash tugmasi matni
        cancel_text: Bekor qilish tugmasi matni
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Callback yasash
    if item_id is not None:
        confirm_cb = f"adm_yes:{action}:{item_id}"
        cancel_cb = f"adm_no:{action}:{item_id}"
    else:
        confirm_cb = f"adm_yes:{action}"
        cancel_cb = f"adm_no:{action}"

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.YES} {confirm_text}",
            callback_data=safe_callback(confirm_cb)
        ),
        InlineKeyboardButton(
            f"{AdminEmoji.NO} {cancel_text}",
            callback_data=safe_callback(cancel_cb)
        )
    )

    return keyboard


def adm_file_type_kb(
        category_id: int,
        pdf_count: int = 0,
        audio_count: int = 0,
        show_all: bool = True
) -> InlineKeyboardMarkup:
    """
    Fayl turini tanlash keyboard

    Args:
        category_id: Kategoriya ID
        pdf_count: PDF kitoblar soni
        audio_count: Audio kitoblar soni
        show_all: "Hammasi" tugmasini ko'rsatish
    """
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Hech narsa yo'q
    if pdf_count == 0 and audio_count == 0:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Bu kategoriyada kitoblar yo'q",
                callback_data="adm_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BACK} Orqaga",
                callback_data="adm_back:categories"
            )
        )
        return keyboard

    # PDF
    if pdf_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BOOK_PDF} PDF ({pdf_count})",
                callback_data=safe_callback(f"adm_type:pdf:{category_id}")
            )
        )

    # Audio
    if audio_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BOOK_AUDIO} Audio ({audio_count})",
                callback_data=safe_callback(f"adm_type:audio:{category_id}")
            )
        )

    # Hammasi
    if show_all and (pdf_count > 0 or audio_count > 0):
        total = pdf_count + audio_count
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BOOKS} Hammasi ({total})",
                callback_data=safe_callback(f"adm_type:all:{category_id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Orqaga",
            callback_data="adm_back:categories"
        )
    )

    return keyboard


def adm_deleted_items_kb(
        books_count: int = 0,
        categories_count: int = 0
) -> InlineKeyboardMarkup:
    """
    O'chirilgan elementlar keyboard

    Args:
        books_count: O'chirilgan kitoblar soni
        categories_count: O'chirilgan kategoriyalar soni
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    if books_count == 0 and categories_count == 0:
        keyboard.add(
            InlineKeyboardButton(
                "✨ O'chirilgan elementlar yo'q",
                callback_data="adm_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BACK} Admin menyu",
                callback_data="adm_back:main"
            )
        )
        return keyboard

    if books_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.BOOK} O'chirilgan kitoblar ({books_count})",
                callback_data="adm_deleted:books"
            )
        )

    if categories_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.FOLDER} O'chirilgan kategoriyalar ({categories_count})",
                callback_data="adm_deleted:categories"
            )
        )

    # Hammasini tozalash
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.WARNING} Hammasini tozalash",
            callback_data="adm_purge_all"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Admin menyu",
            callback_data="adm_back:main"
        )
    )

    return keyboard


def adm_bulk_upload_kb(
        category_id: int,
        uploaded_count: int = 0,
        failed_count: int = 0
) -> InlineKeyboardMarkup:
    """
    Bulk upload status keyboard

    Args:
        category_id: Kategoriya ID
        uploaded_count: Yuklangan kitoblar soni
        failed_count: Xato bo'lganlar soni
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Status
    if uploaded_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{AdminEmoji.DONE} {uploaded_count} ta yuklandi" +
                (f", {failed_count} ta xato" if failed_count else ""),
                callback_data="adm_bulk_status"
            )
        )

    # Davom ettirish
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.UPLOAD} Yana yuklash",
            callback_data=safe_callback(f"adm_bulk_more:{category_id}")
        )
    )

    # Tugatish
    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.DONE} Tugatish",
            callback_data=safe_callback(f"adm_bulk_done:{category_id}")
        )
    )

    return keyboard


def adm_stats_kb() -> InlineKeyboardMarkup:
    """Statistika keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BOOK} Kitoblar",
            callback_data="adm_stats:books"
        ),
        InlineKeyboardButton(
            f"{AdminEmoji.FOLDER} Kategoriyalar",
            callback_data="adm_stats:categories"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.DOWNLOAD} Yuklab olishlar",
            callback_data="adm_stats:downloads"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            "🔄 Yangilash",
            callback_data="adm_stats:refresh"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            f"{AdminEmoji.BACK} Admin menyu",
            callback_data="adm_back:main"
        )
    )

    return keyboard


# =================== CALLBACK PARSER ===================

class AdminCallbackParser:
    """Admin callback datani parse qilish"""

    @staticmethod
    def parse(callback_data: str) -> dict:
        """
        Callback datani parse qilish

        Format: "adm_action:param1:param2"
        Returns: {"action": str, "params": list}
        """
        parts = callback_data.split(":")
        action = parts[0].replace("adm_", "") if parts[0].startswith("adm_") else parts[0]
        return {
            "action": action,
            "params": parts[1:] if len(parts) > 1 else [],
            "raw_action": parts[0]
        }

    @staticmethod
    def get_action(callback_data: str) -> str:
        """Faqat action olish (adm_ prefix olib tashlanadi)"""
        parts = callback_data.split(":")
        action = parts[0] if parts else ""
        return action.replace("adm_", "") if action.startswith("adm_") else action

    @staticmethod
    def get_param(callback_data: str, index: int = 0, default: any = None) -> any:
        """Parametr olish"""
        parts = callback_data.split(":")
        try:
            return parts[index + 1]
        except IndexError:
            return default

    @staticmethod
    def get_int_param(callback_data: str, index: int = 0, default: int = 0) -> int:
        """Integer parametr olish"""
        try:
            return int(AdminCallbackParser.get_param(callback_data, index, default))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def is_admin_callback(callback_data: str) -> bool:
        """Admin callback ekanligini tekshirish"""
        return callback_data.startswith("adm_")