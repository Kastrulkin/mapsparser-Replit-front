import sys

from services.sales_room_file_storage import load_sales_room_file, store_sales_room_file


def test_sales_room_file_storage_local_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SALES_ROOM_STORAGE_BACKEND", "local")
    monkeypatch.setenv("SALES_ROOM_UPLOAD_DIR", str(tmp_path))

    stored = store_sales_room_file(
        room_id="room-1",
        file_id="file-1",
        extension="txt",
        content=b"hello",
        original_name="hello.txt",
        mime_type="text/plain",
    )

    assert stored["backend"] == "local"
    assert load_sales_room_file(str(stored["storage_path"])) == b"hello"


def test_sales_room_file_storage_s3_roundtrip(monkeypatch) -> None:
    fake_client = _FakeS3Client()
    fake_boto3 = _FakeBoto3(fake_client)
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("SALES_ROOM_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("SALES_ROOM_S3_BUCKET", "localos-test")
    monkeypatch.setenv("SALES_ROOM_S3_PREFIX", "sales-room-files")
    monkeypatch.setenv("SALES_ROOM_S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("SALES_ROOM_S3_SECRET_ACCESS_KEY", "secret")

    stored = store_sales_room_file(
        room_id="room-1",
        file_id="file-1",
        extension="txt",
        content=b"hello-s3",
        original_name="hello.txt",
        mime_type="text/plain",
    )

    assert stored["backend"] == "s3"
    assert stored["storage_path"] == "s3://localos-test/sales-room-files/room-1/file-1.txt"
    assert load_sales_room_file(str(stored["storage_path"])) == b"hello-s3"


class _FakeBody:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects = {}

    def put_object(self, **kwargs):
        bucket = kwargs["Bucket"]
        key = kwargs["Key"]
        self.objects[(bucket, key)] = kwargs["Body"]

    def get_object(self, **kwargs):
        bucket = kwargs["Bucket"]
        key = kwargs["Key"]
        return {"Body": _FakeBody(self.objects[(bucket, key)])}


class _FakeBoto3:
    def __init__(self, client) -> None:
        self._client = client

    def client(self, *args, **kwargs):
        return self._client
