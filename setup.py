from setuptools import setup, find_packages

setup(
    name='multifunction_tool',
    version='1.0',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'transcript=program:main',
        ],
    },
    install_requires=[
        'whisper', 
        'tiktoken', 
        'moviepy', 
        'tqdm'
    ]
)
