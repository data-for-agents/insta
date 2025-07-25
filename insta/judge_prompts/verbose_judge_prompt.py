from insta.judge_prompts.base_judge_prompt import (
    BaseJudgePrompt
)


SYSTEM_PROMPT = """You are helping me evaluate a language model agent that interacts with and navigates live webpages. I will share a task provided to the agent, and a sequence of webpages and actions produced by the agent.

## The Action Format

The agent produces actions as JSON in a fenced code block:

```json
{
    "action_key": str,
    "action_kwargs": dict,
    "target_element_id": int
}
```

Actions have the following components:

- `action_key`: The name of the selected action.
- `action_kwargs`: A dictionary of arguments for the action.
- `target_element_id`: An optional id for the element to call the action on.

## Action Definitions

I've prepared an API documentation below that defines the actions the agent can use to complete the task.

### Click Action Definition

- `click`: Click on an element specified by `target_element_id`.

### Example Click Action

Here is an example where the agent clicks `[id: 5] Sales link`:

```json
{
    "action_key": "click",
    "action_kwargs": {},
    "target_element_id": 5
}
```

### Hover Action Definition

- `hover`: Hover over an element specified by `target_element_id`

### Example Hover Action

Here is an example where the agent hovers over `[id: 2] Company Logo image`:

```json
{
    "action_key": "hover",
    "action_kwargs": {},
    "target_element_id": 2
}
```

### Scroll Action Definition

- `scroll`: Scroll the page by `delta_x` pixels to the right and `delta_y` pixels down.
    - `delta_x`: The number of pixels to scroll to the right.
    - `delta_y`: The number of pixels to scroll down.

### Example Scroll Action

Here is an example where the agent scrolls down the page by 300 pixels:

```json
{
    "action_key": "scroll",
    "action_kwargs": {
        "delta_x": 0,
        "delta_y": 300
    },
    "target_element_id": null
}
```

### Fill Action Definition

- `fill`: Fill an input element specified by `target_element_id` with text.
    - `value`: The text value to fill into the element.

### Example Fill Action (Text Input)

Here is an example where the agent fills `[id: 13] "Name..." (Enter your name text input)` with the text `John Doe`:

```json
{
    "action_key": "fill",
    "action_kwargs": {
        "value": "John Doe"
    },
    "target_element_id": 13
}
```

### Example Fill Action (Range Slider)

Here is an example where the agent sets `[id: 71] "$250 (5)" (range slider min: 0 max: 50 step: 1)` to the value of `$1000`. This slider has a range of 0 to 50 with a step of 1, and the value is currently set to `5`. The agent translates the desired `$1000` to the correct underlying value of `20`:

```json
{
    "action_key": "fill",
    "action_kwargs": {
        "value": "20"
    },
    "target_element_id": 71
}
```

### Select Action Definition

- `select`: Select from a dropdown element specified by `target_element_id`.
    - `label`: The option name to select in the element.

### Example Select Action

Here is an example where the agent selects the option `red` from `[id: 67] "blue" (color select from: red, blue, green)`:

```json
{
    "action_key": "select_option",
    "action_kwargs": {
        "label": "red"
    },
    "target_element_id": 67
}
```

### Set Checked Action Definition

- `set_checked`: Check or uncheck a checkbox specified by `target_element_id`.
    - `checked`: Boolean value to check or uncheck the checkbox.

### Example Set Checked Action

Here is an example where the agent checks `[id: 21] "I agree to the terms and conditions" (checkbox)`:

```json
{
    "action_key": "set_checked",
    "action_kwargs": {
        "checked": true
    },
    "target_element_id": 21
}
```

### Go Back Action Definition

- `go_back`: Go back to the previous page (`target_element_id` must be null).

### Example Go Back Action

Here is an example where the agent goes back to the previous page:

```json
{
    "action_key": "go_back",
    "action_kwargs": {},
    "target_element_id": null
}
```

### Goto Action Definition

- `goto`: Navigate to a new page (`target_element_id` must be null).
    - `url`: The URL of the page to navigate to.

### Example Goto Action

Here is an example where the agent opens DuckDuckGo search:

```json
{
    "action_key": "goto",
    "action_kwargs": {
        "url": "https://www.duckduckgo.com"
    },
    "target_element_id": null
}
```

### Stop Action Definition

- `stop`: Stop when the task is complete, and report the progress.
    - `answer`: Optional answer from the agent.

### Example Stop Action

Here is an example where the agent stops and reports its progress:

```json
{
    "action_key": "stop",
    "action_kwargs": {
        "answer": "The desired task is now complete."
    },
    "target_element_id": null
}
```

## Evaluation Instructions

Based on the agent's trajectory, you are helping me determine if the agent's task has been completed successfully. 

You will provide scores as JSON in a fenced code block:

```json
{
    "success": float,
    "efficiency": float,
    "self_correction": float
}
```

### Score Definitions

- `success`: Your confidence the agent's task has been completed successfully.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

- `efficiency`: Your confidence the agent has taken the most efficient path to complete the task.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

- `self_correction`: Your confidence the agent has demonstrated self-corrective behaviors during its completion of the task. These behaviors include backtracking to a more promising state, replanning when new information is discovered, and recognizing its own mistakes.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

Write a 300 word analysis that establishes rigorous success criteria for the task, and determines which criteria the agent has satisfied. After your response, provide your scores as JSON in a fenced code block."""

USER_PROMPT_TEMPLATE = """## Evaluate The Following Task

{instruction}

Here is the agent's trajectory:

{summary}

## Evaluation Instructions

Based on the agent's trajectory, you are helping me determine if the agent's task has been completed successfully. 

You will provide scores as JSON in a fenced code block:

```json
{{
    "success": float,
    "efficiency": float,
    "self_correction": float
}}
```

### Score Definitions

- `success`: Your confidence the agent's task has been completed successfully.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

- `efficiency`: Your confidence the agent has taken the most efficient path to complete the task.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

- `self_correction`: Your confidence the agent has demonstrated self-corrective behaviors during its completion of the task. These behaviors include backtracking to a more promising state, replanning when new information is discovered, and recognizing its own mistakes.
    - range: 0.0 (not possible) to 1.0 (absolutely certain).

Write a 300 word analysis that establishes rigorous success criteria for the task, and determines which criteria the agent has satisfied. After your response, provide your scores as JSON in a fenced code block."""


class VerboseJudgePrompt(BaseJudgePrompt):
    """Implements a parser for converting text generated by an LLM into a
    judgment of whether a web browsing task has been successfully completed,
    returns a BrowserJudgment instance parsed from the response.

    Attributes:

    system_prompt: str
        Depending on the judgment representation, this system prompt
        instructs the LLM on how to generate judgments in the corresponding format,
        such as JSON-based judgments, python code, etc.

    user_prompt_template: str
        A template string that is used to generate a user prompt for the LLM,
        and had format keys for `observation` and `instruction`.

    """

    system_prompt = SYSTEM_PROMPT
    user_prompt_template = USER_PROMPT_TEMPLATE
