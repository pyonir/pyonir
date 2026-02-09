import os
from pyonir.core.media import BaseMedia, ImageFormat
from pathlib import Path

from pyonir.tests.conftest import app_setup_path

frontend_path = Path(os.path.join(app_setup_path, "frontend", "public"))
temp_media_file = os.path.join(frontend_path, "test_image.png")
test_metadata = {
        "name": "test_image",
        "width": 800,
        "height": 600,
        "created_on": "2024-01-01 00:00:00"
    }

def test_basic_file_properties():
    media = BaseMedia(temp_media_file)

    assert media.file_path == temp_media_file
    assert media.file_ext == ".png"
    assert media.file_name == "test_image"
    assert media.file_dirname == str(Path(temp_media_file).parent.name)
    assert media.slug == f"{media.file_dirname}/test_image.png"

def test_encode_filename():
    file_ext = temp_media_file.split('.')[-1]
    encoded = BaseMedia.encode_filename(temp_media_file, test_metadata)
    assert isinstance(encoded, str)
    assert encoded.endswith(f".{file_ext}")
    assert "=" not in encoded  # No padding characters
    assert "/" not in encoded  # URL-safe encoding

def test_decode_filename():
    # Test with a known encoded filename
    encoded = "bmFtZT10ZXN0X2ltYWdlJndpZHRoPTgwMCZoZWlnaHQ9NjAw"
    decoded = BaseMedia.decode_filename(encoded)

    assert isinstance(decoded, dict)
    assert decoded.get('name') == "test_image"
    assert decoded.get('width') == "800"
    assert decoded.get('height') == "600"

def test_rename_media_file():
    media = BaseMedia(temp_media_file)
    old_path = media.file_path

    # Set test metadata
    media.data = test_metadata
    media.rename_media_file()

    assert media.file_path != old_path
    assert os.path.exists(media.file_path)
    assert not os.path.exists(old_path)
    # Set back to original for cleanup
    media.rename_media_file(os.path.basename(old_path))
    assert media.file_path == old_path

def test_resize_image():
    from PIL import Image
    from pyonir import Site

    # Create a real test image
    img_path = os.path.join(frontend_path, "test_resize.jpg")
    test_image = Image.new('RGB', (100, 100), color='red')
    test_image.save(img_path)

    media = BaseMedia(str(img_path))
    sizes = [(50, 50), (25, 25)]
    media.resize(sizes)

    # Check if thumbnail directory exists with resized images
    thumb_dir = Path(media.file_dirpath) / (Site.UPLOADS_THUMBNAIL_DIRNAME if Site else media.file_name)
    assert thumb_dir.exists()

    # Check if resized files exist
    for width, height in sizes:
        resized_file = thumb_dir / f"{media.file_name}--{width}x{height}{media.file_ext}"
        assert resized_file.exists()

    # Cleanup
    os.remove(img_path)
    for f in thumb_dir.glob("*"):
        os.remove(f)
    print("Removing thumbnail directory:", thumb_dir)
    thumb_dir.rmdir()

def test_compress_image():
    from PIL import Image

    # Create a test image
    input_path = frontend_path / "test_compress.jpg"
    output_path = frontend_path / "test_compress_output.jpg"

    test_image = Image.new('RGB', (100, 100), color='red')
    test_image.save(input_path)

    # Test compression
    BaseMedia.compress_image(str(input_path), str(output_path), quality=50)

    assert output_path.exists()
    # Compressed file should be smaller
    assert output_path.stat().st_size <= input_path.stat().st_size

    # Cleanup
    os.remove(input_path)
    os.remove(output_path)

def test_get_media_data():
    from PIL import Image

    # Create a test image
    img_path = frontend_path / "test_metadata.jpg"
    test_image = Image.new('RGB', (800, 600), color='red')
    test_image.save(img_path)

    media_data = BaseMedia.get_media_data(str(img_path))

    assert isinstance(media_data, dict)
    if media_data:
        assert 'width' in media_data
        assert 'height' in media_data
        assert media_data['width'] == 800
        assert media_data['height'] == 600

    os.remove(img_path)

def test_image_thumbnails():
    from pyonir import Site

    media = BaseMedia(os.path.join(frontend_path, "test_image.png"))
    media.resized_to(40, 40)
    t = media.thumbnails
    assert t.get(f'40x40') is not None

    thumb_dir = Path(media.file_dirpath) / (Site.UPLOADS_THUMBNAIL_DIRNAME if Site else media.file_name)

    for f in thumb_dir.glob("*"):
        os.remove(f)
    thumb_dir.rmdir()

