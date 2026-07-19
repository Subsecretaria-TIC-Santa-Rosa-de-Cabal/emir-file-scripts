import hashlib
import os
import tempfile

import pytest

from domain.entities.file import FileHashType
from infrastructure.persistence.json.repositories.json_report_repository import JsonReportRepository
from infrastructure.storage.local.repositories.local_file_repository import LocalFileRepository


@pytest.fixture
def sample_dir():
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "a.txt"), "w", encoding="utf-8") as f:
            f.write("hello")
        with open(os.path.join(tmp, "b.txt"), "w", encoding="utf-8") as f:
            f.write("world")
        yield tmp


@pytest.fixture
def inventory_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


class TestLocalFileRepository:
    def test_get_from_path_returns_file_with_sha256(self, sample_dir):
        repo = LocalFileRepository()
        file_path = os.path.join(sample_dir, "a.txt")
        file = repo.get_from_path(file_path, FileHashType.SHA256)

        assert file.name == "a"
        assert file.extension == "txt"
        assert file.size == 5
        assert file.path == sample_dir
        assert file.hash_type == FileHashType.SHA256

        expected = hashlib.sha256(b"hello").hexdigest()
        assert file.hash_digest == expected


class TestJsonReportRepository:
    def test_generate_creates_inventory(self, sample_dir, inventory_dir):
        file_repo = LocalFileRepository()
        report_repo = JsonReportRepository()

        output = os.path.join(inventory_dir, "inventory.json")
        report = report_repo.generate(
            root_path=sample_dir,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
            output_path=output,
        )

        assert len(report.files) == 2
        assert os.path.isfile(output)

        with open(output, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
        assert data["root_path"] == sample_dir
        assert len(data["files"]) == 2
        assert "errors" in data

    def test_verify_detects_no_changes(self, sample_dir, inventory_dir):
        file_repo = LocalFileRepository()
        report_repo = JsonReportRepository()

        output = os.path.join(inventory_dir, "inventory.json")
        report_repo.generate(
            root_path=sample_dir,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
            output_path=output,
        )

        result = report_repo.verify(
            root_path=sample_dir,
            inventory_path=output,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
        )

        assert len(result.modified_files) == 0
        assert len(result.missing_files) == 0
        assert len(result.added_files) == 0
        assert len(result.errors) == 0

    def test_verify_detects_modifications(self, sample_dir, inventory_dir):
        file_repo = LocalFileRepository()
        report_repo = JsonReportRepository()

        output = os.path.join(inventory_dir, "inventory.json")
        report_repo.generate(
            root_path=sample_dir,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
            output_path=output,
        )

        with open(os.path.join(sample_dir, "a.txt"), "w", encoding="utf-8") as f:
            f.write("modified")

        result = report_repo.verify(
            root_path=sample_dir,
            inventory_path=output,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
        )

        assert "a.txt" in result.modified_files
        assert len(result.missing_files) == 0
        assert len(result.added_files) == 0

    def test_verify_detects_missing_and_added_files(self, sample_dir, inventory_dir):
        file_repo = LocalFileRepository()
        report_repo = JsonReportRepository()

        output = os.path.join(inventory_dir, "inventory.json")
        report_repo.generate(
            root_path=sample_dir,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
            output_path=output,
        )

        os.remove(os.path.join(sample_dir, "b.txt"))
        with open(os.path.join(sample_dir, "c.txt"), "w", encoding="utf-8") as f:
            f.write("new")

        result = report_repo.verify(
            root_path=sample_dir,
            inventory_path=output,
            hash_type=FileHashType.SHA256,
            workers=2,
            file_repository=file_repo,
        )

        assert "b.txt" in result.missing_files
        assert "c.txt" in result.added_files
