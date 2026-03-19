"""
Navigation provider system for Zen IDE.

Supports pluggable backends: custom (regex) and terraform.
Language-specific code navigation: Python, Terraform.
"""

from navigation.custom_provider import CustomProvider
from navigation.navigation_provider import NavigationProvider
from navigation.terraform_provider import TerraformProvider

__all__ = ["NavigationProvider", "CustomProvider", "TerraformProvider"]
