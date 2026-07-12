from __future__ import annotations

import unittest

from evaluation.scripts.merge_api_results import merge_api_rows


class ApiResumeTest(unittest.TestCase):
    def test_merge_api_rows_requires_disjoint_complete_results(self) -> None:
        rows = merge_api_rows([[{"request_id": "b"}], [{"request_id": "a"}]], expected=2)

        self.assertEqual(["a", "b"], [row["request_id"] for row in rows])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            merge_api_rows([[{"request_id": "a"}], [{"request_id": "a"}]], expected=1)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            merge_api_rows([[{"request_id": "a"}]], expected=2)


if __name__ == "__main__":
    unittest.main()
