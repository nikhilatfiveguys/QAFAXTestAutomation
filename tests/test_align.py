from __future__ import annotations

import os
import unittest

from app.verify.align import align_documents
from app.verify.loaders import DocumentData, DocumentPage


class AlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_disable = os.environ.get("QAFAX_DISABLE_PROMPTS")
        os.environ["QAFAX_DISABLE_PROMPTS"] = "1"

    def tearDown(self) -> None:
        if self._prev_disable is None:
            os.environ.pop("QAFAX_DISABLE_PROMPTS", None)
        else:
            os.environ["QAFAX_DISABLE_PROMPTS"] = self._prev_disable

    def _document(self, pages: list[list[str]]) -> DocumentData:
        document_pages = [
            DocumentPage(index=i, text_lines=lines, image=None, dpi=None) for i, lines in enumerate(pages)
        ]
        return DocumentData(path=None, content=b"", sha256="sha", pages=document_pages)  # type: ignore[arg-type]

    def test_reordered_pages_align_by_content(self) -> None:
        reference = self._document([["alpha"], ["beta"], ["gamma"]])
        candidate = self._document([["beta"], ["gamma"], ["alpha"]])

        pairs, warnings = align_documents(reference, candidate)

        aligned = [(pair.reference.text_lines, pair.candidate.text_lines) for pair in pairs]

        self.assertEqual(len(pairs), 3)
        self.assertEqual(aligned[0][0], ["alpha"])
        self.assertEqual(aligned[0][1], ["alpha"])
        self.assertEqual(aligned[1][0], ["beta"])
        self.assertEqual(aligned[1][1], ["beta"])
        self.assertEqual(aligned[2][0], ["gamma"])
        self.assertEqual(aligned[2][1], ["gamma"])
        self.assertFalse(warnings)

    def test_low_confidence_records_warning(self) -> None:
        reference = self._document([["alpha"], ["beta"]])
        candidate = self._document([["zeta"], ["theta"]])

        pairs, warnings = align_documents(reference, candidate, low_confidence_threshold=0.95)

        self.assertEqual(len(pairs), 2)
        self.assertTrue(any("Low alignment confidence" in warning for warning in warnings))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
