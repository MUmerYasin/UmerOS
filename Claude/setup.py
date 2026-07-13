"""
Umer OS — setup.py
==================
Standard Python package configuration for Umer OS.

Install in development mode::

    pip install -e .

Build a distributable::

    python setup.py sdist bdist_wheel
"""

from setuptools import setup, find_packages

setup(
    name="umer-os",
    version="0.1.0-alpha",
    description="Umer OS: Python-first hybrid classical-quantum AI-native operating system",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Umer OS Project",
    licence="Apache-2.0",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*", "docs*", "build*"]),
    install_requires=[
        "numpy>=1.26.0",
        "cryptography>=42.0.0",
    ],
    extras_require={
        "quantum": [
            "qiskit>=1.0.0",
            "qiskit-aer>=0.14.0",
            "cirq>=1.3.0",
            "pennylane>=0.35.0",
        ],
        "ai": [
            "onnxruntime>=1.17.0",
            "scikit-learn>=1.4.0",
        ],
        "ui": [
            "kivy>=2.3.0",
            "Pillow>=10.2.0",
        ],
        "pqc": [
            "liboqs-python>=0.9.0",
        ],
        "net": [
            "aiohttp>=3.9.0",
            "dnspython>=2.6.0",
            "zeroconf>=0.131.0",
        ],
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
        ],
        "all": [
            "numpy>=1.26.0",
            "cryptography>=42.0.0",
            "qiskit>=1.0.0",
            "qiskit-aer>=0.14.0",
            "cirq>=1.3.0",
            "pennylane>=0.35.0",
            "onnxruntime>=1.17.0",
            "scikit-learn>=1.4.0",
            "kivy>=2.3.0",
            "Pillow>=10.2.0",
            "aiohttp>=3.9.0",
            "dnspython>=2.6.0",
            "zeroconf>=0.131.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "umer-boot=boot.bootloader:main",
            "umer-install=installer.installer:main",
            "umer-pkg=packages.umer_pkg:main",
        ],
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Licence :: OSI Approved :: Apache Software Licence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Operating System",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
