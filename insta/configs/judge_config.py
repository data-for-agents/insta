from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class JudgeConfig:

    judge_prompt: str = "verbose"

    tokenizer: str = "Qwen/Qwen2.5-72B-Instruct"

    client_type: str = None
    client_kwargs: Dict = None
    generation_kwargs: Dict = None

    last_actions: int = 5
    last_obs: int = 5
    max_obs_tokens: int = 2048

    catch_errors: bool = True
    max_errors: int = 5
    log_errors: bool = True


@dataclass
class BrowserJudgment:

    success: float = None
    efficiency: float = None
    self_correction: float = None

    response: str = None
    matched_response: str = None


VALUE_KEYS = [
    "success",
    "efficiency",
    "self_correction"
]


DEFAULT_JUDGE_PROMPT = "verbose"


DEFAULT_TOKENIZER = "Qwen/Qwen2.5-72B-Instruct"


DEFAULT_CLIENT_TYPE = "openai"


DEFAULT_CLIENT_KWARGS = {
    "api_key": "token-abc123",
    "base_url": "http://localhost:8000/v1",
}


DEFAULT_GENERATION_KWARGS = {
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "max_tokens": 2048,
    "top_p": 1.0,
    "temperature": 0.5
}


DEFAULT_LAST_ACTIONS = 5
DEFAULT_LAST_OBS = 5
DEFAULT_MAX_OBS_TOKENS = 2048


DEFAULT_CATCH_ERRORS = True
DEFAULT_MAX_ERRORS = 5
DEFAULT_LOG_ERRORS = False


DEFAULT_JUDGE_CONFIG = JudgeConfig(
    judge_prompt = DEFAULT_JUDGE_PROMPT,
    tokenizer = DEFAULT_TOKENIZER,
    client_type = DEFAULT_CLIENT_TYPE,
    client_kwargs = DEFAULT_CLIENT_KWARGS,
    generation_kwargs = DEFAULT_GENERATION_KWARGS,
    last_actions = DEFAULT_LAST_ACTIONS,
    last_obs = DEFAULT_LAST_OBS,
    max_obs_tokens = DEFAULT_MAX_OBS_TOKENS,
    catch_errors = DEFAULT_CATCH_ERRORS,
    max_errors = DEFAULT_MAX_ERRORS,
    log_errors = DEFAULT_LOG_ERRORS,
)


def get_judge_config(
    **judge_kwargs
) -> JudgeConfig:
    
    default_judge_kwargs = asdict(DEFAULT_JUDGE_CONFIG)
    default_judge_kwargs.update(judge_kwargs)
    
    return JudgeConfig(
        **default_judge_kwargs
    )
