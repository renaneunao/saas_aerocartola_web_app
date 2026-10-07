"""Decode untrusted uploads and persist normalized avatars in PostgreSQL."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from database import get_db_connection, close_db_connection


def normalize_photo(payload):
    if not payload or len(payload) > 2 * 1024 * 1024:
        raise ValueError('Envie uma imagem de até 2 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError('A imagem tem resolução muito alta.')
                image = ImageOps.exif_transpose(image).convert('RGB')
                image = ImageOps.fit(image, (256, 256))
                result = BytesIO()
                image.save(result, format='JPEG', quality=88)
                return result.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Envie uma imagem válida em JPG, PNG ou WebP.') from None


def save_photo(user_id, payload):
    normalized = normalize_photo(payload)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS acw_user_photos (
                user_id INTEGER PRIMARY KEY REFERENCES acw_users(id) ON DELETE CASCADE,
                photo BYTEA NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
            cursor.execute('''INSERT INTO acw_user_photos (user_id, photo) VALUES (%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET photo=EXCLUDED.photo, updated_at=NOW()''',
                (user_id, normalized))
        conn.commit()
    finally:
        close_db_connection(conn)


def read_photo(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.acw_user_photos')")
            if not cursor.fetchone()[0]:
                return None
            cursor.execute('SELECT photo FROM acw_user_photos WHERE user_id=%s', (user_id,))
            row = cursor.fetchone()
            return bytes(row[0]) if row else None
    finally:
        close_db_connection(conn)
