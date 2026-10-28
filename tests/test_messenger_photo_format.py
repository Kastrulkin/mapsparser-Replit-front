import io
import pytest
from PIL import Image
from services.operator_attachments import image_identity
from core.upload_security import upload_content_matches_type

@pytest.mark.parametrize('format,mime,extension',[('WEBP','image/webp','.webp'),('PNG','image/png','.png'),('JPEG','image/jpeg','.jpg')])
def test_messenger_image_with_placeholder_jpg_uses_actual_format(format,mime,extension):
    output=io.BytesIO()
    Image.new('RGB',(12,12)).save(output,format=format)
    name,actual=image_identity(output.getvalue(),'photo.jpg')
    assert name=='photo'+extension
    assert actual==mime
    assert upload_content_matches_type(extension=extension.lstrip('.'),mime_type=actual,content=output.getvalue())

def test_unsupported_image_cannot_be_disguised_as_jpg():
    output=io.BytesIO()
    Image.new('RGB',(12,12)).save(output,format='GIF')
    with pytest.raises(ValueError):image_identity(output.getvalue(),'photo.jpg')
