from setuptools import setup, find_packages


def find_namespaced_packages(namespace):
    """
    Like find_packages, but for the given local namespace directory.

    Working around https://github.com/pypa/setuptools/issues/97
    """
    packages = find_packages(namespace)
    return ["%s.%s" % (namespace, pkg) for pkg in packages]


setup(
    name="europe",
    version="0.1.1",
    description="Project Europe",
    packages=find_namespaced_packages("europe"),
    include_package_data=True,
)
