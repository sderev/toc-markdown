"""
Setup configuration for the toc-markdown package.

This script uses setuptools to package and distribute the toc-markdown
library. It also reads the requirements and long description directly 
from external files for ease of maintenance.
"""
from setuptools import find_packages, setup

VERSION = "0.0.1"


def read_requirements():
    """
    Read requirements from requirements.txt file.
    """
    with open("requirements.txt", encoding="UTF-8") as file:
        return list(file)


def get_long_description():
    """
    Read README.md file.
    """
    with open("README.md", encoding="utf8") as file:
        return file.read()


setup(
    name="toc-markdown",
    description="Generate a table of contents for a Markdown file.",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Sébastien De Revière",
    url="https://github.com/sderev/toc-markdown",
    project_urls={
        "Documentation": "https://github.com/sderev/toc-markdown",
        "Issues": "http://github.com/sderev/toc-markdown/issues",
        "Changelog": "https://github.com/sderev/toc-markdown/releases",
    },
    license="Apache Licence, Version 2.0",
    version=VERSION,
    packages=find_packages(),
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "toc-markdown=toc_markdown.cli:cli",
        ]
    },
    python_requires=">=3.8",
)
