#!/usr/bin/env python3
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="supercrawler",
    version="1.0.0",
    author="SuperCrawler Team",
    author_email="example@example.com",
    description="灵活的基于YAML配置的网页爬虫工作流引擎",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/supercrawler",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "supercrawler=src.__main__:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.md"],
    },
) 