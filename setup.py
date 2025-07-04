import setuptools


REQUIREMENTS = [
    'gymnasium',
    'huggingface-hub',
    'transformers',
    'datasets',
    'openai',
    'vllm',
    'lxml[html_clean]',
    'tqdm',
    'Pillow',
    'scikit-video',
    'opencv-python',
    'gradio',
    'gradio_client',
    'langchain',
]

URL = (
    'https://github.com/data-for-agents/environment'
)

DOWNLOAD_URL = (
    'https://github.com/data-for-agents/environment/archive/v0_1.tar.gz'
)

DESCRIPTION = (
    'Official training environment for --- InSTA: Towards Internet-Scale Training For Agents.'
)

CLASSIFIERS = [
    'Intended Audience :: Developers',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering',
    'Topic :: Scientific/Engineering :: Artificial Intelligence',
    'Topic :: Scientific/Engineering :: Mathematics',
    'Topic :: Software Development',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
]

ENTRY_POINTS = {
    'console_scripts': [
        'start-insta-pipeline=insta.entry_points.insta_pipeline:start_insta_pipeline',
        'start-annotate-judge=insta.entry_points.annotate_judge:start_annotate_judge',
        'start-annotate-task-proposer=insta.entry_points.annotate_task_proposer:start_annotate_task_proposer',
    ]
}


setuptools.setup(
    name = 'insta-env',
    author = 'Brandon Trabucco',
    author_email = 'brandon@btrabucco.com',
    version = '0.1',
    license = 'MIT',
    packages = ['insta'],
    install_requires = REQUIREMENTS,
    url = URL, download_url = DOWNLOAD_URL,
    description = DESCRIPTION,
    long_description = DESCRIPTION,
    long_description_content_type = 'text/markdown',
    classifiers = CLASSIFIERS,
    entry_points = ENTRY_POINTS,
    extras_require = {
        'pii': [
            'scrubadub',
            'scrubadub_spacy',
        ],
    },
)
