# NOTE: default rounding (inherited from decimal.Decimal is ROUND_HALF_EVEN)
from decimal import Decimal

from dinero import Dinero
from dinero.currencies import USD
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class UsDollars(Dinero):
    def __init__(self, amount: int | float | str | Decimal):
        super().__init__(amount, currency=USD)

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return self.format(symbol=True, currency=True)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source, handler: GetCoreSchemaHandler):
        def validate(v):
            if isinstance(v, cls):
                return v
            if isinstance(v, Dinero):
                return cls(v.amount)  # adjust if needed
            return cls(v)

        return core_schema.no_info_after_validator_function(
            function=validate,
            schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(cls),
                    core_schema.is_instance_schema(Dinero),
                    core_schema.int_schema(),
                    core_schema.float_schema(),
                    core_schema.str_schema(),
                    core_schema.decimal_schema(),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: str(v), when_used="json"
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        schema.update({"type": "string", "title": "US Dollars", "example": "19.99"})
        return schema
