"""Utility functions for Enhanced Content-Aware Fill"""


class UtilsMixin:
    """Mixin class for utility methods"""

    @staticmethod
    def check_module_available(module_name):
        """Check if a Python module is available

        Args:
            module_name: Name of the module to check

        Returns:
            bool: True if module is available, False otherwise
        """
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False
