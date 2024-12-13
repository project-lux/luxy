from setuptools import setup, find_packages

setup(
    name="pylux",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0"
    ],
    author="Yale University",
    description="A Python wrapper for Yale's Lux API.",
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
