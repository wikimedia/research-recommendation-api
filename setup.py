from setuptools import setup, find_packages

setup(
    name="recommendation",
    version="0.4.0",
    url="https://github.com/wikimedia/research-recommendation-api",
    license="Apache Software License",
    maintainer="Wikimedia Research",
    maintainer_email="nschaaf@wikimedia.org",
    description="Provide recommendations in Wikimedia projects",
    long_description="",
    packages=find_packages(exclude=["test", "test.*", "*.test"]),
    install_requires=[
        "flask",
        "flask-restplus",
        "requests",
        "numpy",
        "scipy",
        "scikit-learn",
        # https://github.com/noirbizarre/flask-restplus/issues/777
        "Werkzeug==0.16.0",
    ],
    package_data={
        "recommendation.web": [
            "static/*.*",
            "static/i18n/*",
            "static/images/*",
            "static/suggest-searches/*",
            "templates/*",
        ],
        "recommendation": ["data/*"],
    },
    zip_safe=False,
    setup_requires=["pytest-runner", "setuptools_scm < 2.0.0"],
    tests_require=["pytest", "responses", "memory_profiler", "psutil"],
)
