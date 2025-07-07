# from fasthtml.common import (
#     FastHTML,
#     H2,
#     H4,
#     A,
#     Span,
#     P,
#     Ul,
#     Input,
#     Form,
#     Video,
#     Div,
#     Li,
#     Script,
#     Html,
#     Head,
#     Meta,
#     Body,
#     Title,
#     serve,
# )
from monsterui.all import (
    Button,
)


def BackButton(url: str = "/"):
    return (
        Button(
            "← Go Back",
            hx_get=url,
            hx_push_url="true",
            hx_target="body",
        ),
    )
