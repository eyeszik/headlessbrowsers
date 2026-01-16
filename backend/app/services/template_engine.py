"""
Template engine with variable substitution and platform-specific rendering.
"""
from typing import Dict, Any, Optional
import re
from jinja2 import Environment, BaseLoader, TemplateSyntaxError
import logging

from backend.app.models.models import ContentTemplate, PlatformType

logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Template engine for content generation.

    Features:
    - Variable substitution with {{variable}} syntax
    - Platform-specific overrides
    - Validation and error handling
    - Default value support
    """

    def __init__(self):
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=False
        )

    def render_template(
        self,
        template: ContentTemplate,
        variables: Dict[str, Any],
        platform: Optional[PlatformType] = None
    ) -> str:
        """
        Render template with variables.

        Args:
            template: ContentTemplate object
            variables: Dict of variable values
            platform: Optional platform for platform-specific rendering

        Returns:
            Rendered content string

        Raises:
            ValueError: If required variables are missing
            TemplateSyntaxError: If template syntax is invalid
        """
        # Get template text (use platform override if available)
        template_text = template.template_text

        if platform and template.platform_overrides:
            platform_override = template.platform_overrides.get(platform.value)
            if platform_override:
                template_text = platform_override
                logger.info(f"Using platform override for {platform.value}")

        # Validate required variables
        required_vars = self._extract_variables(template_text)
        missing_vars = required_vars - set(variables.keys())

        if missing_vars:
            raise ValueError(
                f"Missing required variables: {', '.join(missing_vars)}"
            )

        # Render using Jinja2
        try:
            jinja_template = self.jinja_env.from_string(template_text)
            rendered = jinja_template.render(**variables)
            return rendered
        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {e}")
            raise

    def _extract_variables(self, template_text: str) -> set:
        """
        Extract variable names from template.

        Args:
            template_text: Template string

        Returns:
            Set of variable names
        """
        # Match {{variable}} syntax
        pattern = r'\{\{\s*(\w+)\s*\}\}'
        matches = re.findall(pattern, template_text)
        return set(matches)

    def validate_template(self, template_text: str) -> Dict[str, Any]:
        """
        Validate template syntax and extract metadata.

        Args:
            template_text: Template string

        Returns:
            Dict with validation results and metadata
        """
        result = {
            "valid": True,
            "errors": [],
            "variables": [],
            "character_count": len(template_text)
        }

        # Check syntax
        try:
            self.jinja_env.from_string(template_text)
        except TemplateSyntaxError as e:
            result["valid"] = False
            result["errors"].append(f"Syntax error: {str(e)}")

        # Extract variables
        try:
            variables = self._extract_variables(template_text)
            result["variables"] = list(variables)
        except Exception as e:
            result["errors"].append(f"Variable extraction error: {str(e)}")

        return result

    def create_variants(
        self,
        template: ContentTemplate,
        variable_sets: list[Dict[str, Any]],
        platform: Optional[PlatformType] = None
    ) -> list[str]:
        """
        Create multiple content variants from a single template.

        Args:
            template: ContentTemplate object
            variable_sets: List of variable dictionaries
            platform: Optional platform for rendering

        Returns:
            List of rendered content strings
        """
        variants = []

        for variable_set in variable_sets:
            try:
                rendered = self.render_template(template, variable_set, platform)
                variants.append(rendered)
            except Exception as e:
                logger.error(f"Failed to render variant: {e}")
                variants.append("")

        return variants

    def preview_template(
        self,
        template_text: str,
        sample_variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preview template with sample data.

        Args:
            template_text: Template string
            sample_variables: Sample variable values

        Returns:
            Dict with preview and metadata
        """
        result = {
            "preview": "",
            "valid": True,
            "errors": [],
            "variables_used": []
        }

        # Validate
        validation = self.validate_template(template_text)
        result["valid"] = validation["valid"]
        result["errors"] = validation["errors"]

        if not result["valid"]:
            return result

        # Render preview
        try:
            jinja_template = self.jinja_env.from_string(template_text)
            result["preview"] = jinja_template.render(**sample_variables)

            # Track which variables were actually used
            variables_in_template = self._extract_variables(template_text)
            result["variables_used"] = list(variables_in_template)

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Rendering error: {str(e)}")

        return result


# Global instance
template_engine = TemplateEngine()
