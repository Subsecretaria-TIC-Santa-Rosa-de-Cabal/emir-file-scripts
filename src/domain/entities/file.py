from datetime import datetime
from enum import Enum, unique
from typing import Optional
from uuid import UUID

from domain.entities.base import Base


@unique
class FileHashType(Enum):
    SHA1 = 'SHA1'
    SHA256 = 'SHA256'
    SHA3_512 = 'SHA3_512'
    BLAKE2B = 'BLAKE2B'

class File(Base):
    def __init__(
            self,
            identifier: UUID,
            enabled: bool,
            registration_date: datetime,
            last_update: datetime,
            name: str,
            extension: str,
            size: int,
            path: str,
            hash_digest: Optional[str],
            hash_type: Optional[FileHashType]
        ):
        super().__init__(
            identifier,
            enabled,
            registration_date,
            last_update,
        )
        self.__name = name
        self.__extension = extension
        self.__size = size
        self.__path = path
        self.__hash_digest = hash_digest
        self.__hash_type = hash_type

    @property
    def name(self) -> str:
        return self.__name

    @property
    def extension(self) -> str:
        return self.__extension
    
    @property
    def size(self) -> int:
        return self.__size
    
    @property
    def path(self) -> str:
        return self.__path
    
    @property
    def hash_digest(self) -> Optional[str]:
        return self.__hash_digest
    
    @property
    def hash_type(self) -> Optional[FileHashType]:
        return self.__hash_type
