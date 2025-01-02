from setuptools import setup, find_packages

setup(
    name="nmkr_support_v4",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "nmkr_support_v4": ["*.json"],
    },
) 