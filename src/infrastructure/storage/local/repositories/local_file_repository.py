from datetime import datetime
import hashlib
import os
from uuid import uuid4

from pathlib import Path
from typing import Optional

from domain.entities.file import File, FileHashType
from domain.repositories.file_repository import FileRepository


class LocalFileRepository(FileRepository):
    def __init__(self):
        self.__block_size = 65536
    
    def __get_creation_datetime(self, p: Path) -> datetime:
        if not p.exists():
            raise FileNotFoundError()

        stat = p.stat()

        # MacOS and Windows
        if hasattr(stat, "st_birthtime"):
            ts = stat.st_birthtime
            if ts:
                return datetime.fromtimestamp(ts)

        # Linux
        try:
            stx = os.statx(str(p), 0)
            btime = getattr(stx, "stx_btime", None)
            if btime and btime.tv_sec:
                return datetime.fromtimestamp(btime.tv_sec)
        except Exception:
            pass

        ts = stat.st_mtime
        return datetime.fromtimestamp(ts)
    
    def __get_last_modified(self, p: Path) -> datetime:
        if not p.exists():
            raise FileNotFoundError()
        ts = p.stat().st_mtime
        dt = datetime.fromtimestamp(ts)
        return dt
    
    def __fielname_without_all_extensions(self, p: Path) -> str:
        if not p.suffixes:
            return p.name
        all_suffix = ''.join(p.suffixes)
        return p.name[:-len(all_suffix)]

    def get_from_path(self, file_path: str, hash_type: Optional[FileHashType]) -> File:
        p = Path(file_path)

        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not p.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        hash_digest = None
        hash_func = None

        if hash_type == FileHashType.SHA1:
            hash_func = hashlib.sha1()
        elif hash_type == FileHashType.SHA256:
            hash_func = hashlib.sha256()
        elif hash_type == FileHashType.SHA3_512:
            hash_func = hashlib.sha3_512()
        elif hash_type == FileHashType.BLAKE2B:
            hash_func = hashlib.blake2b()

        if hash_func is not None:
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(self.__block_size), b""):
                    hash_func.update(chunk)
            hash_digest = hash_func.hexdigest()

        return File(
            identifier = uuid4(),
            enabled =  True,
            registration_date = self.__get_creation_datetime(p),
            last_update = self.__get_last_modified(p),
            name = self.__fielname_without_all_extensions(p),
            extension = ''.join(p.suffixes).lstrip('.'),
            size = p.stat().st_size,
            path = str(p.parent),
            hash_digest = hash_digest,
            hash_type = hash_type
        )

    def delete(self, file_path: str) -> File:
        file = self.get_from_path(file_path)
        p = Path(file_path)
        p.unlink()
        return file
