import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import json
import os
from typing import Callable, Dict, Optional
from uuid import uuid4

from domain.entities.file import File, FileHashType
from domain.entities.report import Report
from domain.repositories.file_repository import FileRepository
from domain.repositories.interfaces.report_interface import CheckedReportInterface
from domain.repositories.report_repository import ReportRepository
from infrastructure.persistence.json.config import JSON_DB_FOLDER


logger = logging.getLogger(__name__)


class JsonReportRepository(ReportRepository):
    IGNORE_DIRS = {
        "$recycle.bin",
        "system volume information",
        ".trash",
        ".ds_store",
        ".spotlight-v100"
    }

    def __should_ignore(self, path: str) -> bool:
        """Check if a folder or file should be ignored."""
        parts = [p.lower() for p in os.path.normpath(path).split(os.sep)]
        return any(part in self.IGNORE_DIRS for part in parts)

    def __relative_path(self, root_path: str, file_path: str) -> str:
        """Return a normalized relative path for comparison."""
        return os.path.normpath(
            os.path.relpath(os.path.normpath(file_path), os.path.normpath(root_path))
        )

    def __file_to_dict(self, relative_path: str, file: File) -> dict:
        return {
            'identifier': str(file.identifier),
            'enabled': file.enabled,
            'registration_date': str(file.registration_date),
            'last_update': str(file.last_update),
            'name': file.name,
            'extension': file.extension,
            'size': file.size,
            'relative_path': relative_path,
            'path': file.path,
            'hash_digest': file.hash_digest,
            'hash_type': file.hash_type.value if file.hash_type else None
        }

    def __load_inventory(self, inventory_path: str) -> Dict[str, str]:
        """Load a previous inventory and return a map of relative paths to hashes."""
        with open(inventory_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        files = data.get("files", [])
        inventory = {}
        for item in files:
            relative = item.get("relative_path")
            if not relative:
                # Fallback for older inventories without relative_path
                root_path = data.get("root_path", "")
                absolute_path = os.path.normpath(
                    os.path.join(root_path, item.get("path", ""), f"{item.get('name', '')}.{item.get('extension', '')}")
                )
                relative = self.__relative_path(root_path, absolute_path)
            inventory[os.path.normpath(relative)] = item.get("hash_digest")
        return inventory

    def __scan_paths(self, root_path: str) -> list:
        """Return a list of file paths under root_path that should be processed."""
        file_paths = []
        for folder, _, files in os.walk(root_path):
            if self.__should_ignore(folder):
                continue
            for name in files:
                path = os.path.join(folder, name)
                if not self.__should_ignore(path):
                    file_paths.append(path)
        return file_paths

    def generate(
        self,
        root_path: str,
        hash_type: FileHashType,
        workers: int,
        file_repository: FileRepository,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Report:
        if not os.path.isdir(root_path):
            raise ValueError(f"Directory does not exist: {root_path}")

        file_paths = self.__scan_paths(root_path)
        files_by_path: Dict[str, File] = {}
        total = len(file_paths)
        completed = 0
        errors = []

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(file_repository.get_from_path, path, hash_type): path
                for path in file_paths
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    result = future.result()
                    relative = self.__relative_path(root_path, path)
                    files_by_path[relative] = result
                except Exception as exc:
                    logger.error("Error processing %s: %s", path, exc)
                    errors.append(f"{path}: {exc}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        response = Report(
            identifier=uuid4(),
            enabled=True,
            registration_date=datetime.now(),
            last_update=datetime.now(),
            root_path=root_path,
            files=list(files_by_path.values())
        )

        reports_folder = os.path.join(JSON_DB_FOLDER or "", "reports/")
        os.makedirs(reports_folder, exist_ok=True)

        if output_path:
            destination = output_path
        else:
            timestamp = str(response.registration_date).replace(':', '-').replace('.', '-')
            destination = os.path.join(reports_folder, f"{timestamp}.json")

        json_data = {
            'identifier': str(response.identifier),
            'enabled': response.enabled,
            'registration_date': str(response.registration_date),
            'last_update': str(response.last_update),
            'root_path': root_path,
            'files': [self.__file_to_dict(relative, f) for relative, f in files_by_path.items()],
            'errors': errors
        }

        with open(destination, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)

        if errors:
            logger.warning("Inventory generated with %d error(s).", len(errors))

        return response

    def verify(
        self,
        root_path: str,
        inventory_path: str,
        hash_type: FileHashType,
        workers: int,
        file_repository: FileRepository,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> CheckedReportInterface:
        if not os.path.isdir(root_path):
            raise ValueError(f"Directory does not exist: {root_path}")
        if not os.path.isfile(inventory_path):
            raise ValueError(f"Inventory file does not exist: {inventory_path}")

        expected_files = self.__load_inventory(inventory_path)
        current_paths = self.__scan_paths(root_path)
        current_files: Dict[str, str] = {}
        total = len(current_paths)
        completed = 0
        errors = []

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(file_repository.get_from_path, path, hash_type): path
                for path in current_paths
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    result = future.result()
                    relative = self.__relative_path(root_path, path)
                    current_files[relative] = result.hash_digest
                except Exception as exc:
                    logger.error("Error verifying %s: %s", path, exc)
                    errors.append(f"{path}: {exc}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        modified_files = []
        missing_files = []

        for relative, expected_hash in expected_files.items():
            if relative not in current_files:
                missing_files.append(relative)
            elif current_files[relative] != expected_hash:
                modified_files.append(relative)

        added_files = [
            relative for relative in current_files
            if relative not in expected_files
        ]

        result = CheckedReportInterface()
        result.reportidentifier = uuid4()
        result.date = datetime.now()
        result.hash_algo = hash_type
        result.workers = workers
        result.modified_files = modified_files
        result.missing_files = missing_files
        result.added_files = added_files
        result.errors = errors

        logger.info(
            "Verification complete: %d modified, %d missing, %d added, %d errors.",
            len(modified_files), len(missing_files), len(added_files), len(errors)
        )

        return result
