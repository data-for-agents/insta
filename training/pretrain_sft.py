from trl import SFTConfig, SFTTrainer
from datasets import load_dataset

from insta.configs.agent_config import (
    AgentConfig,
    get_agent_config,
    DEFAULT_AGENT_CONFIG
)

from insta.agent import BrowserAgent
from functools import partial

import argparse
import json
import os


def select_valid_samples(
    example: dict,
    base_data_dir: str = "data-v3",
) -> bool:

    observations_dir = os.path.join(
        base_data_dir,
        "observations"
    )

    actions_dir = os.path.join(
        base_data_dir,
        "actions"
    )

    judgments_dir = os.path.join(
        base_data_dir,
        "judgments"
    )
            
    valid_domain = (
        os.path.exists(
            os.path.join(
                observations_dir,
                "{}.json".format(example["domain"])
            )
        ) and os.path.exists(
            os.path.join(
                actions_dir,
                "{}.json".format(example["domain"])
            )
        ) and os.path.exists(
            os.path.join(
                judgments_dir,
                "{}.json".format(example["domain"])
            )
        )
    )

    return valid_domain


def prepare_messages(
    examples: dict,
    base_data_dir: str = "data-v3",
    agent: BrowserAgent = None,
) -> dict:

    observations_dir = os.path.join(
        base_data_dir,
        "observations"
    )

    actions_dir = os.path.join(
        base_data_dir,
        "actions"
    )

    judgments_dir = os.path.join(
        base_data_dir,
        "judgments"
    )

    domains = examples["domain"]
    instructions = examples["task"]

    messages = []
    
    for domain, instruction in zip(domains, instructions):

        observations_path = os.path.join(
            observations_dir,
            "{}.json".format(domain)
        )

        actions_path = os.path.join(
            actions_dir,
            "{}.json".format(domain)
        )

        with open(observations_path, "r") as file:
            observations = json.load(file)

        with open(actions_path, "r") as file:
            actions = json.load(file)

        for last_timestep in range(1, len(observations)):

            first_timestep = max(0, last_timestep - agent.config.max_history - 1)

            obs = observations[first_timestep:last_timestep]
            act = actions[first_timestep:last_timestep]

            current_message = [{
                "role": "system",
                "content": agent.system_prompt
            }]

            for obs_t, act_t in zip(obs, act):

                invalid_step = (
                    obs_t['processed_text'] is None or
                    act_t['response'] is None
                )

                if invalid_step:

                    continue

                user_prompt = agent.get_user_prompt(
                    observation = obs_t['processed_text'],
                    instruction = instruction
                )

                current_message.append({
                    "role": "user",
                    "content": user_prompt
                })

                current_message.append({
                    "role": "assistant",
                    "content": act_t['response']
                })

            messages.append(
                current_message
            )

    return {
        "messages": messages
    }


if __name__ == "__main__":

    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "4"

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model_name",
        type = str,
        default="Qwen/Qwen2.5-1.5B-Instruct"
    )

    parser.add_argument(
        "--dataset_name",
        type = str,
        default="data-for-agents/insta-150k-v2"
    )

    parser.add_argument(
        "--dataset_split",
        type = str,
        default="train"
    )

    parser.add_argument(
        "--base_data_dir",
        type = str,
        default="data-v3"
    )

    parser.add_argument(
        "--output_dir",
        type = str,
        default="./qwen-1.5b"
    )

    parser.add_argument(
        "--max_seq_length",
        type = int,
        default = 8196
    )

    parser.add_argument(
        "--max_history",
        type = int,
        default = 2
    )

    parser.add_argument(
        "--max_obs_length",
        type = int,
        default = 2048
    )

    parser.add_argument(
        "--use_bf16",
        action = "store_true"
    )

    args = parser.parse_args()

    dataset = load_dataset(
        args.dataset_name,
        split = args.dataset_split
    )

    agent_config = get_agent_config(
        max_history = args.max_history,
        max_obs_tokens = args.max_obs_length,
    )

    agent: BrowserAgent = BrowserAgent(
        agent_config,
        action_parser = "json"
    )

    # client cannot be pickled
    agent.llm_client = None

    select_valid_samples = partial(
        select_valid_samples,
        base_data_dir = args.base_data_dir
    )
    
    dataset = dataset.filter(
        select_valid_samples
    )

    prepare_messages = partial(
        prepare_messages,
        base_data_dir = args.base_data_dir,
        agent = agent
    )

    insta_dataset = dataset.map(
        prepare_messages,
        batched = True,
        remove_columns = dataset.column_names,
        batch_size = 32,
        num_proc = 8,
    )

    training_args = SFTConfig(
        optim = "adamw_torch_fused",
        gradient_checkpointing = True,
        gradient_checkpointing_kwargs = {'use_reentrant': False},
        gradient_accumulation_steps = 4,
        learning_rate = 1e-5,
        num_train_epochs = 1,
        max_length = args.max_seq_length,
        output_dir = args.output_dir,
        per_device_train_batch_size = 1,
        per_device_eval_batch_size = 1,
        bf16 = args.use_bf16,
    )

    trainer = SFTTrainer(
        model = args.model_name,
        train_dataset = insta_dataset,
        args = training_args,
    )

    trainer.train()