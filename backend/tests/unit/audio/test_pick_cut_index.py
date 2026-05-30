from backend.audio.segmentation import pick_cut_index


class TestBasicMinFinding:
    def test_finds_minimum_in_window(self):
        peaks = [0.9, 0.9, 0.1, 0.9, 0.9]
        assert pick_cut_index(peaks, 0, 5) == 2

    def test_ties_resolve_to_earliest(self):
        peaks = [0.5, 0.1, 0.1, 0.5]
        assert pick_cut_index(peaks, 0, 4) == 1

    def test_window_start_included(self):
        # Start = 2, so index 0 and 1 are excluded
        peaks = [0.0, 0.0, 0.5, 0.1, 0.9]
        assert pick_cut_index(peaks, 2, 5) == 3

    def test_window_end_exclusive(self):
        # End = 3, so index 3 and 4 are excluded
        peaks = [0.9, 0.1, 0.9, 0.0, 0.0]
        assert pick_cut_index(peaks, 0, 3) == 1


class TestEdgeCases:
    def test_empty_list_returns_none(self):
        assert pick_cut_index([], 0, 0) is None

    def test_zero_length_window_returns_none(self):
        assert pick_cut_index([0.5, 0.5], 2, 2) is None

    def test_inverted_window_returns_none(self):
        assert pick_cut_index([0.5, 0.5], 3, 1) is None

    def test_start_beyond_list_returns_none(self):
        assert pick_cut_index([0.5], 5, 10) is None

    def test_single_element_window(self):
        peaks = [0.9, 0.1, 0.9]
        assert pick_cut_index(peaks, 1, 2) == 1

    def test_window_clamped_to_list_bounds(self):
        peaks = [0.9, 0.1]
        # end=100 is clamped to len(peaks)=2
        assert pick_cut_index(peaks, 0, 100) == 1
