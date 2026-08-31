from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import Type

from docling_core.types.doc import DocItemLabel

from docling.datamodel.base_models import Page, TableStructurePrediction
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import BaseTableStructureOptions
from docling.models.base_model import BaseModelWithOptions, BasePageModel

# The three table backends share one policy for which layout regions to run table
# structure on, and when to trust the result. Centralising it here keeps the
# backends from drifting apart as that policy evolves.


def table_candidate_labels(try_table_on_picture: bool) -> list[DocItemLabel]:
    """Layout labels a table backend should attempt structure recognition on.

    Regions the layout model already identified as tables are always processed.
    With ``try_table_on_picture`` enabled, picture regions are processed too: the
    layout model sometimes labels a table as a picture when its rows embed icons
    or diagrams, which otherwise drops the whole table from the output (#3410).
    """
    labels = [DocItemLabel.TABLE, DocItemLabel.DOCUMENT_INDEX]
    if try_table_on_picture:
        labels.append(DocItemLabel.PICTURE)
    return labels


def is_table_like(num_rows: int, num_cols: int) -> bool:
    """Whether a table-structure prediction is strong enough to keep.

    Only used to gate picture regions promoted by ``try_table_on_picture``. A
    genuine table has at least two rows and two columns, so smaller predictions
    are treated as the model forcing structure onto a real image, and the region
    is left as a picture instead.
    """
    return num_rows >= 2 and num_cols >= 2


class BaseTableStructureModel(BasePageModel, BaseModelWithOptions, ABC):
    """Shared interface for table structure models."""

    enabled: bool

    @classmethod
    @abstractmethod
    def get_options_type(cls) -> Type[BaseTableStructureOptions]:
        """Return the options type supported by this table model."""

    @abstractmethod
    def predict_tables(
        self,
        conv_res: ConversionResult,
        pages: Sequence[Page],
    ) -> Sequence[TableStructurePrediction]:
        """Produce table structure predictions for the provided pages."""

    def __call__(
        self,
        conv_res: ConversionResult,
        page_batch: Iterable[Page],
    ) -> Iterable[Page]:
        if not getattr(self, "enabled", True):
            yield from page_batch
            return

        pages = list(page_batch)
        predictions = self.predict_tables(conv_res, pages)

        for page, prediction in zip(pages, predictions):
            page.predictions.tablestructure = prediction
            yield page
