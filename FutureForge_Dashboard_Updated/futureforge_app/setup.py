from setuptools import setup, find_packages

setup(
    name="futureforge-ml",
    version="1.0.0",
    description="FutureForge - Hybrid AI Productivity Prediction System",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="FutureForge Team",
    author_email="team@futureforge.ai",
    url="https://github.com/futureforge/hybrid-predictor",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "tensorflow>=2.10.0",
        "scikit-learn>=1.0.0",
        "pandas>=1.3.0",
        "numpy>=1.20.0",
        "joblib>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "flake8>=3.9",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
