from app.services.strategy.base import Parameter, ParameterType


def test_parameter_to_dict_matches_frontend_contract():
    param = Parameter(
        name="short_period",
        param_type=ParameterType.INT,
        default=5,
        min_value=1,
        max_value=30,
        description="Short MA period",
    )

    payload = param.to_dict()

    assert payload["type"] == "slider"
    assert payload["min"] == 1
    assert payload["max"] == 30
    assert payload["default"] == 5
    assert payload["description"] == "Short MA period"
