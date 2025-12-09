"""
BookDatabase - Professional Kutubxona Database Moduli
======================================================
Xususiyatlar:
- Eski Database klassidan meros
- Dataclass modellar (Book, Category, PaginatedResult)
- FileType enum
- Soft delete support
- Pagination
- FTS (Full-Text Search) ready
- Backward compatible (eski metodlar ham ishlaydi)
"""

from .database import Database
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =================== ENUMS ===================

class FileType(str, Enum):
    """Fayl turlari"""
    PDF = "pdf"
    AUDIO = "audio"
    EPUB = "epub"
    FB2 = "fb2"

    @classmethod
    def from_string(cls, value: str) -> "FileType":
        """String dan FileType ga convert"""
        if value is None:
            return cls.PDF
        try:
            return cls(value.lower().strip())
        except ValueError:
            return cls.PDF


class SortOrder(str, Enum):
    """Saralash tartibi"""
    ASC = "ASC"
    DESC = "DESC"


class BookSortBy(str, Enum):
    """Kitoblarni saralash"""
    TITLE = "title"
    CREATED_AT = "created_at"
    DOWNLOAD_COUNT = "download_count"
    AUTHOR = "author"


# =================== DATA CLASSES ===================

@dataclass
class Category:
    """Kategoriya modeli"""
    id: int
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    created_at: datetime
    created_by: int
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    book_count: int = 0

    @classmethod
    def from_row(cls, row: Union[tuple, None]) -> Optional["Category"]:
        """Tuple dan Category yaratish"""
        if not row:
            return None
        return cls(
            id=row[0],
            name=row[1],
            description=row[2],
            parent_id=row[3],
            created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else (row[4] or datetime.now()),
            created_by=row[5],
            is_deleted=bool(row[6]) if len(row) > 6 else False,
            deleted_at=datetime.fromisoformat(row[7]) if len(row) > 7 and row[7] else None,
            book_count=row[8] if len(row) > 8 else 0
        )


@dataclass
class Book:
    """Kitob modeli"""
    id: int
    title: str
    file_id: str
    file_type: FileType
    category_id: int
    author: Optional[str]
    narrator: Optional[str]
    description: Optional[str]
    duration: Optional[int]
    file_size: Optional[int]
    uploaded_by: int
    download_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    category_name: Optional[str] = None

    @classmethod
    def from_row(cls, row: Union[tuple, None]) -> Optional["Book"]:
        """Tuple dan Book yaratish"""
        if not row:
            return None

        # Row uzunligiga qarab parsing
        # Eski format: id, title, file_id, file_type, category_id, author, narrator,
        #              description, duration, file_size, uploaded_by, download_count, created_at, [category_name]

        return cls(
            id=row[0],
            title=row[1],
            file_id=row[2],
            file_type=FileType.from_string(row[3]),
            category_id=row[4],
            author=row[5],
            narrator=row[6],
            description=row[7],
            duration=row[8],
            file_size=row[9],
            uploaded_by=row[10],
            download_count=row[11] or 0,
            created_at=datetime.fromisoformat(row[12]) if isinstance(row[12], str) else (row[12] or datetime.now()),
            updated_at=None,
            is_deleted=False,
            deleted_at=None,
            category_name=row[13] if len(row) > 13 else None
        )

    @property
    def duration_formatted(self) -> str:
        """Davomiylikni formatlash"""
        if not self.duration:
            return ""
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def file_size_formatted(self) -> str:
        """Fayl hajmini formatlash"""
        if not self.file_size:
            return ""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


@dataclass
class PaginatedResult:
    """Pagination natijasi"""
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass
class Statistics:
    """Statistika modeli"""
    total_categories: int
    main_categories: int
    total_books: int
    pdf_books: int
    audio_books: int
    total_downloads: int = 0
    deleted_books: int = 0
    deleted_categories: int = 0


# =================== DATABASE CLASS ===================

class BookDatabase(Database):
    """
    Professional Kutubxona Database

    Eski metodlar saqlanib qolgan + yangi dataclass metodlar qo'shilgan
    """

    def create_tables(self):
        """Jadvallarni yaratish"""

        # Kategoriyalar jadvali (yangilangan)
        sql_categories = """
        CREATE TABLE IF NOT EXISTS Categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            description TEXT NULL,
            parent_id INTEGER NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            deleted_at DATETIME NULL,
            FOREIGN KEY (parent_id) REFERENCES Categories(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES Users(id) ON DELETE CASCADE
        );
        """
        self.execute(sql_categories, commit=True)

        # Kitoblar jadvali (yangilangan)
        sql_books = """
        CREATE TABLE IF NOT EXISTS Books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(500) NOT NULL,
            file_id VARCHAR(500) NOT NULL,
            file_type VARCHAR(10) NOT NULL DEFAULT 'pdf',
            category_id INTEGER NOT NULL,
            author VARCHAR(255) NULL,
            narrator VARCHAR(255) NULL,
            description TEXT NULL,
            duration INTEGER NULL,
            file_size INTEGER NULL,
            uploaded_by INTEGER NOT NULL,
            download_count INTEGER DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            deleted_at DATETIME NULL,
            FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES Users(id) ON DELETE CASCADE
        );
        """
        self.execute(sql_books, commit=True)

        # Yangi ustunlarni qo'shish (agar jadval mavjud bo'lsa)
        self._add_soft_delete_columns()

    def _add_soft_delete_columns(self):
        """Soft delete ustunlarini qo'shish (migration)"""
        try:
            self.execute("ALTER TABLE Categories ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0", commit=True)
        except:
            pass
        try:
            self.execute("ALTER TABLE Categories ADD COLUMN deleted_at DATETIME NULL", commit=True)
        except:
            pass
        try:
            self.execute("ALTER TABLE Books ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0", commit=True)
        except:
            pass
        try:
            self.execute("ALTER TABLE Books ADD COLUMN deleted_at DATETIME NULL", commit=True)
        except:
            pass

    # =================== KATEGORIYALAR (YANGILANGAN) ===================

    def add_category(self, name: str, created_by: int, description: str = None, parent_id: int = None) -> int:
        """Yangi kategoriya qo'shish"""
        sql = """
        INSERT INTO Categories (name, description, parent_id, created_by)
        VALUES (?, ?, ?, ?)
        """
        cursor = self.execute(sql, parameters=(name, description, parent_id, created_by), commit=True)
        return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None

    def get_all_categories(self, include_deleted: bool = False) -> List[Category]:
        """Barcha kategoriyalar (dataclass)"""
        if include_deleted:
            sql = "SELECT * FROM Categories ORDER BY parent_id, name"
        else:
            sql = "SELECT * FROM Categories WHERE is_deleted = 0 OR is_deleted IS NULL ORDER BY parent_id, name"
        rows = self.execute(sql, fetchall=True)
        return [Category.from_row(row) for row in (rows or [])]

    def get_main_categories(self, include_deleted: bool = False) -> List[Category]:
        """Asosiy kategoriyalar (dataclass)"""
        if include_deleted:
            sql = "SELECT * FROM Categories WHERE parent_id IS NULL ORDER BY name"
        else:
            sql = "SELECT * FROM Categories WHERE parent_id IS NULL AND (is_deleted = 0 OR is_deleted IS NULL) ORDER BY name"
        rows = self.execute(sql, fetchall=True)
        return [Category.from_row(row) for row in (rows or [])]

    def get_subcategories(self, parent_id: int, include_deleted: bool = False) -> List[Category]:
        """Subkategoriyalar (dataclass)"""
        if include_deleted:
            sql = "SELECT * FROM Categories WHERE parent_id = ? ORDER BY name"
        else:
            sql = "SELECT * FROM Categories WHERE parent_id = ? AND (is_deleted = 0 OR is_deleted IS NULL) ORDER BY name"
        rows = self.execute(sql, parameters=(parent_id,), fetchall=True)
        return [Category.from_row(row) for row in (rows or [])]

    def has_subcategories(self, category_id: int) -> bool:
        """Subkategoriyalar bormi?"""
        sql = "SELECT COUNT(*) FROM Categories WHERE parent_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)"
        result = self.execute(sql, parameters=(category_id,), fetchone=True)
        return result[0] > 0 if result else False

    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        """ID bo'yicha kategoriya (dataclass)"""
        sql = "SELECT * FROM Categories WHERE id = ?"
        row = self.execute(sql, parameters=(category_id,), fetchone=True)
        return Category.from_row(row)

    def get_category_by_name(self, name: str, parent_id: int = None) -> Optional[Category]:
        """Nom bo'yicha kategoriya"""
        if parent_id is not None:
            sql = "SELECT * FROM Categories WHERE name = ? AND parent_id = ? AND (is_deleted = 0 OR is_deleted IS NULL)"
            row = self.execute(sql, parameters=(name, parent_id), fetchone=True)
        else:
            sql = "SELECT * FROM Categories WHERE name = ? AND parent_id IS NULL AND (is_deleted = 0 OR is_deleted IS NULL)"
            row = self.execute(sql, parameters=(name,), fetchone=True)
        return Category.from_row(row)

    def delete_category(self, category_id: int, hard_delete: bool = False):
        """Kategoriyani o'chirish (soft yoki hard)"""
        if hard_delete:
            sql = "DELETE FROM Categories WHERE id = ?"
        else:
            sql = "UPDATE Categories SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?"
        self.execute(sql, parameters=(category_id,), commit=True)

    def restore_category(self, category_id: int):
        """O'chirilgan kategoriyani qaytarish"""
        sql = "UPDATE Categories SET is_deleted = 0, deleted_at = NULL WHERE id = ?"
        self.execute(sql, parameters=(category_id,), commit=True)

    def update_category(self, category_id: int, name: str = None, description: str = None,
                        parent_id: int = None) -> bool:
        """Kategoriyani yangilash (flexible)"""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if parent_id is not None:
            updates.append("parent_id = ?")
            params.append(parent_id)

        if not updates:
            return False

        params.append(category_id)
        sql = f"UPDATE Categories SET {', '.join(updates)} WHERE id = ?"
        self.execute(sql, parameters=tuple(params), commit=True)
        return True

    def update_category_name(self, category_id: int, new_name: str):
        """Kategoriya nomini yangilash (backward compatible)"""
        return self.update_category(category_id, name=new_name)

    def update_category_description(self, category_id: int, new_description: str):
        """Kategoriya tavsifini yangilash (backward compatible)"""
        return self.update_category(category_id, description=new_description)

    def count_categories(self, include_deleted: bool = False) -> int:
        """Kategoriyalar soni"""
        if include_deleted:
            sql = "SELECT COUNT(*) FROM Categories"
        else:
            sql = "SELECT COUNT(*) FROM Categories WHERE is_deleted = 0 OR is_deleted IS NULL"
        result = self.execute(sql, fetchone=True)
        return result[0] if result else 0

    def get_category_path(self, category_id: int) -> str:
        """Kategoriya yo'li (Asosiy → Sub)"""
        path = []
        current_id = category_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            category = self.get_category_by_id(current_id)
            if category:
                path.insert(0, category.name)
                current_id = category.parent_id
            else:
                break
        return " → ".join(path) if path else ""

    def get_categories_with_book_count(self, file_type: FileType = None) -> List[Category]:
        """Kategoriyalar kitoblar soni bilan"""
        if file_type:
            sql = """
                SELECT c.*, 
                    (SELECT COUNT(*) FROM Books b 
                     WHERE b.category_id = c.id AND (b.is_deleted = 0 OR b.is_deleted IS NULL) AND b.file_type = ?) as book_count
                FROM Categories c
                WHERE c.is_deleted = 0 OR c.is_deleted IS NULL
                ORDER BY c.parent_id NULLS FIRST, c.name
            """
            rows = self.execute(sql, parameters=(file_type.value if isinstance(file_type, FileType) else file_type,),
                                fetchall=True)
        else:
            sql = """
                SELECT c.*, 
                    (SELECT COUNT(*) FROM Books b 
                     WHERE b.category_id = c.id AND (b.is_deleted = 0 OR b.is_deleted IS NULL)) as book_count
                FROM Categories c
                WHERE c.is_deleted = 0 OR c.is_deleted IS NULL
                ORDER BY c.parent_id NULLS FIRST, c.name
            """
            rows = self.execute(sql, fetchall=True)

        return [Category.from_row(row) for row in (rows or [])]

    # =================== KITOBLAR (YANGILANGAN) ===================

    def add_book(self, title: str, file_id: str, category_id: int, uploaded_by: int,
                 file_type: Union[str, FileType] = 'pdf', author: str = None, narrator: str = None,
                 description: str = None, duration: int = None, file_size: int = None) -> int:
        """Kitob qo'shish"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        sql = """
        INSERT INTO Books (title, file_id, file_type, category_id, author, narrator, 
                          description, duration, file_size, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.execute(sql, parameters=(title, file_id, file_type_value, category_id, author,
                                               narrator, description, duration, file_size, uploaded_by),
                              commit=True)
        return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None

    def add_books_bulk(self, books_list: list) -> Tuple[int, int]:
        """Ko'p kitobni qo'shish (returns: added, errors)"""
        added = 0
        errors = 0
        for book in books_list:
            try:
                # file_type ni normalize qilish
                book_data = list(book)
                if len(book_data) > 2 and isinstance(book_data[2], FileType):
                    book_data[2] = book_data[2].value

                sql = """
                INSERT INTO Books (title, file_id, file_type, category_id, author, narrator, 
                                  description, duration, file_size, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.execute(sql, parameters=tuple(book_data), commit=True)
                added += 1
            except Exception as e:
                logger.error(f"Error adding book {book[0]}: {e}")
                errors += 1
        return added, errors

    def get_books(self, category_id: int = None, file_type: Union[str, FileType] = None,
                  include_deleted: bool = False, page: int = 1, per_page: int = 20,
                  sort_by: BookSortBy = BookSortBy.CREATED_AT,
                  sort_order: SortOrder = SortOrder.DESC) -> PaginatedResult:
        """Kitoblarni olish (pagination bilan, dataclass)"""

        conditions = []
        params = []

        if not include_deleted:
            conditions.append("(b.is_deleted = 0 OR b.is_deleted IS NULL)")
        if category_id:
            conditions.append("b.category_id = ?")
            params.append(category_id)
        if file_type:
            file_type_value = file_type.value if isinstance(file_type, FileType) else file_type
            conditions.append("b.file_type = ?")
            params.append(file_type_value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count
        count_sql = f"SELECT COUNT(*) FROM Books b {where_clause}"
        total = self.execute(count_sql, parameters=tuple(params), fetchone=True)[0]

        # Pagination
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        offset = (page - 1) * per_page

        # Ma'lumotlar
        sort_by_value = sort_by.value if isinstance(sort_by, BookSortBy) else sort_by
        sort_order_value = sort_order.value if isinstance(sort_order, SortOrder) else sort_order

        sql = f"""
            SELECT b.*, c.name as category_name
            FROM Books b
            LEFT JOIN Categories c ON b.category_id = c.id
            {where_clause}
            ORDER BY b.{sort_by_value} {sort_order_value}
            LIMIT ? OFFSET ?
        """
        params.extend([per_page, offset])

        rows = self.execute(sql, parameters=tuple(params), fetchall=True)
        books = [Book.from_row(row) for row in (rows or [])]

        return PaginatedResult(
            items=books,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )

    def get_all_books(self, file_type: Union[str, FileType] = None) -> List[Book]:
        """Barcha kitoblar (dataclass)"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        if file_type_value:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE (Books.is_deleted = 0 OR Books.is_deleted IS NULL) AND Books.file_type = ?
            ORDER BY Books.created_at DESC
            """
            rows = self.execute(sql, parameters=(file_type_value,), fetchall=True)
        else:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE Books.is_deleted = 0 OR Books.is_deleted IS NULL
            ORDER BY Books.created_at DESC
            """
            rows = self.execute(sql, fetchall=True)

        return [Book.from_row(row) for row in (rows or [])]

    def get_books_by_category(self, category_id: int, file_type: Union[str, FileType] = None,
                              page: int = 1, per_page: int = 20) -> PaginatedResult:
        """Kategoriya bo'yicha kitoblar (pagination bilan)"""
        return self.get_books(category_id=category_id, file_type=file_type, page=page, per_page=per_page)

    def get_book_by_id(self, book_id: int) -> Optional[Book]:
        """ID bo'yicha kitob (dataclass)"""
        sql = """
        SELECT Books.*, Categories.name as category_name 
        FROM Books 
        LEFT JOIN Categories ON Books.category_id = Categories.id
        WHERE Books.id = ?
        """
        row = self.execute(sql, parameters=(book_id,), fetchone=True)
        return Book.from_row(row)

    def get_book_by_file_id(self, file_id: str) -> Optional[Book]:
        """File ID bo'yicha kitob (dataclass)"""
        sql = """
        SELECT Books.*, Categories.name as category_name 
        FROM Books 
        LEFT JOIN Categories ON Books.category_id = Categories.id
        WHERE Books.file_id = ?
        """
        row = self.execute(sql, parameters=(file_id,), fetchone=True)
        return Book.from_row(row)

    def search_books(self, query: str, file_type: Union[str, FileType] = None,
                     page: int = 1, per_page: int = 20, use_fts: bool = False) -> PaginatedResult:
        """Kitob qidirish (pagination bilan)"""
        search_query = f"%{query}%"
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        conditions = [
            "(Books.is_deleted = 0 OR Books.is_deleted IS NULL)",
            "(Books.title LIKE ? OR Books.author LIKE ? OR Books.narrator LIKE ?)"
        ]
        params = [search_query, search_query, search_query]

        if file_type_value:
            conditions.append("Books.file_type = ?")
            params.append(file_type_value)

        where_clause = f"WHERE {' AND '.join(conditions)}"

        # Count
        count_sql = f"SELECT COUNT(*) FROM Books {where_clause}"
        total = self.execute(count_sql, parameters=tuple(params), fetchone=True)[0]

        # Pagination
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        offset = (page - 1) * per_page

        # Ma'lumotlar
        sql = f"""
        SELECT Books.*, Categories.name as category_name 
        FROM Books 
        LEFT JOIN Categories ON Books.category_id = Categories.id
        {where_clause}
        ORDER BY Books.title
        LIMIT ? OFFSET ?
        """
        params.extend([per_page, offset])

        rows = self.execute(sql, parameters=tuple(params), fetchall=True)
        books = [Book.from_row(row) for row in (rows or [])]

        return PaginatedResult(
            items=books,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )

    def delete_book(self, book_id: int, hard_delete: bool = False):
        """Kitobni o'chirish (soft yoki hard)"""
        if hard_delete:
            sql = "DELETE FROM Books WHERE id = ?"
        else:
            sql = "UPDATE Books SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ?"
        self.execute(sql, parameters=(book_id,), commit=True)

    def restore_book(self, book_id: int):
        """O'chirilgan kitobni qaytarish"""
        sql = "UPDATE Books SET is_deleted = 0, deleted_at = NULL WHERE id = ?"
        self.execute(sql, parameters=(book_id,), commit=True)

    def delete_books_bulk(self, book_ids: list, hard_delete: bool = False) -> int:
        """Ko'p kitobni o'chirish"""
        deleted = 0
        for book_id in book_ids:
            try:
                self.delete_book(book_id, hard_delete)
                deleted += 1
            except:
                continue
        return deleted

    def increment_download_count(self, book_id: int) -> int:
        """Yuklab olishlar sonini oshirish"""
        sql = "UPDATE Books SET download_count = download_count + 1 WHERE id = ?"
        self.execute(sql, parameters=(book_id,), commit=True)

        result = self.execute("SELECT download_count FROM Books WHERE id = ?",
                              parameters=(book_id,), fetchone=True)
        return result[0] if result else 0

    def count_books(self, file_type: Union[str, FileType] = None, include_deleted: bool = False) -> int:
        """Kitoblar soni"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        conditions = []
        params = []

        if not include_deleted:
            conditions.append("(is_deleted = 0 OR is_deleted IS NULL)")
        if file_type_value:
            conditions.append("file_type = ?")
            params.append(file_type_value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) FROM Books {where_clause}"

        result = self.execute(sql, parameters=tuple(params), fetchone=True)
        return result[0] if result else 0

    def count_books_by_category(self, category_id: int, file_type: Union[str, FileType] = None) -> int:
        """Kategoriya bo'yicha kitoblar soni"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        conditions = ["category_id = ?", "(is_deleted = 0 OR is_deleted IS NULL)"]
        params = [category_id]

        if file_type_value:
            conditions.append("file_type = ?")
            params.append(file_type_value)

        sql = f"SELECT COUNT(*) FROM Books WHERE {' AND '.join(conditions)}"
        result = self.execute(sql, parameters=tuple(params), fetchone=True)
        return result[0] if result else 0

    def get_popular_books(self, limit: int = 10, file_type: Union[str, FileType] = None) -> List[Book]:
        """Eng mashhur kitoblar (dataclass)"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        if file_type_value:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE (Books.is_deleted = 0 OR Books.is_deleted IS NULL) AND Books.file_type = ?
            ORDER BY Books.download_count DESC
            LIMIT ?
            """
            rows = self.execute(sql, parameters=(file_type_value, limit), fetchall=True)
        else:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE Books.is_deleted = 0 OR Books.is_deleted IS NULL
            ORDER BY Books.download_count DESC
            LIMIT ?
            """
            rows = self.execute(sql, parameters=(limit,), fetchall=True)

        return [Book.from_row(row) for row in (rows or [])]

    def get_recent_books(self, limit: int = 10, file_type: Union[str, FileType] = None) -> List[Book]:
        """Eng yangi kitoblar (dataclass)"""
        file_type_value = file_type.value if isinstance(file_type, FileType) else file_type

        if file_type_value:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE (Books.is_deleted = 0 OR Books.is_deleted IS NULL) AND Books.file_type = ?
            ORDER BY Books.created_at DESC
            LIMIT ?
            """
            rows = self.execute(sql, parameters=(file_type_value, limit), fetchall=True)
        else:
            sql = """
            SELECT Books.*, Categories.name as category_name 
            FROM Books 
            LEFT JOIN Categories ON Books.category_id = Categories.id
            WHERE Books.is_deleted = 0 OR Books.is_deleted IS NULL
            ORDER BY Books.created_at DESC
            LIMIT ?
            """
            rows = self.execute(sql, parameters=(limit,), fetchall=True)

        return [Book.from_row(row) for row in (rows or [])]

    def get_deleted_books(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        """O'chirilgan kitoblar"""
        return self.get_books(include_deleted=True, page=page, per_page=per_page)

    # =================== KITOBNI YANGILASH ===================

    def update_book(self, book_id: int, title: str = None, author: str = None,
                    narrator: str = None, description: str = None,
                    category_id: int = None, file_id: str = None,
                    file_type: Union[str, FileType] = None, file_size: int = None,
                    duration: int = None) -> bool:
        """Kitobni yangilash (flexible)"""
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if author is not None:
            updates.append("author = ?")
            params.append(author)
        if narrator is not None:
            updates.append("narrator = ?")
            params.append(narrator)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if category_id is not None:
            updates.append("category_id = ?")
            params.append(category_id)
        if file_id is not None:
            updates.append("file_id = ?")
            params.append(file_id)
        if file_type is not None:
            file_type_value = file_type.value if isinstance(file_type, FileType) else file_type
            updates.append("file_type = ?")
            params.append(file_type_value)
        if file_size is not None:
            updates.append("file_size = ?")
            params.append(file_size)
        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)

        if not updates:
            return False

        params.append(book_id)
        sql = f"UPDATE Books SET {', '.join(updates)} WHERE id = ?"
        self.execute(sql, parameters=tuple(params), commit=True)
        return True

    # Backward compatible metodlar
    def update_book_title(self, book_id: int, new_title: str):
        return self.update_book(book_id, title=new_title)

    def update_book_author(self, book_id: int, new_author: str):
        return self.update_book(book_id, author=new_author)

    def update_book_narrator(self, book_id: int, new_narrator: str):
        return self.update_book(book_id, narrator=new_narrator)

    def update_book_description(self, book_id: int, new_description: str):
        return self.update_book(book_id, description=new_description)

    def update_book_category(self, book_id: int, new_category_id: int):
        return self.update_book(book_id, category_id=new_category_id)

    def update_book_file(self, book_id: int, file_id: str, file_type: str,
                         file_size: int = None, duration: int = None):
        return self.update_book(book_id, file_id=file_id, file_type=file_type,
                                file_size=file_size, duration=duration)

    # =================== STATISTIKA ===================

    def get_statistics(self) -> Statistics:
        """To'liq statistika (dataclass)"""
        total_downloads_sql = "SELECT COALESCE(SUM(download_count), 0) FROM Books WHERE is_deleted = 0 OR is_deleted IS NULL"
        total_downloads = self.execute(total_downloads_sql, fetchone=True)[0] or 0

        deleted_books = self.count_books(include_deleted=True) - self.count_books()
        deleted_cats = self.count_categories(include_deleted=True) - self.count_categories()

        return Statistics(
            total_categories=self.count_categories(),
            main_categories=len(self.get_main_categories()),
            total_books=self.count_books(),
            pdf_books=self.count_books(file_type='pdf'),
            audio_books=self.count_books(file_type='audio'),
            total_downloads=total_downloads,
            deleted_books=deleted_books,
            deleted_categories=deleted_cats
        )

    def get_deleted_items_count(self) -> Dict[str, int]:
        """O'chirilgan elementlar soni"""
        books = self.execute(
            "SELECT COUNT(*) FROM Books WHERE is_deleted = 1",
            fetchone=True
        )
        categories = self.execute(
            "SELECT COUNT(*) FROM Categories WHERE is_deleted = 1",
            fetchone=True
        )
        return {
            "books": books[0] if books else 0,
            "categories": categories[0] if categories else 0
        }

    def purge_deleted(self, days_old: int = 30) -> Dict[str, int]:
        """Eski o'chirilganlarni butunlay o'chirish"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days_old)

        books_deleted = 0
        cats_deleted = 0

        try:
            cursor = self.execute(
                "DELETE FROM Books WHERE is_deleted = 1 AND deleted_at < ?",
                parameters=(cutoff,), commit=True
            )
            books_deleted = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
        except:
            pass

        try:
            cursor = self.execute(
                "DELETE FROM Categories WHERE is_deleted = 1 AND deleted_at < ?",
                parameters=(cutoff,), commit=True
            )
            cats_deleted = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
        except:
            pass

        return {"books": books_deleted, "categories": cats_deleted}

    def clear_cache(self):
        """Cache ni tozalash (placeholder)"""
        pass