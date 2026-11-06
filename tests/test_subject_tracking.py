import numpy as np

from wathba.inference import select_person


def test_initial_largest_subject_is_selected_when_unambiguous():
    boxes = np.array([[0, 0, 100, 200], [300, 0, 340, 90]])
    selected, reason = select_person(boxes)
    assert selected.tolist() == boxes[0].tolist()
    assert reason == ""


def test_ambiguous_people_require_selection():
    selected, reason = select_person([[0, 0, 100, 200], [200, 0, 300, 200]])
    assert selected is None
    assert "subject region" in reason


def test_tracker_does_not_switch_to_larger_bystander():
    previous = np.array([20, 20, 120, 220])
    boxes = np.array([[25, 22, 125, 222], [300, 0, 500, 450]])
    selected, _ = select_person(boxes, previous)
    assert selected.tolist() == boxes[0].tolist()


def test_person_leaving_is_not_replaced_by_someone_else():
    selected, reason = select_person([[300, 0, 500, 450]], np.array([20, 20, 120, 220]))
    assert selected is None
    assert "left" in reason
