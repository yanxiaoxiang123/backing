from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Union, List


class ParameterType(Enum):
    """Parameter types supported by the strategy engine."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CHOICE = "choice"


@dataclass
class Parameter:
    """
    Parameter definition for strategy configuration.

    Attributes:
        name: Parameter display name
        param_type: Type of parameter (int, float, bool, choice)
        default: Default value for the parameter
        min_value: Minimum allowed value (for int/float)
        max_value: Maximum allowed value (for int/float)
        choices: List of choices (for choice type)
        description: Parameter description for UI
    """

    name: str
    param_type: ParameterType
    default: Any
    min_value: Union[int, float, None] = None
    max_value: Union[int, float, None] = None
    choices: List[Any] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        """Validate parameter configuration."""
        if self.param_type == ParameterType.CHOICE and not self.choices:
            raise ValueError(
                f"Parameter '{self.name}' of type 'choice' must have choices defined"
            )

        if self.param_type in (ParameterType.INT, ParameterType.FLOAT):
            if self.min_value is not None and self.max_value is not None:
                if self.min_value > self.max_value:
                    raise ValueError(
                        f"Parameter '{self.name}': min_value ({self.min_value}) "
                        f"must be <= max_value ({self.max_value})"
                    )
            if self.default is not None:
                if self.min_value is not None and self.default < self.min_value:
                    raise ValueError(
                        f"Parameter '{self.name}': default ({self.default}) "
                        f"must be >= min_value ({self.min_value})"
                    )
                if self.max_value is not None and self.default > self.max_value:
                    raise ValueError(
                        f"Parameter '{self.name}': default ({self.default}) "
                        f"must be <= max_value ({self.max_value})"
                    )

        if self.param_type == ParameterType.BOOL and not isinstance(self.default, bool):
            raise ValueError(
                f"Parameter '{self.name}': bool parameter must have boolean default"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter to dictionary for serialization."""
        config_type = "input"
        if self.param_type in (ParameterType.INT, ParameterType.FLOAT):
            config_type = "slider"
        elif self.param_type == ParameterType.CHOICE:
            config_type = "select"

        return {
            "name": self.name,
            "type": config_type,
            "default": self.default,
            "min": self.min_value,
            "max": self.max_value,
            "step": 1
            if self.param_type == ParameterType.INT
            else 0.1
            if self.param_type == ParameterType.FLOAT
            else None,
            "options": [
                {"label": str(choice), "value": choice} for choice in self.choices
            ]
            if self.choices
            else None,
            "description": self.description,
        }


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.

    Subclasses must implement:
        - generate_signals: Generate trading signals from price data
        - get_parameters: Return strategy parameters
        - get_name: Return strategy name
        - get_description: Return strategy description
    """

    @abstractmethod
    def generate_signals(self, data: Any) -> Any:
        """
        Generate trading signals from market data.

        Args:
            data: DataFrame containing market data (OHLCV, indicators, etc.)

        Returns:
            DataFrame with added signal columns (typically 'signal' column)
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict[str, Parameter]:
        """
        Get strategy parameters.

        Returns:
            Dictionary mapping parameter names to Parameter objects
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get strategy name.

        Returns:
            Unique strategy identifier
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Get strategy description.

        Returns:
            Human-readable description of the strategy
        """
        pass
