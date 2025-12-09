"""
User Keyboards - Professional Telegram Bot Klaviaturalari
=========================================================
Xususiyatlar:
- Dataclass bilan ishlaydi (Book, Category)
- Pagination support
- FileType enum
- Callback data validation (64 byte limit)
- Empty state handling
- DRY principle
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from typing import List, Optional, Callable
from enum import Enum

# Type imports (circular import oldini olish uchun TYPE_CHECKING)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.db_api.book_database import Book, Category, PaginatedResult, FileType


# =================== CONSTANTS ===================

class Emoji:
    """Emoji konstantalari"""
    FOLDER = "📁"
    FOLDER_OPEN = "📂"
    BOOK_PDF = "📕"
    BOOK_AUDIO = "🎧"
    SEARCH = "🔍"
    STAR = "⭐️"
    STATS = "📊"
    HELP = "ℹ️"
    BACK = "🔙"
    CANCEL = "❌"
    DOWNLOAD = "📥"
    PLAY = "▶️"
    NEXT = "➡️"
    PREV = "⬅️"
    HOME = "🏠"
    NEW = "🆕"
    FIRE = "🔥"


# Callback data max length (Telegram limit: 64 bytes)
MAX_CALLBACK_LENGTH = 64


# =================== HELPER FUNCTIONS ===================

def truncate_text(text: str, max_length: int = 35, suffix: str = "...") -> str:
    """Matnni qisqartirish"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_callback(callback: str) -> str:
    """Callback data xavfsizligini tekshirish"""
    if len(callback.encode('utf-8')) > MAX_CALLBACK_LENGTH:
        raise ValueError(f"Callback data too long: {len(callback.encode('utf-8'))} bytes")
    return callback


def build_grid_keyboard(
        buttons: List[InlineKeyboardButton],
        row_width: int = 2,
        footer_buttons: List[InlineKeyboardButton] = None
) -> InlineKeyboardMarkup:
    """Grid shaklidagi keyboard yaratish (DRY)"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)

    # Asosiy buttonlarni grid qilib qo'shish
    for i in range(0, len(buttons), row_width):
        row = buttons[i:i + row_width]
        keyboard.row(*row)

    # Footer buttonlar (orqaga, bekor qilish, etc.)
    if footer_buttons:
        for btn in footer_buttons:
            keyboard.row(btn)

    return keyboard


def get_book_emoji(file_type) -> str:
    """Kitob turi uchun emoji"""
    # String yoki FileType enum bo'lishi mumkin
    file_type_str = file_type.value if hasattr(file_type, 'value') else str(file_type)
    return Emoji.BOOK_PDF if file_type_str == "pdf" else Emoji.BOOK_AUDIO


# =================== REPLY KEYBOARDS ===================

def user_main_menu() -> ReplyKeyboardMarkup:
    """User asosiy menyu"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{Emoji.FOLDER} Kategoriyalar"),
        KeyboardButton(f"{Emoji.SEARCH} Qidirish")
    )
    keyboard.add(
        KeyboardButton(f"{Emoji.FIRE} Mashhurlar"),
        KeyboardButton(f"{Emoji.NEW} Yangilar")
    )
    keyboard.add(
        KeyboardButton(f"{Emoji.STATS} Statistika"),
        KeyboardButton(f"{Emoji.HELP} Yordam")
    )
    return keyboard


def back_button(text: str = "Orqaga") -> ReplyKeyboardMarkup:
    """Orqaga tugmasi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(f"{Emoji.BACK} {text}"))
    return keyboard


def cancel_button(text: str = "Bekor qilish") -> ReplyKeyboardMarkup:
    """Bekor qilish tugmasi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(f"{Emoji.CANCEL} {text}"))
    return keyboard


def back_and_home() -> ReplyKeyboardMarkup:
    """Orqaga va Bosh menyu"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(f"{Emoji.BACK} Orqaga"),
        KeyboardButton(f"{Emoji.HOME} Bosh menyu")
    )
    return keyboard


# =================== INLINE KEYBOARDS ===================

def categories_keyboard(
        categories: List["Category"],
        prefix: str = "u_cat",
        show_book_count: bool = False,
        back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Kategoriyalar inline keyboard

    Args:
        categories: Category dataclass lari ro'yxati
        prefix: Callback prefix (u_cat, u_subcat, etc.)
        show_book_count: Kitoblar sonini ko'rsatish
        back_callback: Orqaga tugmasi callback
    """
    # Bo'sh holat
    if not categories:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "📭 Kategoriyalar mavjud emas",
                callback_data="u_empty"
            )
        )
        if back_callback:
            keyboard.add(
                InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
            )
        return keyboard

    buttons = []
    for cat in categories:
        # Dataclass dan ma'lumotlarni olish
        cat_id = cat.id
        cat_name = cat.name
        book_count = getattr(cat, 'book_count', 0)

        # Button text
        if show_book_count and book_count > 0:
            text = f"{Emoji.FOLDER} {cat_name} ({book_count})"
        else:
            text = f"{Emoji.FOLDER} {cat_name}"

        text = truncate_text(text, 30)

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
            InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
        )

    return build_grid_keyboard(buttons, row_width=2, footer_buttons=footer)


def subcategories_keyboard(
        subcategories: List["Category"],
        parent_id: int,
        show_book_count: bool = False
) -> InlineKeyboardMarkup:
    """
    Subkategoriyalar keyboard

    Args:
        subcategories: Subkategoriyalar ro'yxati
        parent_id: Parent kategoriya ID
        show_book_count: Kitoblar sonini ko'rsatish
    """
    # Bo'sh holat
    if not subcategories:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                "📭 Subkategoriyalar mavjud emas",
                callback_data="u_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.BACK} Orqaga",
                callback_data="u_back:categories"
            )
        )
        return keyboard

    buttons = []
    for sub in subcategories:
        sub_id = sub.id
        sub_name = sub.name
        book_count = getattr(sub, 'book_count', 0)

        if show_book_count and book_count > 0:
            text = f"{Emoji.FOLDER_OPEN} {sub_name} ({book_count})"
        else:
            text = f"{Emoji.FOLDER_OPEN} {sub_name}"

        text = truncate_text(text, 30)

        buttons.append(
            InlineKeyboardButton(
                text,
                callback_data=safe_callback(f"u_subcat:{sub_id}")
            )
        )

    footer = [
        InlineKeyboardButton(
            f"{Emoji.BACK} Kategoriyalar",
            callback_data="u_back:categories"
        )
    ]

    return build_grid_keyboard(buttons, row_width=2, footer_buttons=footer)


def book_type_keyboard(
        category_id: int,
        pdf_count: int = 0,
        audio_count: int = 0,
        back_callback: str = "back:categories"
) -> InlineKeyboardMarkup:
    """
    PDF/Audio tanlash keyboard

    Args:
        category_id: Kategoriya ID
        pdf_count: PDF kitoblar soni
        audio_count: Audio kitoblar soni
        back_callback: Orqaga tugmasi callback
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Hech narsa yo'q
    if pdf_count == 0 and audio_count == 0:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Bu kategoriyada kitoblar yo'q",
                callback_data="u_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
        )
        return keyboard

    if pdf_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.BOOK_PDF} PDF kitoblar ({pdf_count})",
                callback_data=safe_callback(f"u_type:pdf:{category_id}")
            )
        )

    if audio_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.BOOK_AUDIO} Audio kitoblar ({audio_count})",
                callback_data=safe_callback(f"u_type:audio:{category_id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
    )

    return keyboard


def books_list_keyboard(
        books: List["Book"],
        back_callback: str,
        page: int = 1,
        total_pages: int = 1,
        category_id: Optional[int] = None,
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Kitoblar ro'yxati keyboard (pagination bilan)

    Args:
        books: Book dataclass lari ro'yxati
        back_callback: Orqaga tugmasi callback
        page: Hozirgi sahifa
        total_pages: Jami sahifalar
        category_id: Kategoriya ID (pagination uchun)
        file_type: Fayl turi (pagination uchun)
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Bo'sh holat
    if not books:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Kitoblar topilmadi",
                callback_data="u_empty"
            )
        )
        keyboard.add(
            InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
        )
        return keyboard

    # Kitoblar
    for book in books:
        emoji = get_book_emoji(book.file_type)
        display_title = truncate_text(book.title, 35)

        keyboard.add(
            InlineKeyboardButton(
                f"{emoji} {display_title}",
                callback_data=safe_callback(f"u_dl:{book.id}")
            )
        )

    # Pagination buttons
    if total_pages > 1:
        pagination_row = []

        # Oldingi sahifa
        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{Emoji.PREV} {page - 1}",
                    callback_data=safe_callback(f"u_pg:{page - 1}:{category_id or 0}:{file_type or 'all'}")
                )
            )

        # Hozirgi sahifa
        pagination_row.append(
            InlineKeyboardButton(
                f"· {page}/{total_pages} ·",
                callback_data="u_page_info"
            )
        )

        # Keyingi sahifa
        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{page + 1} {Emoji.NEXT}",
                    callback_data=safe_callback(f"u_pg:{page + 1}:{category_id or 0}:{file_type or 'all'}")
                )
            )

        keyboard.row(*pagination_row)

    # Orqaga
    keyboard.add(
        InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
    )

    return keyboard


def books_paginated_keyboard(
        paginated_result: "PaginatedResult",
        back_callback: str,
        category_id: Optional[int] = None,
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    PaginatedResult bilan keyboard yaratish

    Args:
        paginated_result: Database dan kelgan PaginatedResult
        back_callback: Orqaga tugmasi callback
        category_id: Kategoriya ID
        file_type: Fayl turi
    """
    return books_list_keyboard(
        books=paginated_result.items,
        back_callback=back_callback,
        page=paginated_result.page,
        total_pages=paginated_result.total_pages,
        category_id=category_id,
        file_type=file_type
    )


def book_detail_keyboard(
        book: "Book",
        back_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Kitob tafsilotlari keyboard

    Args:
        book: Book dataclass
        back_callback: Orqaga tugmasi callback (None bo'lsa, avtomatik)
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Fayl turiga qarab button
    file_type_str = book.file_type.value if hasattr(book.file_type, 'value') else str(book.file_type)

    if file_type_str == "pdf":
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.DOWNLOAD} Yuklab olish",
                callback_data=safe_callback(f"download:{book.id}")
            )
        )
    else:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.PLAY} Tinglash",
                callback_data=safe_callback(f"download:{book.id}")
            )
        )

    # Orqaga
    if back_callback is None:
        back_callback = f"books:{file_type_str}:{book.category_id}"

    keyboard.add(
        InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data=back_callback)
    )

    return keyboard


def search_type_keyboard(
        pdf_count: int = 0,
        audio_count: int = 0,
        search_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """
    Qidiruv natijalarida tur tanlash

    Args:
        pdf_count: PDF natijalar soni
        audio_count: Audio natijalar soni
        search_id: Qidiruv ID (cache uchun, query o'rniga)
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Hech narsa topilmadi
    if pdf_count == 0 and audio_count == 0:
        keyboard.add(
            InlineKeyboardButton(
                "😔 Hech narsa topilmadi",
                callback_data="u_empty"
            )
        )
        return keyboard

    if pdf_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.BOOK_PDF} PDF natijalar ({pdf_count})",
                callback_data=safe_callback(f"u_stype:pdf:{search_id or 0}")
            )
        )

    if audio_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.BOOK_AUDIO} Audio natijalar ({audio_count})",
                callback_data=safe_callback(f"u_stype:audio:{search_id or 0}")
            )
        )

    return keyboard


def search_results_keyboard(
        books: List["Book"],
        page: int = 1,
        total_pages: int = 1,
        search_id: Optional[int] = None,
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Qidiruv natijalari keyboard (pagination bilan)

    Args:
        books: Topilgan kitoblar
        page: Hozirgi sahifa
        total_pages: Jami sahifalar
        search_id: Qidiruv ID
        file_type: Fayl turi filtri
    """
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not books:
        keyboard.add(
            InlineKeyboardButton(
                "😔 Hech narsa topilmadi",
                callback_data="u_empty"
            )
        )
        return keyboard

    # Kitoblar - bosilganda yuklanadi
    for book in books:
        emoji = get_book_emoji(book.file_type)
        display_title = truncate_text(book.title, 32)

        # dl = direct download
        keyboard.add(
            InlineKeyboardButton(
                f"{emoji} {display_title}",
                callback_data=safe_callback(f"u_dl:{book.id}")
            )
        )

    # Pagination
    if total_pages > 1:
        pagination_row = []

        if page > 1:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{Emoji.PREV}",
                    callback_data=safe_callback(f"u_sp:{page - 1}:{search_id}:{file_type}")
                )
            )

        pagination_row.append(
            InlineKeyboardButton(f"· {page}/{total_pages} ·", callback_data="current_page")
        )

        if page < total_pages:
            pagination_row.append(
                InlineKeyboardButton(
                    f"{Emoji.NEXT}",
                    callback_data=safe_callback(f"u_sp:{page + 1}:{search_id}:{file_type}")
                )
            )

        keyboard.row(*pagination_row)

    # Tur almashtirgich (agar search_id bo'lsa)
    if search_id:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.SEARCH} Tur tanlash",
                callback_data=safe_callback(f"u_sback:{search_id}")
            )
        )

    return keyboard


def popular_keyboard(
        pdf_count: int = 0,
        audio_count: int = 0
) -> InlineKeyboardMarkup:
    """Mashhur kitoblar tur tanlash"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    if pdf_count == 0 and audio_count == 0:
        keyboard.add(
            InlineKeyboardButton(
                "📭 Mashhur kitoblar yo'q",
                callback_data="u_empty"
            )
        )
        return keyboard

    if pdf_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.FIRE} Mashhur PDF ({pdf_count})",
                callback_data="u_popular:pdf"
            )
        )

    if audio_count > 0:
        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.FIRE} Mashhur Audio ({audio_count})",
                callback_data="u_popular:audio"
            )
        )

    return keyboard


def popular_books_keyboard(
        books: List["Book"],
        file_type: str
) -> InlineKeyboardMarkup:
    """Mashhur kitoblar ro'yxati"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not books:
        keyboard.add(
            InlineKeyboardButton("📭 Kitoblar yo'q", callback_data="u_empty")
        )
        keyboard.add(
            InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data="u_back:popular")
        )
        return keyboard

    for i, book in enumerate(books, 1):
        emoji = get_book_emoji(book.file_type)

        # Reyting ko'rsatish
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        display_title = truncate_text(book.title, 28)
        downloads = book.download_count

        keyboard.add(
            InlineKeyboardButton(
                f"{medal} {display_title} ({downloads})",
                callback_data=safe_callback(f"u_dl:{book.id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(f"{Emoji.BACK} Orqaga", callback_data="u_back:popular")
    )

    return keyboard


def recent_books_keyboard(
        books: List["Book"],
        file_type: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Yangi kitoblar ro'yxati"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    if not books:
        keyboard.add(
            InlineKeyboardButton("📭 Yangi kitoblar yo'q", callback_data="u_empty")
        )
        return keyboard

    for book in books:
        emoji = get_book_emoji(book.file_type)
        display_title = truncate_text(book.title, 32)

        keyboard.add(
            InlineKeyboardButton(
                f"{Emoji.NEW} {emoji} {display_title}",
                callback_data=safe_callback(f"u_dl:{book.id}")
            )
        )

    keyboard.add(
        InlineKeyboardButton(f"{Emoji.HOME} Bosh menyu", callback_data="u_back:main")
    )

    return keyboard


def confirm_keyboard(
        confirm_callback: str,
        cancel_callback: str,
        confirm_text: str = "✅ Ha",
        cancel_text: str = "❌ Yo'q"
) -> InlineKeyboardMarkup:
    """Tasdiqlash keyboard"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(confirm_text, callback_data=confirm_callback),
        InlineKeyboardButton(cancel_text, callback_data=cancel_callback)
    )
    return keyboard


def close_keyboard() -> InlineKeyboardMarkup:
    """Yopish tugmasi"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✖️ Yopish", callback_data="u_close")
    )
    return keyboard


# =================== CALLBACK PARSER ===================

class CallbackParser:
    """Callback datani parse qilish uchun helper"""

    @staticmethod
    def parse(callback_data: str) -> dict:
        """
        Callback datani parse qilish

        Format: "action:param1:param2:..."
        Returns: {"action": str, "params": list}
        """
        parts = callback_data.split(":")
        return {
            "action": parts[0] if parts else "",
            "params": parts[1:] if len(parts) > 1 else []
        }

    @staticmethod
    def get_action(callback_data: str) -> str:
        """Faqat action olish"""
        return callback_data.split(":")[0] if callback_data else ""

    @staticmethod
    def get_param(callback_data: str, index: int = 0, default: any = None) -> any:
        """Parametr olish"""
        parts = callback_data.split(":")
        try:
            return parts[index + 1]  # +1 chunki 0 = action
        except IndexError:
            return default

    @staticmethod
    def get_int_param(callback_data: str, index: int = 0, default: int = 0) -> int:
        """Integer parametr olish"""
        try:
            return int(CallbackParser.get_param(callback_data, index, default))
        except (ValueError, TypeError):
            return default