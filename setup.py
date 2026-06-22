from setuptools import setup, find_packages

setup(
    name="umer_os",
    version="2.0.0",
    author="Umer",
    description="A Python-first, hybrid classical-quantum, AI-native, cross-device operating system.",
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "qiskit>=1.0.0",
        "numpy>=1.26.0",
        "onnxruntime>=1.17.0",
        "cryptography>=42.0.0",
        "kivy>=2.3.0",
        "aiohttp>=3.9.0"
    ],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.12",
    ],
    entry_points={
        'console_scripts': [
            'umer-pkg=packages.umer_pkg:main',
        ],
    },
)
