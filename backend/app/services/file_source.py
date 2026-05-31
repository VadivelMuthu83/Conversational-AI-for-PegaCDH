"""
File source abstraction: local | s3 | polaris.
Uses settings.files_path (resolves KNOWLEDGE_PATH or LOCAL_FILES_PATH).
"""
import logging
from pathlib import Path
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class FileInfo:
    def __init__(self, name, path, size, last_modified=None):
        self.name = name
        self.path = path
        self.size = size
        self.last_modified = last_modified

    def to_dict(self):
        sz = self.size
        for unit in ["B", "KB", "MB", "GB"]:
            if sz < 1024:
                human = f"{sz:.1f} {unit}"
                break
            sz /= 1024
        else:
            human = f"{sz:.1f} TB"
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "size_human": human,
            "last_modified": self.last_modified,
        }


class LocalFileSource:
    def __init__(self, base_path: str = None):
        # Use resolved property: KNOWLEDGE_PATH → LOCAL_FILES_PATH
        resolved = base_path or settings.files_path
        self.base_path = Path(resolved).resolve()
        logger.info(f"LocalFileSource: {self.base_path}")

    def list_files(self) -> List[FileInfo]:
        if not self.base_path.exists():
            logger.warning(f"Path not found: {self.base_path}")
            return []
        files = []
        for p in sorted(self.base_path.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rel = str(p.relative_to(self.base_path))
                st = p.stat()
                files.append(FileInfo(p.name, rel, st.st_size, str(st.st_mtime)))
        return files

    def read_file(self, path: str) -> bytes:
        target = (self.base_path / path).resolve()
        if not str(target).startswith(str(self.base_path)):
            raise ValueError(f"Path traversal blocked: {path}")
        return target.read_bytes()

    def file_exists(self, path: str) -> bool:
        target = (self.base_path / path).resolve()
        return target.exists() and target.is_file()


class S3FileSource:
    def __init__(self):
        self.bucket = settings.S3_BUCKET
        self.prefix = settings.S3_PREFIX
        self._client = None

    def _get_client(self):
        if not self._client:
            import boto3
            self._client = boto3.client(
                "s3",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return self._client

    def list_files(self) -> List[FileInfo]:
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        kwargs = {"Bucket": self.bucket}
        if self.prefix:
            kwargs["Prefix"] = self.prefix
        files = []
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue
                name = obj["Key"].split("/")[-1]
                files.append(FileInfo(name, obj["Key"], obj["Size"], str(obj["LastModified"])))
        return files

    def read_file(self, path: str) -> bytes:
        resp = self._get_client().get_object(Bucket=self.bucket, Key=path)
        return resp["Body"].read()

    def file_exists(self, path: str) -> bool:
        try:
            self._get_client().head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False


def get_file_source():
    if settings.FILE_SOURCE == "s3":
        return S3FileSource()
    elif settings.FILE_SOURCE == "polaris":
        from app.polaris.catalog import PolarisFileSource
        return PolarisFileSource()
    return LocalFileSource()
