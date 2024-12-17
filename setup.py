from setuptools import setup, find_packages

setup(
    name="luxy",
    version="0.0.2",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0"
    ],
    author="William J.B. Mattingly",
    description="A Python wrapper for Yale's Lux API, provided by Yale University.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/project-lux/pylux",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.5",
)
