from setuptools import setup, find_packages

print(find_packages('.'))

setup(
    name="europe",
    version="0.1.0",
    description="Project Europe",
    packages=find_packages("."),
    include_package_data=True,
)
