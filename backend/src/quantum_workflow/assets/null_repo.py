"""v1 no-op lookup implementation of the asset repository.

`lookup` always returns an empty list (no similarity search), but `save`
persists successfully executed code and metadata to disk, accumulating
training data for the v2 vector-search implementation.
"""
import uuid
from pathlib import Path

from quantum_workflow.schemas.exec import ExecResult, ExecStatus
from quantum_workflow.schemas.intent import ParsedIntent

from .protocol import Asset, AssetMatch


class NullAssetRepo:
    """v1 asset-repository implementation: lookup returns no candidates, but successful executions are persisted for v2 use."""

    def __init__(self, root: Path):
        """Initialize the repository, ensuring the root directory exists.

        Args:
            root: Root path for asset storage; created automatically if missing.
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def lookup(self, intent: ParsedIntent, top_k: int = 5) -> list[AssetMatch]:
        """In v1 always return an empty list; no similarity search is performed."""
        return []

    def save(
        self, request_id: str, code: str, intent: ParsedIntent, exec_result: ExecResult
    ) -> None:
        """Persist successfully executed code and its metadata to disk.

        Only writes when exec_result.status is SUCCESS; failed results
        are discarded. Each asset gets its own directory named with a
        random UUID, containing code.py, intent.json, exec_result.json,
        and request_id.
        """
        # Failed executions are not worth saving; skip them.
        if exec_result.status != ExecStatus.SUCCESS:
            return
        asset_id = str(uuid.uuid4())
        asset_dir = self.root / asset_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "code.py").write_text(code)
        (asset_dir / "intent.json").write_text(intent.model_dump_json(indent=2))
        (asset_dir / "exec_result.json").write_text(exec_result.model_dump_json(indent=2))
        (asset_dir / "request_id").write_text(request_id)

    def get(self, asset_id: str) -> Asset | None:
        """Load an asset from disk by id; return None if its directory does not exist.

        Args:
            asset_id: Asset directory name (UUID string).
        Returns:
            The Asset, or None when the directory is missing.
        """
        asset_dir = self.root / asset_id
        if not asset_dir.exists():
            return None
        return Asset(
            asset_id=asset_id,
            code=(asset_dir / "code.py").read_text(),
            intent=ParsedIntent.model_validate_json((asset_dir / "intent.json").read_text()),
            exec_result=ExecResult.model_validate_json(
                (asset_dir / "exec_result.json").read_text()
            ),
        )

    def list_ids(self) -> list[str]:
        """Return the list of asset ids (i.e. subdirectory names) under root."""
        return [p.name for p in self.root.iterdir() if p.is_dir()]
