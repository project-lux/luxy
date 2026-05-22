from setuptools import setup, find_packages

setup(
    name="luxy",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "luxql @ git+https://github.com/project-lux/luxql.git@main#egg=luxql",
    ],
    extras_require={
        "qlever": ["SPARQLWrapper>=2.0"],
        "lmdb": ["lmdb>=1.4"],
        "all": ["SPARQLWrapper>=2.0", "lmdb>=1.4"],
    },
    author="William J.B. Mattingly",
    description=(
        "A Python wrapper for Yale's Lux API with luxql-backed query building, "
        "graph-style relationship filtering, response profiles, pluggable backends "
        "(MarkLogic / QLever), and adaptive rate limiting."
    ),
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/project-lux/luxy",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
)
