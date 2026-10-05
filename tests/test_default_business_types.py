from core.default_business_types import get_default_business_types


def test_children_hair_salon_is_available_as_a_business_type():
    assert (
        "children_hair_salon",
        "Детская парикмахерская",
        "Парикмахерская для детей и семей с детьми",
    ) in get_default_business_types()
