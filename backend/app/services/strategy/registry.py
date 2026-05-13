from typing import Dict, Type, Optional, List
from .base import Strategy


class StrategyRegistry:
    """
    Registry for managing strategy classes.

    Provides functionality to register, retrieve, and list available strategies.
    """

    _strategies: Dict[str, Type[Strategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[Strategy]) -> None:
        """
        Register a strategy class.

        Args:
            name: Unique strategy identifier
            strategy_class: Strategy class to register
        """
        if name in cls._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")

        if not issubclass(strategy_class, Strategy):
            raise TypeError(
                f"Strategy class must be a subclass of Strategy, "
                f"got {strategy_class.__name__}"
            )

        cls._strategies[name] = strategy_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[Strategy]]:
        """
        Get strategy class by name.

        Args:
            name: Strategy identifier

        Returns:
            Strategy class or None if not found
        """
        return cls._strategies.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, Type[Strategy]]:
        """
        Get all registered strategies.

        Returns:
            Dictionary mapping strategy names to strategy classes
        """
        return cls._strategies.copy()

    @classmethod
    def list_strategies(cls) -> List[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(cls._strategies.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a strategy.

        Args:
            name: Strategy identifier

        Returns:
            True if strategy was unregistered, False if not found
        """
        if name in cls._strategies:
            del cls._strategies[name]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered strategies (mainly for testing)."""
        cls._strategies.clear()


def register_strategy(name: str) -> Type[Strategy]:
    """
    Decorator to register a strategy class.

    Usage:
        @register_strategy("my_strategy")
        class MyStrategy(Strategy):
            ...

    Args:
        name: Unique strategy identifier

    Returns:
        Decorator function that registers the strategy class
    """

    def decorator(strategy_class: Type[Strategy]) -> Type[Strategy]:
        StrategyRegistry.register(name, strategy_class)
        return strategy_class

    return decorator
