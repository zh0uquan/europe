import os
import re
import json
import toml
import delegator
import subprocess

import click
from jsonschema import validate
from pathlib import Path
from poetry.utils.toml_file import TomlFile
from poetry.packages import Package, VCSDependency

VERSION_BUMP_RE = re.compile(
    r"(?P<major>\*)|(?P<minor>\d+\.\*)|(?P<patch>\d+\.\d+\.\*)"
)
VERSION_RE = re.compile('version\s+=\s+"*(?P<version>(\d+\.\d+\.\d+))"*')

ROOT_PATH = Path(".")
REPO_NAME = re.compile(r"europe(\.\w+])*")
AUTOGEN_REQ_INI = "autogen_requirements.ini"
AUTOGEN_REQ_TXT = "autogen_requirements.txt"
AUTO_TEST = "autogen_test.sh"
SETUP_PY = "setup.py"

PAC_JSON_SCHEMA = {
    "definitions": {},
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/root.json",
    "type": "object",
    "title": "The Root Schema",
    "required": ["package", "dependencies", "dev-dependencies"],
    "properties": {
        "package": {
            "$id": "#/properties/package",
            "type": "object",
            "title": "The Package Schema",
            "required": ["name", "version"],
            "properties": {
                "name": {
                    "$id": "#/properties/package/properties/name",
                    "type": "string",
                    "title": "The Name Schema",
                    "default": "",
                    "pattern": "^(.*)$",
                },
                "version": {
                    "$id": "#/properties/package/properties/version",
                    "type": "string",
                    "title": "The Version Schema",
                    "default": "",
                    "examples": ["0.1.0"],
                    "pattern": "^(.*)$",
                },
            },
        },
        "dependencies": {
            "$id": "#/properties/dependencies",
            "type": "object",
            "title": "The Dependencies Schema",
            "default": None,
            "": "",
        },
        "dev-dependencies": {
            "$id": "#/properties/dev-dependencies",
            "type": "object",
            "title": "The Dev-dependencies Schema",
        },
    },
}

NO_MANUL_BUMP_VERSION_ERROR = """
Please check package {name}
No manual version bump found in your toml file!
Please use fuzzy bump to increase the package you changed!
For example, if you want to release a new major change, do
change the version in pac.toml file as follows:

[package]
name = changed_package
version = "*" # indicates a major bump for automated scripts

"""

SETUP_PY_TEMPLATE = """
from setuptools import setup

setup(
    name="{package_name}",
    version="{package_version}",
    description="AUTO GENERATED SCRIPT",
    packages=["{package_name}"],
    include_package_data=True,
    zip_safe=True
)
"""


class ModifiedPackage(Package):
    def __init__(self, name, version, old_version):
        if not VERSION_BUMP_RE.match(version):
            raise RuntimeError(NO_MANUL_BUMP_VERSION_ERROR.format(name=name))

        self._old_version = old_version
        self._next_version = _get_next_version(version, old_version)
        super().__init__(name, self._next_version)


    @property
    def next_version(self):
        return self._next_version

    @property
    def old_version(self):
        return self._old_version


def _get_next_version(version_constraint, old_version) -> str:
    match = VERSION_BUMP_RE.match(version_constraint)
    major, minor, patch = old_version.split(".")

    if match.group("major"):
        return f"{int(major)+1}.0.0"

    elif match.group("minor"):
        return f"{major}.{int(minor)+1}.0"

    elif match.group("patch"):
        return f"{major}.{minor}.{int(patch)+1}"


def _get_old_version(pac_file) -> str:

    c = delegator.run(f"git show origin/master:{pac_file} | grep version")
    match = VERSION_RE.match(c.out)
    if not match:
        raise RuntimeError(
            f"Modified package {pac_file} doesn't have a correct semantic version"
        )
    return match.group("version")


class Pac:
    def __init__(self, file: Path, local_config: dict, package: Package):
        self._file = TomlFile(file)
        self._local_config = local_config
        self._package = package

    @property
    def file(self):
        return self._file

    @property
    def local_config(self):
        return self._local_config

    @property
    def package(self):
        return self._package

    @classmethod
    def create(cls, pac_file: Path, modified=False):

        local_config = TomlFile(pac_file.as_posix()).read()
        if "package" not in local_config:
            raise RuntimeError(
                "[package] section not found in {}".format(pac_file.name)
            )
        # Checking validity
        cls.check(local_config)

        if str(pac_file.parent) == str(ROOT_PATH):
            name = local_config["package"]["name"]

        else:
            if pac_file.parts[-2] != local_config["package"]["name"]:
                raise RuntimeWarning(
                    "[package] directory name is not as same as we "
                    "defined in {},".format(pac_file)
                )

            name = re.sub("/", ".", str(pac_file.parent))
        version = local_config["package"]["version"]

        if not modified:
            package = Package(name, version)
        else:
            old_version = _get_old_version(pac_file)
            package = ModifiedPackage(name, version, old_version)

        package.root_dir = pac_file.parent

        if "dependencies" in local_config:
            for name, constraint in local_config["dependencies"].items():
                package.add_dependency(name, constraint)

        if "dev-dependencies" in local_config:
            for name, constraint in local_config["dev-dependencies"].items():
                package.add_dependency(name, constraint, category="dev")

        return cls(pac_file, local_config, package)

    @classmethod
    def check(cls, config):
        """
        Checks the validity of a configuration
        """
        validate(config, PAC_JSON_SCHEMA)


def generate_requirements_text(requirements):
    with open(AUTOGEN_REQ_INI, "w+") as f:
        for dep in requirements:
            if isinstance(dep, VCSDependency):
                f.write(f"-e {dep.source}#egg={dep.name}\n")
            else:
                f.write(f"{dep.to_pep_508()}\n")

    c = delegator.run(f"pip-compile {AUTOGEN_REQ_INI} -v")
    c.run()
    if c.err:
        raise RuntimeError(c.err)
    print(c.out)

    os.remove(AUTOGEN_REQ_INI)


def get_requirements(package, dev=False):
    if dev:
        requirements = package.requires + package.dev_requires
    else:
        requirements = package.requires
    return requirements


def install_package(package):
    with open("setup.py", "w+") as f:
        f.write(
            SETUP_PY_TEMPLATE.format(
                package_name=package.name, package_version=package.version
            )
        )

    try:
        c1 = delegator.run("python setup.py install")
        c2 = delegator.run(f"pip install -r {AUTOGEN_REQ_TXT}")
        if c1.err or c2.err:
            raise Exception(
                f"""{c1.err}
                
                {c2.err}
                """
            )
    except Exception as e:
        raise RuntimeError(e)
    else:
        print(c1.out)
        print(c2.out)
    finally:
        os.remove(AUTOGEN_REQ_TXT)
        os.remove(SETUP_PY)


def run_package_tests(package):
    path = re.sub("\.", "/", package.name)
    subprocess.call(["pytest", f"{path}"])


def track_changed_paths():
    c = delegator.run("git diff origin/master --name-only")
    package_paths = set()

    for path in c.out.split("\n"):
        # we don't detect changes in non python code
        if Path(path).suffix != ".py":
            continue

        package_path = Path(path).parent
        if "tests" in str(package_path):
            package_path = Path(path).parents[1]

        # remove root changes
        if ROOT_PATH in package_paths:
            package_paths.remove(ROOT_PATH)

        while True:
            # make sure changes belong to one of the package
            if (package_path / "pac.toml").exists():
                break
            package_path = Path(package_path).parents[0]
        package_paths.add(package_path)

    return set(path / "pac.toml" for path in package_paths)


@click.command()
def scoped_test():
    c = delegator.run("git branch | grep \* | cut -d ' ' -f2")
    if c.err:
        raise RuntimeError("current branch is not shown due to err")

    all_paths = set(Path(".").rglob("pac.toml"))
    changed_paths = track_changed_paths()
    pending_paths = all_paths - changed_paths

    changed_packages = [
        Pac.create(path, modified=True).package for path in changed_paths
    ]
    pending_packages = [Pac.create(path).package for path in pending_paths]

    affected_packages = set()

    changed_package_dict = {package.name: package for package in changed_packages}

    for package in pending_packages:
        # skip the package we have changed
        if package in changed_packages:
            continue

        for dependency in package.requires:
            dependency_name = dependency.name
            if dependency_name not in changed_package_dict:
                continue

            if package in affected_packages:
                continue

            # pac's dependency is affected by changed packages
            if dependency.accepts(changed_package_dict[dependency_name]):
                affected_packages.add(package)

    affected_packages = list(affected_packages)

    print(f"we have tracked changed packages: {changed_packages}")
    print(f"we have found affected packages {affected_packages}")

    for package in changed_packages + affected_packages:
        # we need to assume all the requirements in package
        # is already built there, to let us to install from
        print(package.name)
        print("=" * 80)
        requirements = get_requirements(package, dev=True)
        generate_requirements_text(requirements)
        install_package(package)
        run_package_tests(package)

    # detect global conflicts by checking the requirements compiled together
    requirements = []
    for package in changed_packages + affected_packages:
        requirements.extend(get_requirements(package, dev=True))

    # try to compile and see if there is a error
    generate_requirements_text(requirements)


@click.command()
def merge():
    changed_paths = track_changed_paths()

    changed_pacs = [Pac.create(path, modified=True) for path in changed_paths]
    for pac in changed_pacs:
        pac.local_config['package']['version'] = pac.package.next_version
        with open(pac.file.path, "w") as f:
            f.write(pac.local_config.as_string())


@click.group()
def cli():
    pass


cli.add_command(scoped_test, "test")
# cli.add_command(publish, "release")
cli.add_command(merge, "merge")

if __name__ == "__main__":
    cli()

    # from poetry.packages import Dependency
    from poetry.installation import Installer

    # d = Dependency("pytest", "^4.0.0")
    # print(d.constraint)

    # functionality pac install version
