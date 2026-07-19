import logging
import os
import sys
from pathlib import Path

from tqdm import tqdm
import typer


current_file = Path(__file__).resolve()
src_dir = current_file.parents[2]
sys.path.insert(0, str(src_dir))

from domain.entities.file import FileHashType
from infrastructure.persistence.json.repositories.json_report_repository import JsonReportRepository
from infrastructure.storage.local.repositories.local_file_repository import LocalFileRepository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = typer.Typer(help="Disk Integrity Checker - Create or verify file inventories")


def _resolve_hash_type(hash_algo: str) -> FileHashType:
    try:
        return FileHashType[hash_algo.upper()]
    except KeyError as exc:
        valid = ", ".join(ht.value for ht in FileHashType)
        raise typer.BadParameter(
            f"Invalid hash algorithm '{hash_algo}'. Valid options: {valid}"
        ) from exc


def _build_progress_bar(desc: str):
    pbar = tqdm(desc=desc, unit="file")

    def callback(done: int, total: int):
        pbar.total = total
        pbar.n = done
        pbar.refresh()
        if done >= total:
            pbar.close()

    return callback


@app.command()
def inventory(
    directory: str = typer.Argument(..., help="Directory to scan"),
    output_file: str = typer.Option("inventory.json", help="Inventory file path"),
    hash_algo: str = typer.Option("sha1", help="Hash algorithm (e.g., sha1, sha256, sha3_512, blake2b)"),
    workers: int = typer.Option(8, help="Number of parallel workers"),
):
    """
    Create a file inventory for the given directory.
    """
    typer.echo("=" * 60)
    typer.echo("   Disk Integrity Checker - Inventory")
    typer.echo("=" * 60)

    if workers is None or workers <= 0:
        workers = os.cpu_count() or 1

    hash_type = _resolve_hash_type(hash_algo)
    file_repository = LocalFileRepository()
    repository = JsonReportRepository()

    report = repository.generate(
        root_path=directory,
        hash_type=hash_type,
        workers=workers,
        file_repository=file_repository,
        output_path=output_file,
        progress_callback=_build_progress_bar("Scanning files"),
    )

    typer.echo(f"Inventory saved to: {output_file}")
    typer.echo(f"Files scanned: {len(report.files)}")
    typer.echo(f"Root path: {report.root_path}")


@app.command()
def verify(
    directory: str = typer.Argument(..., help="Directory to verify"),
    inventory_file: str = typer.Option(..., help="Path to the inventory JSON to compare against"),
    hash_algo: str = typer.Option("sha1", help="Hash algorithm used in the inventory"),
    workers: int = typer.Option(8, help="Number of parallel workers"),
):
    """
    Verify a directory against a previously generated inventory.
    """
    typer.echo("=" * 60)
    typer.echo("   Disk Integrity Checker - Verify")
    typer.echo("=" * 60)

    if workers is None or workers <= 0:
        workers = os.cpu_count() or 1

    hash_type = _resolve_hash_type(hash_algo)
    file_repository = LocalFileRepository()
    repository = JsonReportRepository()

    result = repository.verify(
        root_path=directory,
        inventory_path=inventory_file,
        hash_type=hash_type,
        workers=workers,
        file_repository=file_repository,
        progress_callback=_build_progress_bar("Verifying files"),
    )

    typer.echo(f"Modified files: {len(result.modified_files)}")
    typer.echo(f"Missing files: {len(result.missing_files)}")
    typer.echo(f"Added files: {len(result.added_files)}")
    typer.echo(f"Errors: {len(result.errors)}")

    if result.modified_files:
        typer.echo("Modified:")
        for path in result.modified_files:
            typer.echo(f"  - {path}")
    if result.missing_files:
        typer.echo("Missing:")
        for path in result.missing_files:
            typer.echo(f"  - {path}")
    if result.added_files:
        typer.echo("Added:")
        for path in result.added_files:
            typer.echo(f"  - {path}")
    if result.errors:
        typer.echo("Errors:")
        for error in result.errors:
            typer.echo(f"  - {error}")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app()