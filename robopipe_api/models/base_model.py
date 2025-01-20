from pydantic import BaseModel as PydanticBaseModel

from typing import Any


class BaseModel(PydanticBaseModel):
    class Config:
        @staticmethod
        def json_schema_extra(schema: dict[str, Any]) -> None:
            for prop in schema.get("properties", {}).values():
                description_parts = []

                if "minimum" in prop and "maximum" in prop:
                    description_parts.append(
                        f"between {prop['minimum']} and {prop['maximum']}"
                    )
                elif "minimum" in prop:
                    description_parts.append(f"greater or equal to {prop['minimum']}")
                elif "maximum" in prop:
                    description_parts.append(f"less or equal to {prop['maximum']}")

                if description_parts:
                    original_description = prop.get("description", "")

                    if original_description:
                        if not original_description.endswith("."):
                            original_description += "."

                        original_description += " "

                    prop["description"] = (
                        original_description
                        + "Value must be "
                        + " and ".join(description_parts)
                    )
