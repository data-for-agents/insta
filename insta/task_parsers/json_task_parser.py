from insta.utils import (
    BrowserStatus
)

from insta.configs.task_proposer_config import (
    BrowserTaskProposal
)

from insta.task_parsers.task_parser import (
    BaseTaskParser
)

import re
import json


TASK_PATTERN = re.compile(
    r"```json\n(?P<json>.*)\n```",
    re.DOTALL
)


SYSTEM_PROMPT = """You are a helpful assistant designing tasks for a web automation script. I will show you previous runs of the script, including previous tasks, webpages, actions, and performance reviews, formatted in markdown. Help me design *challenging* new tasks.

## Formatting The Proposed Task

Format your task in the following JSON schema:

```json
{
    "proposed_task": str,
    "steps": List[str],
    "criteria": str
}
```

Here is what each key means:

- `proposed_task`: A specific, challenging task that an expert user might leverage this website to complete.
    - Must not require making an account, logging in, submitting personal information, making a purchase, or placing an order.

- `steps`: Steps an expert user would follow to complete the proposed task.
- `criteria`: The required answer, and criteria to determine if the task was completed.

## Example Tasks For Inspiration

Suppose you want to design a task around the 'C-to-C Hose-Shut-Off Valve' on 'awg-fittings.com':

```json
{
    "proposed_task": "What is the C-to-C Hose-Shut-Off Valve length in mm?",
    "steps": [
        "Navigate to 'awg-fittings.com'",
        "Open the product catelog for fittings",
        "Locate the product listing for the C-to-C Hose-Shut-Off Valve",
        "Find the product length in mm, and respond with that length in the answer"
    ],
    "criteria": "The answer should include the specific length of '237 mm' for this product"
}
```

Suppose you want to design a task around the document 'The Angora cat; how to breed train and keep it' on 'biodiversitylibrary.org':

```json
{
    "proposed_task": "Open a scanned copy of 'The Angora cat; how to breed train and keep it'.",
    "steps": [
        "Navigate to 'biodiversitylibrary.org'",
        "Search for 'The Angora cat; how to breed train and keep it' in the search bar",
        "Click on the title of the document in the search results",
        "Confirm the correct document is displayed in an embedded PDF reader"
    ],
    "criteria": "The final webpage should display the correct document in an embedded PDF reader"
}
```

Suppose you want to design a task around the 'Generative Adversarial Networks' paper on 'scholar.google.com':

```json
{
    "proposed_task": "How many citations does the paper 'Generative Adversarial Networks' have?",
    "steps": [
        "Navigate to 'scholar.google.com'",
        "Search for 'Generative Adversarial Networks' in the search bar",
        "Locate the correct paper in the search results",
        "Find an up-to-date citation count, and respond with that count in the answer"
    ],
    "criteria": "The answer should include an up-to-date citation count, which is '80613' as of April 2025"
}
```

Suppose you want to design a task around the word 'serendipity' on 'wiktionary.org':

```json
{
    "proposed_task": "What is the definition and etymology of the word 'serendipity'?",
    "steps": [
        "Navigate to 'wiktionary.org'",
        "Search for 'serendipity' in the search bar",
        "Find the definition and etymology sections of the 'serendipity' page",
        "Summarize the contents of these sections in the answer"
    ],
    "criteria": "The answer should mention Serendip (or Serendib), coined by English writer and politician Horace Walpole in 1754"
}
```

Thanks for helping me design challenging new tasks, please follow the instructions carefully. Start your response with an analysis for how an expert user would leverage this website, followed by a step-by-step breakdown of your proposed task, and finally, enter your task in the JSON format. Respond in 500 words."""


USER_PROMPT_TEMPLATE = """## Summary Of Previous Runs 

Here are previous runs of the script, including tasks, webpages, actions, and performance reviews, formatted in markdown:

{annotations}

## Formatting The Proposed Task

Enter a task in the following JSON schema:

```json
{{
    "proposed_task": str,
    "steps": List[str],
    "criteria": str
}}
```

Here is what each key means:

- `proposed_task`: A specific, challenging task that an expert user might leverage {target_url} to complete.
    - Must not require making an account, logging in, submitting personal information, making a purchase, or placing an order.

- `steps`: Steps an expert user would follow to complete the proposed task.
- `criteria`: The required answer, and criteria to determine if the task was completed.

Start your response with an analysis for how an expert user would leverage {target_url}, followed by a step-by-step breakdown of your proposed task, and finally, enter your task in the JSON format. Respond in 500 words."""


class JsonTaskParser(BaseTaskParser):
    """Implements a parser for converting text generated by an LLM into a
    task for an LLM agent to attempt to complete using a web browser,
    returns a BrowserJudgment instance parsed from the response.

    Attributes:

    system_prompt: str
        Depending on the task representation, this system prompt
        instructs the LLM on how to generate tasks in the corresponding format,
        such as JSON-based tasks, YAML format, etc.

    user_prompt_template: str
        A template string that is used to generate a user prompt for the LLM,
        and has format keys for `annotations` which represents
        previous task runs and judgments produced by the LLM judge.

    """

    system_prompt = SYSTEM_PROMPT
    user_prompt_template = USER_PROMPT_TEMPLATE

    def parse_task(self, response: str) -> BrowserTaskProposal | BrowserStatus:
        """Parse a task proposal string produced by an LLM, and return a
        BrowserTaskProposal object that contains the proposed task,
        and additional metadata about the task feasibility, and difficulty.

        Arguments:

        response: str
            The response from an LLM that contains a task proposal in a code block,
            which will be parsed into a BrowserTaskProposal object.
        
        Returns:

        BrowserTaskProposal | PlaywrightStatus
            The parsed task proposal, or a BrowserStatus object that
            represents a failed parsing attempt.
        
        """
        
        match = TASK_PATTERN.search(response)

        has_required_field = (
            match is not None and 
            "json" in match.groupdict()
        )

        if not has_required_field:
    
            return BrowserStatus.ERROR

        matched_response = match.group("json")
        
        try: response_dict = json.loads(matched_response)
        except json.JSONDecodeError:
            return BrowserStatus.ERROR
        
        has_required_keys = (
            "proposed_task" in response_dict and
            "steps" in response_dict and
            "criteria" in response_dict
        )

        if not has_required_keys:

            return BrowserStatus.ERROR
        
        proposed_task = response_dict["proposed_task"]
        steps = response_dict["steps"]
        criteria = response_dict["criteria"]
        
        keys_right_type = (
            (isinstance(proposed_task, str) and (len(proposed_task) > 0)) and
            (isinstance(steps, list) and (len(steps) > 0) and all([
                isinstance(x, str) for x in steps])) and
            (isinstance(criteria, str) and (len(criteria) > 0))
        )

        if not keys_right_type:

            return BrowserStatus.ERROR
        
        task_dict = {
            "proposed_task": str(proposed_task),
            "steps": list(steps),
            "criteria": str(criteria),
        }
        
        browser_task = BrowserTaskProposal(
            **task_dict,
            response = response,
            matched_response = matched_response
        )

        return browser_task
