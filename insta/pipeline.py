from typing import Callable, Tuple, List, Dict, Generator
from collections import namedtuple

from dataclasses import asdict
from functools import partial
from multiprocessing import Pool

from insta.configs import (
    DEFAULT_AGENT_CONFIG,
    DEFAULT_JUDGE_CONFIG,
    DEFAULT_BROWSER_CONFIG,
    AgentConfig,
    JudgeConfig,
    BrowserConfig,
    get_browser_config,
)

from insta.gym_env import (
    InstaEnv,
    InstaEnvStepOutput
)

from insta.agent import (
    BrowserAgent,
    NULL_ACTION
)

from insta.judge import (
    BrowserJudge
)

from insta.utils import (
    prune_observation,
    METADATA_KEYS,
    VALUE_KEYS
)

import random
import tqdm
import json
import os


DEFAULT_OBSERVATIONS_DIR = "data/observations"
DEFAULT_SCREENSHOT_DIR = "data/screenshots"
DEFAULT_ACTIONS_DIR = "data/actions"
DEFAULT_JUDGMENTS_DIR = "data/judgments"


DEFAULT_AGENT_RESPONSE_KEY = "matched_response"


DEFAULT_MAX_ACTIONS = 30
DEFAULT_SKIP_FINISHED = False
DEFAULT_PRUNE_OBSERVATIONS = False


DEFAULT_SEED = 123
DEFAULT_RANK = 0
DEFAULT_WORLD_SIZE = 1


DEFAULT_NUM_AGENTS = 32
DEFAULT_PLAYWRIGHT_WORKERS = 8
DEFAULT_RETURN_TRAJECTORIES = False


InstaPipelineOutput = namedtuple(
    "InstaPipelineOutput",
    ["observations", "actions", "judgment"]
)


def generate_trajectory(
    agent: BrowserAgent | AgentConfig,
    judge: BrowserJudge | JudgeConfig,
    env: InstaEnv | BrowserConfig,
    url: str, instruction: str,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
) -> Tuple[List[Dict], List[Dict], Dict]:
    """Attempt a web navigation task using the LLM agent, and return the
    observations and actions along the trajectory for later processing.

    Arguments:

    agent: BrowserAgent | AgentConfig
        The LLM agent to use for the task.

    judge: BrowserJudge | JudgeConfig
        The LLM judge to evaluate the trajectory.

    env: InstaEnv | BrowserConfig
        The web navigation environment running Playwright.

    url: str
        Starting URL for the agent.

    instruction: str
        Specific instruction for the agent.

    max_actions: int
        Maximum number of actions per task.

    Returns:

    Tuple[List[Dict], List[Dict], Dict]
        Tuple containing observations, actions, and judgment for the trajectory
        generated by running the agent with an instruction.
    
    """

    if isinstance(agent, AgentConfig):

        agent = BrowserAgent(
            config = agent
        )

    if isinstance(judge, JudgeConfig):

        judge = BrowserJudge(
            config = judge
        )

    if isinstance(env, BrowserConfig):

        env = InstaEnv(
            config = env
        )

    observations = []
    actions = []

    action = NULL_ACTION

    for t in range(max_actions):

        outputs = None

        if action is not NULL_ACTION:

            agent.push_action(
                response = action.response
            )

            outputs = env.step(
                action = action
            )

        elif t == 0:

            agent.reset()

            outputs = env.reset(
                url = url
            )

        is_finished = outputs is None or (
            isinstance(outputs, InstaEnvStepOutput)
            and outputs.done
        )

        if is_finished:
            
            break

        obs = outputs.observation

        for key, value in (obs.metadata or {}).items():

            obs.metadata[key] = {
                key: value.get(key)
                for key in METADATA_KEYS
            } 

        observations.append({
            "current_url": obs.current_url,
            "processed_text": obs.processed_text,
            "raw_html": obs.raw_html,
            "screenshot": obs.screenshot,
            "metadata": obs.metadata
        })

        agent.pop_observation()
        
        action = agent(
            observation = obs.processed_text,
            instruction = instruction,
            current_url = obs.current_url
        )

        function_calls = [
            {"dotpath": x.dotpath, "args": x.args}
            for x in action.function_calls
        ]

        actions.append({
            "function_calls": function_calls,
            "response": action.response,
            "matched_response": action.matched_response
        })

    judgment = judge(
        observations = [
            x["processed_text"]
            for x in observations
        ],
        actions = [
            x[agent_response_key]
            for x in actions
        ],
        instruction = instruction
    )

    judgment_values = {
        key: judgment.values.get(key)
        for key in VALUE_KEYS
    }

    judgment = {
        **judgment_values,
        "response": judgment.response,
        "matched_response": judgment.matched_response,
    }

    return observations, actions, judgment


def iter_trajectories(
    dataset: List[Dict[str, str]],
    agent: BrowserAgent | AgentConfig,
    judge: BrowserJudge | JudgeConfig,
    env: InstaEnv | BrowserConfig,
    observations_dir: str = DEFAULT_OBSERVATIONS_DIR,
    screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
    actions_dir: str = DEFAULT_ACTIONS_DIR,
    judgments_dir: str = DEFAULT_JUDGMENTS_DIR,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
    skip_finished: bool = DEFAULT_SKIP_FINISHED,
    prune_observations: bool = DEFAULT_PRUNE_OBSERVATIONS,
    seed: int = DEFAULT_SEED,
    rank: int = DEFAULT_RANK,
    world_size: int = DEFAULT_WORLD_SIZE
) -> Generator[InstaPipelineOutput, None, None]:
    """Run the InSTA pipeline for internet-scale data collection, and yield
    the observations, actions, and judgments for each task.

    Arguments:

    dataset: List[Dict[str, str]]
        Override the default dataset, and run the pipeline on custom tasks,
        each entry must be a dictionary with keys "domain" and "task".

    agent: BrowserAgent | AgentConfig
        The LLM agent to use for the task.

    judge: BrowserJudge | JudgeConfig
        The LLM judge to evaluate the trajectory.

    env: InstaEnv | BrowserConfig
        The web navigation environment running Playwright.

    observations_dir: str
        Directory to save observations.

    screenshot_dir: str
        Directory to save screenshots.

    actions_dir: str
        Directory to save actions.

    judgments_dir: str
        Directory to save judgments.

    max_actions: int
        Maximum number of actions per task.

    skip_finished: bool
        Whether to skip tasks that are already attempted.

    prune_observations: bool
        Whether to prune observations before saving.

    seed: int
        Seed for the dataset.

    rank: int
        Rank of the process.

    world_size: int
        Number of data collection processes.

    Returns:

    Generator[InstaPipelineOutput, None, None]
        Generator for the observations, actions, and judgments for each task, 
        which are saved to disk for later processing.
    
    """

    if isinstance(agent, AgentConfig):

        agent = BrowserAgent(
            config = agent
        )

    if isinstance(judge, JudgeConfig):

        judge = BrowserJudge(
            config = judge
        )

    if isinstance(env, BrowserConfig):

        env = InstaEnv(
            config = env
        )

    if observations_dir is not None:

        os.makedirs(
            observations_dir, 
            exist_ok = True
        )

    if screenshot_dir is not None:

        os.makedirs(
            screenshot_dir, 
            exist_ok = True
        )

    if actions_dir is not None:

        os.makedirs(
            actions_dir, 
            exist_ok = True
        )

    if judgments_dir is not None:

        os.makedirs(
            judgments_dir, 
            exist_ok = True
        )

    dataset_ids = list(range(len(dataset)))

    random.seed(seed)
    random.shuffle(dataset_ids)

    dataset_ids = dataset_ids[
        rank::world_size
    ]

    progress_bar = tqdm.tqdm(
        dataset_ids, desc = "Processing",
        dynamic_ncols = True
    )

    for example_id in progress_bar:

        example_dict = dataset[example_id]

        domain = example_dict["domain"]
        instruction = example_dict["task"]

        progress_bar.set_description(
            "Processing: {}".format(
                domain
            )
        )

        if observations_dir is not None:

            observations_path = os.path.join(
                observations_dir,
                "{}.json".format(domain)
            )

        if actions_dir is not None:

            actions_path = os.path.join(
                actions_dir,
                "{}.json".format(domain)
            )

        if judgments_dir is not None:

            judgments_path = os.path.join(
                judgments_dir,
                "{}.json".format(domain)
            )

        if screenshot_dir is not None:

            screenshot_domain_dir = os.path.join(
                screenshot_dir,
                "{}".format(domain)
            )

            os.makedirs(
                screenshot_domain_dir,
                exist_ok = True
            )

        skip_this_task = (
            judgments_dir is not None and
            skip_finished and
            os.path.exists(judgments_path)
        )

        if skip_this_task:

            continue

        url = "http://{domain}".format(
            domain = domain
        )
        
        observations, actions, judgment = generate_trajectory(
            env = env, agent = agent, judge = judge,
            url = url, instruction = instruction,
            max_actions = max_actions,
            agent_response_key = agent_response_key
        )

        for step_idx, observation in enumerate(observations):

            if screenshot_dir is not None and \
                    observation.get("screenshot") is not None:

                screenshot_path = os.path.join(
                    screenshot_domain_dir,
                    "screenshot_{:02d}.jpg"
                    .format(step_idx)
                )

                screenshot = observation.pop(
                    "screenshot"
                )

                screenshot.convert("RGB").save(
                    screenshot_path
                )

                observation["screenshot_path"] = (
                    screenshot_path
                )

            if prune_observations:
                
                observations[step_idx] = (
                    prune_observation(
                        observation
                    )
                )

        if observations_dir is not None:
                
            with open(observations_path, "w") as file:
                
                json.dump(
                    observations, 
                    file,
                    indent = 4
                )

        if actions_dir is not None:

            with open(actions_path, "w") as file:
                
                json.dump(
                    actions, 
                    file,
                    indent = 4
                )

        if judgments_dir is not None:

            with open(judgments_path, "w") as file:
                
                json.dump(
                    judgment, 
                    file,
                    indent = 4
                )

        yield InstaPipelineOutput(
            observations = observations,
            actions = actions,
            judgment = judgment
        )


def list_trajectories(
    dataset: List[Dict[str, str]],
    agent: BrowserAgent | AgentConfig, 
    judge: BrowserJudge | JudgeConfig,
    env: InstaEnv | BrowserConfig,
    observations_dir: str = DEFAULT_OBSERVATIONS_DIR,
    screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
    actions_dir: str = DEFAULT_ACTIONS_DIR,
    judgments_dir: str = DEFAULT_JUDGMENTS_DIR,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
    skip_finished: bool = DEFAULT_SKIP_FINISHED,
    prune_observations: bool = DEFAULT_PRUNE_OBSERVATIONS,
    seed: int = DEFAULT_SEED,
    rank: int = DEFAULT_RANK,
    world_size: int = DEFAULT_WORLD_SIZE
) -> List[InstaPipelineOutput]:
    """Run the InSTA pipeline for internet-scale data collection, and list
    the observations, actions, and judgments for each task.

    Arguments:

    dataset: List[Dict[str, str]]
        Override the default dataset, and run the pipeline on custom tasks,
        each entry must be a dictionary with keys "domain" and "task".

    agent: BrowserAgent | AgentConfig
        The LLM agent to use for the task.

    judge: BrowserJudge | JudgeConfig
        The LLM judge to evaluate the trajectory.

    env: InstaEnv | BrowserConfig
        The web navigation environment running Playwright.

    observations_dir: str
        Directory to save observations.

    screenshot_dir: str
        Directory to save screenshots.

    actions_dir: str
        Directory to save actions.

    judgments_dir: str
        Directory to save judgments.

    max_actions: int
        Maximum number of actions per task.

    skip_finished: bool
        Whether to skip tasks that are already attempted.

    prune_observations: bool
        Whether to prune observations before saving.

    seed: int
        Seed for the dataset.

    rank: int
        Rank of the process.

    world_size: int
        Number of data collection processes.

    Returns:

    List[InstaPipelineOutput]
        List with observations, actions, and judgments for each task, 
        which are saved to disk for later processing.
    
    """

    return list(iter_trajectories(
        dataset = dataset, env = env,
        agent = agent, judge = judge,
        observations_dir = observations_dir,
        screenshot_dir = screenshot_dir,
        actions_dir = actions_dir,
        judgments_dir = judgments_dir,
        max_actions = max_actions,
        agent_response_key = agent_response_key,
        skip_finished = skip_finished,
        prune_observations = prune_observations,
        seed = seed,
        rank = rank,
        world_size = world_size
    ))


def save_trajectories(
    dataset: List[Dict[str, str]],
    agent: BrowserAgent | AgentConfig,
    judge: BrowserJudge | JudgeConfig,
    env: InstaEnv | BrowserConfig,
    observations_dir: str = DEFAULT_OBSERVATIONS_DIR,
    screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
    actions_dir: str = DEFAULT_ACTIONS_DIR,
    judgments_dir: str = DEFAULT_JUDGMENTS_DIR,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
    skip_finished: bool = DEFAULT_SKIP_FINISHED,
    prune_observations: bool = DEFAULT_PRUNE_OBSERVATIONS,
    seed: int = DEFAULT_SEED,
    rank: int = DEFAULT_RANK,
    world_size: int = DEFAULT_WORLD_SIZE
) -> None:
    """Run the InSTA pipeline for internet-scale data collection, and save
    the observations, actions, and judgments for each task.

    Arguments:

    dataset: List[Dict[str, str]]
        Override the default dataset, and run the pipeline on custom tasks,
        each entry must be a dictionary with keys "domain" and "task".

    agent: BrowserAgent | AgentConfig
        The LLM agent to use for the task.

    judge: BrowserJudge | JudgeConfig
        The LLM judge to evaluate the trajectory.

    env: InstaEnv | BrowserConfig
        The web navigation environment running Playwright.

    observations_dir: str
        Directory to save observations.

    screenshot_dir: str
        Directory to save screenshots.

    actions_dir: str
        Directory to save actions.

    judgments_dir: str
        Directory to save judgments.

    max_actions: int
        Maximum number of actions per task.

    skip_finished: bool
        Whether to skip tasks that are already attempted.

    prune_observations: bool
        Whether to prune observations before saving.

    seed: int
        Seed for the dataset.

    rank: int
        Rank of the process.

    world_size: int
        Number of data collection processes.
    
    """

    for x in iter_trajectories(
        dataset = dataset, env = env,
        agent = agent, judge = judge,
        observations_dir = observations_dir,
        screenshot_dir = screenshot_dir,
        actions_dir = actions_dir,
        judgments_dir = judgments_dir,
        max_actions = max_actions,
        agent_response_key = agent_response_key,
        skip_finished = skip_finished,
        prune_observations = prune_observations,
        seed = seed,
        rank = rank,
        world_size = world_size
    ):
        
        pass


def launch_data_collection(
    dataset: List[Dict[str, str]],
    agent_config: AgentConfig = DEFAULT_AGENT_CONFIG,
    judge_config: JudgeConfig = DEFAULT_JUDGE_CONFIG,
    browser_config: BrowserConfig = DEFAULT_BROWSER_CONFIG,
    observations_dir: str = DEFAULT_OBSERVATIONS_DIR,
    screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
    actions_dir: str = DEFAULT_ACTIONS_DIR,
    judgments_dir: str = DEFAULT_JUDGMENTS_DIR,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
    skip_finished: bool = DEFAULT_SKIP_FINISHED,
    prune_observations: bool = DEFAULT_PRUNE_OBSERVATIONS,
    seed: int = DEFAULT_SEED,
    return_trajectories: bool = DEFAULT_RETURN_TRAJECTORIES,
    num_agents: int = DEFAULT_NUM_AGENTS,
    playwright_workers: int = DEFAULT_PLAYWRIGHT_WORKERS,
    rank: int = DEFAULT_RANK,
    world_size: int = DEFAULT_WORLD_SIZE,
) -> List[InstaPipelineOutput] | None:
    """Run parallel agents to complete web navigation tasks,
    such as for performing Deep Research across the whole internet.

    Arguments:

    dataset: List[Dict[str, str]]
        Override the default dataset, and run the pipeline on custom tasks,
        each entry must be a dictionary with keys "domain" and "task".

    env: InstaEnv
        The web navigation environment running Playwright.

    agent: BrowserAgent
        The LLM agent to use for the task.

    judge: BrowserJudge
        The LLM judge to evaluate the trajectory.

    observations_dir: str
        Directory to save observations.

    screenshot_dir: str
        Directory to save screenshots.

    actions_dir: str
        Directory to save actions.

    judgments_dir: str
        Directory to save judgments.

    max_actions: int
        Maximum number of actions per task.

    skip_finished: bool
        Whether to skip tasks that are already attempted.

    prune_observations: bool
        Whether to prune observations before saving.

    seed: int
        Seed for the dataset.

    return_trajectories: bool
        Whether to return trajectories or just save them.
        
    num_agents: int
        Number of parallel agents to run.

    playwright_workers: int
        Number of Playwright workers running.

    rank: int
        Rank of the machine.

    world_size: int
        Number of data collection machines.

    Returns:

    List[InstaPipelineOutput] | None
        List with observations, actions, and judgments for each task, 
        which are saved to disk for later processing.
    
    """

    worker_fn = partial(
        list_trajectories
        if return_trajectories else
        save_trajectories,
        observations_dir = observations_dir,
        screenshot_dir = screenshot_dir,
        actions_dir = actions_dir,
        judgments_dir = judgments_dir,
        max_actions = max_actions,
        agent_response_key = agent_response_key,
        skip_finished = skip_finished,
        prune_observations = prune_observations
    )

    worker_args = []

    dataset_ids = list(range(len(dataset)))

    random.seed(seed)
    random.shuffle(dataset_ids)

    browser_config_dict = asdict(browser_config)

    for agent_rank in range(
            rank * num_agents,
            (rank + 1) * num_agents):

        browser_config = get_browser_config(
            playwright_url = browser_config_dict["playwright_url"],
            playwright_port = (
                browser_config_dict["playwright_port"] +
                agent_rank % playwright_workers
            )
        )

        rank_dataset_ids = dataset_ids[
            agent_rank::world_size * num_agents
        ]

        rank_dataset = [
            dataset[example_id]
            for example_id in rank_dataset_ids
        ]

        worker_args.append((
            rank_dataset,
            agent_config,
            judge_config,
            browser_config
        ))
        
    with Pool(processes = num_agents) as pool:

        results = pool.starmap(
            worker_fn, worker_args
        )
        
    if return_trajectories:
        
        return [
            x for result in results
            for x in result
        ]


class InstaPipeline(Callable):
    """Initialize the InSTA pipeline for internet-scale data collection,
    creates a browser, LLM agent, and LLM judge, then runs the agent
    to attempt web navigation tasks from the InSTA-150k dataset.

    Attributes:

    agent: BrowserAgent
        The LLM agent to use for the task.

    judge: BrowserJudge
        The LLM judge to evaluate the trajectory.

    env: InstaEnv
        The web navigation environment running Playwright.

    """

    agent: BrowserAgent
    judge: BrowserJudge
    env: InstaEnv

    def __init__(self, agent_config: AgentConfig = DEFAULT_AGENT_CONFIG,
                 judge_config: JudgeConfig = DEFAULT_JUDGE_CONFIG,
                 browser_config: BrowserConfig = DEFAULT_BROWSER_CONFIG,
                 observations_dir: str = DEFAULT_OBSERVATIONS_DIR,
                 screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
                 actions_dir: str = DEFAULT_ACTIONS_DIR,
                 judgments_dir: str = DEFAULT_JUDGMENTS_DIR,
                 max_actions: int = DEFAULT_MAX_ACTIONS,
                 agent_response_key: str = DEFAULT_AGENT_RESPONSE_KEY,
                 skip_finished: bool = DEFAULT_SKIP_FINISHED,
                 prune_observations: bool = DEFAULT_PRUNE_OBSERVATIONS,
                 seed: int = DEFAULT_SEED,
                 rank: int = DEFAULT_RANK,
                 world_size: int = DEFAULT_WORLD_SIZE):
        """Initialize the InSTA pipeline for internet-scale data collection,
        creates a browser, LLM agent, and LLM judge, then runs the agent
        to attempt web navigation tasks from the InSTA-150k dataset.

        Arguments:

        agent_config: AgentConfig
            Configuration for the LLM agent.

        judge_config: JudgeConfig
            Configuration for the LLM judge.

        browser_config: BrowserConfig
            Configuration for the Playwright environment.

        observations_dir: str
            Directory to save observations.

        screenshot_dir: str
            Directory to save screenshots.

        actions_dir: str
            Directory to save actions.

        judgments_dir: str
            Directory to save judgments.

        max_actions: int
            Maximum number of actions per task.

        skip_finished: bool
            Whether to skip tasks that are already attempted.

        prune_observations: bool
            Whether to prune observations before saving.

        seed: int
            Seed for the dataset.

        rank: int
            Rank of the process.

        world_size: int
            Number of data collection processes.
        
        """

        self.agent_config = agent_config
        self.judge_config = judge_config
        self.browser_config = browser_config

        self.observations_dir = observations_dir
        self.screenshot_dir = screenshot_dir
        self.actions_dir = actions_dir
        self.judgments_dir = judgments_dir

        self.max_actions = max_actions
        self.agent_response_key = agent_response_key
        self.skip_finished = skip_finished
        self.prune_observations = prune_observations

        self.seed = seed
        self.rank = rank
        self.world_size = world_size

        self.agent = BrowserAgent(
            config = self.agent_config
        )

        self.judge = BrowserJudge(
            config = self.judge_config
        )

        self.env = InstaEnv(
            config = self.browser_config
        )

    def generate_trajectory(
        self, url: str, instruction: str
    ) -> Tuple[List[Dict], List[Dict], Dict]:
        """Attempt a web navigation task using the LLM agent, and return the
        observations and actions along the trajectory for later processing.

        Arguments:

        url: str
            Starting URL for the agent.

        instruction: str
            Specific instruction for the agent.

        Returns:

        Tuple[List[Dict], List[Dict], Dict]
            Tuple containing observations, actions, and judgment for the trajectory
            generated by running the agent with an instruction.
        
        """
    
        observations, actions, judgment = generate_trajectory(
            env = self.env, agent = self.agent, judge = self.judge,
            url = url, instruction = instruction,
            max_actions = self.max_actions,
            agent_response_key = self.agent_response_key
        )

        return observations, actions, judgment
    
    def __call__(self, url: str, instruction: str) -> Tuple[List[Dict], List[Dict]]:
        """Attempt a web navigation task using the LLM agent, and return the
        observations and actions along the trajectory for later processing.

        Arguments:

        url: str
            Starting URL for the agent.

        instruction: str
            Specific instruction for the agent.

        Returns:

        Tuple[List[Dict], List[Dict], Dict]
            Tuple containing observations, actions, and judgment for the trajectory
            generated by running the agent with an instruction.
        
        """
        
        return self.generate_trajectory(
            url = url, instruction = instruction
        )

    def iter_trajectories(
        self, dataset: List[Dict[str, str]]
    ) -> Generator[InstaPipelineOutput, None, None]:
        """Run the InSTA pipeline for internet-scale data collection, and yield
        the observations, actions, and judgments for each task.

        Arguments:

        dataset: List[Dict[str, str]]
            Override the default dataset, and run the pipeline on custom tasks,
            each entry must be a dictionary with keys "domain" and "task".

        Returns:

        Generator[InstaPipelineOutput, None, None]
            Generator for the observations, actions, and judgments for each task, 
            which are saved to disk for later processing.
        
        """

        yield from iter_trajectories(
            dataset = dataset, env = self.env,
            agent = self.agent, judge = self.judge, 
            observations_dir = self.observations_dir,
            screenshot_dir = self.screenshot_dir,
            actions_dir = self.actions_dir,
            judgments_dir = self.judgments_dir,
            max_actions = self.max_actions,
            agent_response_key = self.agent_response_key,
            skip_finished = self.skip_finished,
            prune_observations = self.prune_observations,
            seed = self.seed,
            rank = self.rank,
            world_size = self.world_size
        )

    def list_trajectories(
        self, dataset: List[Dict[str, str]]
    ) -> List[InstaPipelineOutput]:
        """Run the InSTA pipeline for internet-scale data collection, and list
        the observations, actions, and judgments for each task.

        Arguments:

        dataset: List[Dict[str, str]]
            Override the default dataset, and run the pipeline on custom tasks,
            each entry must be a dictionary with keys "domain" and "task".

        Returns:

        List[InstaPipelineOutput]
            List with observations, actions, and judgments for each task, 
            which are saved to disk for later processing.
        
        """

        return list_trajectories(
            dataset = dataset, env = self.env,
            agent = self.agent, judge = self.judge, 
            observations_dir = self.observations_dir,
            screenshot_dir = self.screenshot_dir,
            actions_dir = self.actions_dir,
            judgments_dir = self.judgments_dir,
            max_actions = self.max_actions,
            agent_response_key = self.agent_response_key,
            skip_finished = self.skip_finished,
            prune_observations = self.prune_observations,
            seed = self.seed,
            rank = self.rank,
            world_size = self.world_size
        )

    def save_trajectories(self, dataset: List[Dict[str, str]]) -> None:
        """Run the InSTA pipeline for internet-scale data collection, and save
        the observations, actions, and judgments for each task.

        Arguments:

        dataset: List[Dict[str, str]]
            Override the default dataset, and run the pipeline on custom tasks,
            each entry must be a dictionary with keys "domain" and "task".
        
        """

        save_trajectories(
            dataset = dataset, env = self.env,
            agent = self.agent, judge = self.judge, 
            observations_dir = self.observations_dir,
            screenshot_dir = self.screenshot_dir,
            actions_dir = self.actions_dir,
            judgments_dir = self.judgments_dir,
            max_actions = self.max_actions,
            agent_response_key = self.agent_response_key,
            skip_finished = self.skip_finished,
            prune_observations = self.prune_observations,
            seed = self.seed,
            rank = self.rank,
            world_size = self.world_size
        )

    def launch(
        self, dataset: List[Dict[str, str]],
        return_trajectories: bool = DEFAULT_RETURN_TRAJECTORIES,
        num_agents: int = DEFAULT_NUM_AGENTS,
        playwright_workers: int = DEFAULT_PLAYWRIGHT_WORKERS,
    ) -> List[InstaPipelineOutput] | None:
        """Run parallel agents to complete web navigation tasks,
        such as for performing Deep Research across the whole internet.

        Arguments:

        dataset: List[Dict[str, str]]
            Override the default dataset, and run the pipeline on custom tasks,
            each entry must be a dictionary with keys "domain" and "task".

        return_trajectories: bool
            Whether to return trajectories or just save them.

        num_agents: int
            Number of parallel agents to run.

        playwright_workers: int
            Number of Playwright workers running.

        Returns:

        List[InstaPipelineOutput] | None
            List with observations, actions, and judgments for each task, 
            which are saved to disk for later processing.
        
        """

        return launch_data_collection(
            dataset = dataset, agent_config = self.agent_config,
            judge_config = self.judge_config, browser_config = self.browser_config,
            observations_dir = self.observations_dir,
            screenshot_dir = self.screenshot_dir,
            actions_dir = self.actions_dir,
            judgments_dir = self.judgments_dir,
            max_actions = self.max_actions,
            agent_response_key = self.agent_response_key,
            skip_finished = self.skip_finished,
            prune_observations = self.prune_observations,
            seed = self.seed,
            return_trajectories = return_trajectories,
            num_agents = num_agents,
            playwright_workers = playwright_workers,
            rank = self.rank,
            world_size = self.world_size,
        )
