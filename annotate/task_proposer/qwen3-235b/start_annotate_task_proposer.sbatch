#!/bin/bash
#SBATCH --job-name=insta
#SBATCH --exclude=shire-1-1,shire-1-6,shire-1-10,shire-2-5,shire-2-9,babel-2-29,babel-0-19
#SBATCH --output=logs/task-proposer-%A-%a-%N.out
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --nodes=1
#SBATCH --partition=general
#SBATCH --array=0-7



# Slurm arguments for parallelism

export NFS_DIR=${NFS_DIR:-/data/matrix/projects/rsalakhugroup}

SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-0}
SLURM_ARRAY_TASK_COUNT=${SLURM_ARRAY_TASK_COUNT:-1}

RANK=${RANK:-${SLURM_ARRAY_TASK_ID}}
WORLD_SIZE=${WORLD_SIZE:-${SLURM_ARRAY_TASK_COUNT}}

source ~/anaconda3/etc/profile.d/conda.sh
conda activate insta



# Arguments for data collection

DATASET=${DATASET:-"data-for-agents/insta-150k-v3"}
DATASET_SPLIT=${DATASET_SPLIT:-"train"}

SET_EXPLORATION_MODE=${SET_EXPLORATION_MODE:-""}

INPUT_DATA_DIR=${INPUT_DATA_DIR:-"${NFS_DIR}/btrabucc/neurips_data_collection/gemini-2.5-flash-train"}

SKIP_FINISHED=${SKIP_FINISHED:-"--skip_finished"}

TASK_PROPOSER_MODEL_NAME=${TASK_PROPOSER_MODEL_NAME:-"Qwen/Qwen3-235B-A22B-fp8-tput"}
TASK_PROPOSER_LLM_ENDPOINT=${TASK_PROPOSER_LLM_ENDPOINT:-"https://api.together.xyz/v1"}
TASK_PROPOSER_API_KEY=${TASK_PROPOSER_API_KEY:-${TOGETHER_API_KEY}}

JUDGE_NAME=${JUDGE_NAME:-"qwen3-235b-judge"}
TASK_PROPOSER_NAME=${TASK_PROPOSER_NAME:-"qwen3-235b-task-proposer"}

ADD_STEPS_TO_TASK_PROPOSER=${ADD_STEPS_TO_TASK_PROPOSER:-"--add_steps_to_task_proposer"}
ADD_CRITERIA_TO_TASK_PROPOSER=${ADD_CRITERIA_TO_TASK_PROPOSER:-"--add_criteria_to_task_proposer"}

TASK_PROPOSER_DISABLE_THINKING_CHAT_TEMPLATE=${TASK_PROPOSER_DISABLE_THINKING_CHAT_TEMPLATE:-"--task_proposer_disable_thinking_chat_template"}
TASK_PROPOSER_REASONING_EFFORT=${TASK_PROPOSER_REASONING_EFFORT:-""}

TASK_PROPOSER_PROMPT=${TASK_PROPOSER_PROMPT:-"verbose"}



# Array arguments for scripts

LLM_ARGS=(
    --task_proposer_model_name ${TASK_PROPOSER_MODEL_NAME}
    --task_proposer_llm_endpoint ${TASK_PROPOSER_LLM_ENDPOINT}
    --task_proposer_api_key ${TASK_PROPOSER_API_KEY}
    ${ADD_STEPS_TO_TASK_PROPOSER}
    ${ADD_CRITERIA_TO_TASK_PROPOSER}
)

SAMPLING_ARGS=(
    ${TASK_PROPOSER_DISABLE_THINKING_CHAT_TEMPLATE}
    ${TASK_PROPOSER_REASONING_EFFORT}
)

PIPELINE_ARGS=(
    --rank ${RANK}
    --world_size ${WORLD_SIZE}
    ${SKIP_FINISHED}
)

DATA_ARGS=(
    --input_data_dir ${INPUT_DATA_DIR}
    --judge_name ${JUDGE_NAME}
    --task_proposer_name ${TASK_PROPOSER_NAME}
    --task_proposer_prompt ${TASK_PROPOSER_PROMPT}
    --dataset ${DATASET}
    --dataset_split ${DATASET_SPLIT}
    ${SET_EXPLORATION_MODE}
)

ANNOTATE_ARGS=(
    insta.entry_points.annotate_task_proposer
    ${LLM_ARGS[@]}
    ${SAMPLING_ARGS[@]}
    ${PIPELINE_ARGS[@]}
    ${DATA_ARGS[@]}
)



# Annotate trajectories using the task proposer

python -um ${ANNOTATE_ARGS[@]}