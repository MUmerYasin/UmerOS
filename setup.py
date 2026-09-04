# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
UmerOS setuptools configuration.

All UmerOS dependencies are pinned in ``requirements.txt``; this file
is only the minimal metadata so the project is pip-installable and
the ``umer-pkg`` console entry point is registered.

The full quantum / ML / cryptography stack is large (and not every
developer needs every wheel).  The ``extras_require`` table below
lets a developer install just the slices they need:

    pip install -e .                # core runtime only
    pip install -e .[quantum]        # + Qiskit, Cirq, PennyLane
    pip install -e .[ml]             # + ONNX, PyTorch, transformers
    pip install -e .[ui]             # + Kivy (legacy UI)
    pip install -e .[dev]            # + pytest, sphinx, etc.
    pip install -e .[all]            # everything
"""

from __future__ import annotations

from setuptools import find_packages, setup

setup(
    name="umer_os",
    version="2.0.0",
    author="Muhammad Umer Yasin",
    author_email="mumeryasin123456789@gmail.com",
    description=(
        "A Python-first, hybrid classical-quantum, AI-native, "
        "cross-device operating system."
    ),
    long_description=open("README.md", encoding="utf-8").read()
    if __import__("os").path.isfile("README.md")
    else "",
    long_description_content_type="text/markdown",
    url="https://github.com/MUmerYasin/UmerOS",
    license="GPL-3.0-or-later",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        # Core scientific stack — present on every install.
        "numpy>=1.26.0",
        "cryptography>=42.0.0",
    ],
    extras_require={
        "quantum": [
            "qiskit>=1.0.0",
            "qiskit-aer>=0.14.0",
            "cirq>=1.3.0",
            "pennylane>=0.35.0",
            "qiskit-ibm-runtime>=0.20.0",
        ],
        "ml": [
            "onnxruntime>=1.17.0",
            "transformers>=4.40.0",
            "sentence-transformers>=2.7.0",
            "torch>=2.2.0",
            "llama-cpp-python>=0.2.0",
            "scikit-learn>=1.4.0",
            "scipy>=1.11.0",
        ],
        "ui": [
            "kivy>=2.3.0",  # legacy UI; Flutter is the canonical frontend.
            "Pillow>=10.2.0",
        ],
        "net": [
            "aiohttp>=3.9.0",
            "dnspython>=2.6.0",
            "httpx>0.27.0",
            "fastapi>0.110.0",
            "uvicorn[standard]>0.30.0",
        ],
        "security": [
            "liboqs-python>=0.9.0",
            "PyNaCl>=1.5.0",
            "python-jose[cryptography]>=3.3.0",
            "prometheus-client>=0.20.0",
            "loguru>=0.7.0",
        ],
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=2.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "all": [
            "qiskit>=1.0.0", "qiskit-aer>=0.14.0", "cirq>=1.3.0",
            "pennylane>=0.35.0", "qiskit-ibm-runtime>=0.20.0",
            "onnxruntime>=1.17.0", "transformers>=4.40.0",
            "sentence-transformers>=2.7.0", "torch>=2.2.0",
            "llama-cpp-python>=0.2.0", "scikit-learn>=1.4.0",
            "scipy>=1.11.0", "kivy>=2.3.0", "Pillow>=10.2.0",
            "aiohttp>=3.9.0", "dnspython>=2.6.0", "httpx>0.27.0",
            "fastapi>0.110.0", "uvicorn[standard]>0.30.0",
            "liboqs-python>=0.9.0", "PyNaCl>=1.5.0",
            "python-jose[cryptography]>=3.3.0",
            "prometheus-client>=0.20.0", "loguru>=0.7.0",
            "pytest>=8.0.0", "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0", "sphinx>=7.2.0",
            "sphinx-rtd-theme>=2.0.0", "black>=23.0.0",
            "flake8>=6.0.0", "mypy>=1.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Operating System",
        "Topic :: Scientific/Engineering",
    ],
    entry_points={
        "console_scripts": [
            "umer-pkg=packages.umer_pkg:main",
            "umeros=main:boot",
        ],
    },
    python_requires=">=3.12",
    include_package_data=True,
    zip_safe=False,
)
