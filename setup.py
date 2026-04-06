from pathlib import Path

from setuptools import find_packages, setup


if __name__ == "__main__":
    setup(
        name="kflow",
        version="0.1.0",
        description="Workflow enforcement CLI for local software delivery",
        long_description=Path("README.md").read_text(encoding="utf-8"),
        long_description_content_type="text/markdown",
        python_requires=">=3.10",
        packages=find_packages(include=["kflow", "kflow.*"]),
        include_package_data=True,
        install_requires=[
            "typer>=0.12,<1.0",
            "pydantic>=2.7,<3.0",
            "PyYAML>=6.0,<7.0",
            "rich>=13.7,<14.0",
        ],
        extras_require={
            "dev": ["pytest>=8.0,<9.0"],
        },
        entry_points={
            "console_scripts": ["kflow=kflow.main:main"],
        },
    )
