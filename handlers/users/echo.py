from aiogram.types import ContentType
from loader import dp
from aiogram import types

@dp.message_handler(content_types=ContentType.VIDEO)
async def video_echo_handler(message: types.Message):
    """
    Foydalanuvchi video yuborganida file_id va file_unique_id ni qaytaradi.
    Hech qanday fayl saqlanmaydi.
    """
    video = message.video
    file_id = video.file_id
    file_unique = video.file_unique_id
    duration = getattr(video, "duration", None)
    width = getattr(video, "width", None)
    height = getattr(video, "height", None)
    caption = message.caption or ""

    reply_text = (
        "🎬 Video qabul qilindi!\n\n"
        f"file_id:\n`{file_id}`\n\n"
        f"file_unique_id:\n`{file_unique}`\n\n"
        f"🔢 Duration: {duration}s\n"
        f"📐 Size: {width}x{height}\n"
    )
    if caption:
        reply_text += f"\n📎 Caption: {caption}\n"

    # Markdown tarzida file_id ko'rinishi uchun parse_mode qo'shing
    await message.reply(reply_text, parse_mode="Markdown")
