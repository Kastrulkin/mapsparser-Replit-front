from parser_interception import YandexMapsInterceptionParser


def test_fetch_reviews_business_comment_is_preserved_as_owner_response():
    parser = YandexMapsInterceptionParser()

    reviews = parser._extract_reviews_from_api(
        {
            "reviews": [
                {
                    "reviewId": "review-with-business-comment",
                    "author": {"name": "Алина"},
                    "rating": 5,
                    "text": "Прекрасная парикмахерска",
                    "publishedAt": "2026-08-24T15:49:36.374Z",
                    "businessComment": {
                        "text": "Спасибо за ваш отзыв!",
                        "date": "2026-08-25T09:00:00Z",
                    },
                }
            ]
        },
        "https://yandex.com/maps/api/business/fetchReviews",
    )

    assert reviews == [
        {
            "id": "review-with-business-comment",
            "author": "Алина",
            "rating": "5",
            "text": "Прекрасная парикмахерска",
            "date": "2026-08-24T15:49:36.374+00:00",
            "org_reply": "Спасибо за ваш отзыв!",
            "response_text": "Спасибо за ваш отзыв!",
            "response_date": "2026-08-25T09:00:00Z",
            "has_response": True,
        }
    ]
