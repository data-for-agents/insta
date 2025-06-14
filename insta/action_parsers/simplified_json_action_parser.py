from insta.action_parsers.json_action_parser import (
    JsonActionParser
)


SYSTEM_PROMPT = """You are an agent that interacts with and navigates live webpages. Our goal is to complete an internet-based task by operating a virtual web browser."""


USER_PROMPT_TEMPLATE = """## Complete The Following Task

{instruction}

You are at {current_url} observing the viewport:

{observation}"""


class SimplifiedJsonActionParser(JsonActionParser):
    """Implements a parser for converting text generated by an LLM into a
    sequence of function calls to the Playwright API, represented as a
    BrowserAction that contains FunctionCall objects.

    Attributes:

    system_prompt: str
        Depending on the kind of action representation, this system prompt
        instructs the LLM on how to generate actions in the corresponding format,
        such as JSON-based actions, JavaScript code, etc.

    user_prompt_template: str
        A template string that is used to generate a user prompt for the LLM,
        and had format keys for `observation` and `instruction`.

    """

    system_prompt = SYSTEM_PROMPT
    user_prompt_template = USER_PROMPT_TEMPLATE
