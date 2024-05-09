import argparse
import re
from pathlib import Path

import semver

from .base import Validator
from .models import CheckError, CheckResult


class ChangelogValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        changelog_path = module_dir / "CHANGELOG.md"

        if not changelog_path.is_file():
            result.errors.append(
                CheckError(filepath=changelog_path, error="changelog is missing")
            )
            return

        result.options["changelog_path"] = changelog_path

        with open(changelog_path, "rt") as file:
            text = file.read()

        cls.validate_changelog_content(
            text=text, path=changelog_path, result=result, args=args
        )

    @classmethod
    def validate_changelog_content(
        cls, text: str, path: Path, result: CheckResult, args: argparse.Namespace
    ) -> None:
        changelog = ChangeLog.parse(data=text)
        changelog.validate(path, result)


class ChangeLogElement:
    def __init__(
        self,
        raw: str = "",
        title: str = "",
        body: str = "",
        line_number: int | None = None,
    ):
        self.__raw = raw
        self.__title = title
        self.__body = body
        self.__line_number = line_number

    def line_number(self) -> int:
        return self.__line_number

    def title(self) -> str:
        return self.__title

    def body(self) -> str:
        return self.__body

    def raw(self) -> str:
        return self.__raw

    def __repr__(self):
        return self.body()


class ChangeLog:
    SEMVER_REGEX = (
        r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|["
        r"1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+("
        r"?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))? "
    )

    def __init__(
        self,
        data: str = "",
        headers=None,
        versions=None,
    ):
        self.__data = data
        self.__headers = headers if headers else []
        self.__versions = versions if versions else []

    def header(self):
        # Gives access to the top level heading element
        if self.__headers and len(self.__headers) > 0:
            return self.__headers[0]

    def title(self):
        # Returns the title of the changelog
        if self.__headers and len(self.__headers) > 0:
            return self.__headers[0].title()
        return None

    def versions(self) -> list[ChangeLogElement]:
        # Returns a list of all available versions
        return self.__versions

    @classmethod
    def parse(cls, data: str) -> "ChangeLog":
        # read header
        headers = cls.parse_changelog_header(data, 1, 2)

        # read versions
        versions = cls.parse_changelog_header(data, 2, 2)
        # versions = [KACLVersion(element=x) for x in versions]

        return cls(data=data, headers=headers, versions=versions)

    def validate(self, path: Path, result: CheckResult):
        allowed_header_titles = {"Changelog", "Change log"}
        default_content = [
            "All notable changes to this project will be documented in this file.",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), "
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
        ]

        # 1. assert only one header and starts on first line
        if len(self.__headers) == 0:
            result.errors.append(
                CheckError(filepath=path, error="No 'Changelog' header found.")
            )
            return

        elif self.header().raw() != self.header().raw().lstrip():
            result.errors.append(
                CheckError(
                    filepath=path, error="Changelog header not placed on first line."
                )
            )

        if len(self.__headers) > 1:
            for header in self.__headers[1:]:
                result.errors.append(
                    CheckError(
                        filepath=path,
                        error="Unexpected additional top-level heading found.",
                    )
                )

        # 1.1 assert header title is in allowed list of header titles
        if self.header().title() not in allowed_header_titles:
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"Header title not valid. Options are [{','.join(allowed_header_titles)}]",
                )
            )

        # 1.2 assert default content is in the header section
        for default_line in default_content:
            if default_line not in self.header().body().replace("\n", " "):
                result.errors.append(
                    CheckError(
                        filepath=path, error=f"Missing default content '{default_line}'"
                    )
                )

        # 3. assert versions in valid format
        versions = self.versions()
        if len(versions) == 0:
            result.errors.append(
                CheckError(filepath=path, error=f"No entries in changelog")
            )

        for v in versions:
            self.validate_version_semver(v, path, result)
            self.validate_version_date(v, path, result)
            self.validate_version_sections(v, path, result)

        # 3.1 assert versions in descending order
        for i in range(len(versions) - 1):
            try:
                v0 = versions[i]
                v1 = versions[i + 1]
                if (
                    semver.VersionInfo.compare(
                        semver.Version.parse(self.get_version_from_element(v0)),
                        semver.Version.parse(self.get_version_from_element(v1)),
                    )
                    < 1
                ):
                    result.errors.append(
                        CheckError(
                            filepath=path, error="Versions are not in descending order."
                        )
                    )

            except Exception:
                pass

    def get_version_from_element(self, version: ChangeLogElement) -> str:
        title = version.title()
        m = re.search(self.SEMVER_REGEX, title)
        if m:
            return m.group().strip()

        elif "unreleased" in title.lower():
            return "Unreleased"

    def validate_version_semver(
        self, version: ChangeLogElement, path: Path, result: CheckResult
    ):
        sem_ver = self.get_version_from_element(version)
        if sem_ver is None:
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"Line '{version.title()}' has invalid semantic version.",
                )
            )

    def validate_version_date(
        self, version: ChangeLogElement, path: Path, result: CheckResult
    ):
        sem_ver = self.get_version_from_element(version)
        if sem_ver == "Unreleased":
            return

        m = re.search(r"\d\d\d\d-\d\d-\d\d", version.title())
        if not m:
            result.errors.append(
                CheckError(
                    filepath=path,
                    error="Versions need to be decorated with a release date in the following format 'YYYY-MM-DD'",
                )
            )
            return

        m2 = re.match(r"\d\d\d\d-[0-1][\d]-[0-3][\d]", m.group())
        if not m2:
            result.errors.append(
                CheckError(
                    filepath=path, error="Date does not match format 'YYYY-MM-DD'"
                )
            )
            return

    def validate_version_sections(
        self, version: ChangeLogElement, path: Path, result: CheckResult
    ):
        allowed_version_sections = {
            "Added",
            "Changed",
            "Deprecated",
            "Removed",
            "Fixed",
            "Security",
        }

        # 3.1 check that there is no text outside a section
        body = version.body().replace("\n", "").strip()
        if body and not body.startswith("###"):
            result.errors.append(
                CheckError(
                    filepath=path, error=f"Version has content outside of a section."
                )
            )

        # 3.3 check that only allowed sections are in the version
        parsed_sections = self.parse_changelog_header(
            text=version.body(),
            start_depth=3,
            end_depth=3,
            line_offset=version.line_number(),
        )

        sections = {}
        for sec in parsed_sections:
            sections[sec.title()] = sec

        for title, element in sections.items():
            if title not in allowed_version_sections:
                result.errors.append(
                    CheckError(
                        filepath=path,
                        error=f'"{title}" is not a valid section for a version. Options are [{",".join(allowed_version_sections)}]',
                    )
                )

    @staticmethod
    def parse_changelog_header(
        text: str, start_depth: int, end_depth: int | None = None, line_offset: int = 0
    ) -> list[ChangeLogElement]:
        # Inspired by https://gitlab.com/schmieder.matthias/python-kacl/-/blob/main/kacl/parser.py?ref_type=heads#L10
        if not end_depth:
            end_depth = start_depth

        elements = []
        reg_expr_start = r"(\n{depth}|^{depth})\s+?(.*)\n".format(
            depth="#" * start_depth
        )
        reg_expr_end = r"(\n{depth}|^{depth})\s+?(.*)\n".format(depth="#" * end_depth)
        for match in re.finditer(reg_expr_start, text):
            # find end of section
            raw = match.group().strip()
            title = match.group(2).strip()
            start = match.start()
            end = match.end()
            line_number = text[:start].count("\n") + line_offset
            if match.group()[0] == "\n":
                line_number += 2
            else:
                line_number += 1

            next_match = re.search(reg_expr_end, text[end:])

            if next_match:
                body = text[end : next_match.start() + end]
            else:
                body = text[end:]

            elements.append(
                ChangeLogElement(
                    raw=raw, title=title, body=body, line_number=line_number
                )
            )

        return elements
