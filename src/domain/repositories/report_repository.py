from abc import ABC, abstractmethod
from typing import Callable, Optional

from domain.entities.file import FileHashType
from domain.entities.report import Report
from domain.repositories.file_repository import FileRepository
from domain.repositories.interfaces.report_interface import CheckedReportInterface


class ReportRepository(ABC):
    @abstractmethod
    def generate(
        self,
        root_path: str,
        hash_type: FileHashType,
        workers: int,
        file_repository: FileRepository,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int,int], None]] = None
    ) -> Report:
        pass

    @abstractmethod
    def verify(
        self,
        root_path: str,
        inventory_path: str,
        hash_type: FileHashType,
        workers: int,
        file_repository: FileRepository,
        progress_callback: Optional[Callable[[int,int], None]] = None
    ) -> CheckedReportInterface:
        pass
