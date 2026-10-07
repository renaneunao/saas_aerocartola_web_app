import unittest
from io import BytesIO
from unittest.mock import patch
import os

for key, value in {'POSTGRES_HOST':'localhost','POSTGRES_USER':'test',
                   'POSTGRES_PASSWORD':'test','POSTGRES_DB':'test'}.items():
    os.environ.setdefault(key,value)
from PIL import Image
from utils.user_photo import normalize_photo


class UserPhotoTests(unittest.TestCase):
    def test_normalizes_and_resizes_png(self):
        source = BytesIO()
        Image.new('RGBA', (100, 180), 'blue').save(source, format='PNG')
        normalized = normalize_photo(source.getvalue())
        with Image.open(BytesIO(normalized)) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (256, 256))

    def test_rejects_fake_image(self):
        with self.assertRaises(ValueError):
            normalize_photo(b'<script>alert(1)</script>')

    def test_rejects_large_or_empty_upload(self):
        for payload in (b'', b'x' * (2 * 1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                normalize_photo(payload)
