from core.review_response_utils import extract_review_response_text


def test_extract_review_response_text_supports_business_comment() -> None:
    review = {"business_comment": "Спасибо за отзыв"}
    assert extract_review_response_text(review) == "Спасибо за отзыв"


def test_extract_review_response_text_supports_nested_business_comment() -> None:
    review = {"businessComment": {"text": "Ответ организации"}}
    assert extract_review_response_text(review) == "Ответ организации"


def test_extract_review_response_text_supports_answers_list() -> None:
    review = {"answers": [{"message": "Ответ из списка"}]}
    assert extract_review_response_text(review) == "Ответ из списка"
