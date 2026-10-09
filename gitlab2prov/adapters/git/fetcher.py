from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from git import Commit, Repo

from gitlab2prov.adapters.project_url import ProjectUrl
from gitlab2prov.domain.constants import ChangeType, ProvRole
from gitlab2prov.domain.objects import File, FileRevision, GitCommit, User

LOG_DELIMITER = "====DELIMITER===="
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass
class GitFetcher:
    project_url: type[ProjectUrl]
    repo: Repo | None = None
    tmpdir: TemporaryDirectory | None = None

    def __enter__(self) -> Self:
        self.tmpdir = TemporaryDirectory(ignore_cleanup_errors=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.repo:
            self.repo.close()
        if self.tmpdir:
            self.tmpdir.cleanup()

    def do_clone(self, url: str, token: str) -> None:
        clone_url = self.project_url(url).clone_url(token)
        self.repo = Repo.clone_from(clone_url, self.tmpdir.name)

    def fetch_git(self) -> Iterator[GitCommit | File | FileRevision]:
        for commit in self.repo.iter_commits("--all"):
            yield self.git_commit_to_domain_commit(commit)
            for file in self.fetch_files_for_commit(commit):
                yield file
                for revision in self.fetch_revisions_for_file(file):
                    yield revision

    @staticmethod
    def git_commit_to_domain_commit(commit: Commit) -> GitCommit:
        return GitCommit(
            sha=commit.hexsha,
            title=commit.summary,
            message=commit.message,
            author=get_author(commit),
            committer=get_committer(commit),
            deletions=commit.stats.total["deletions"],
            insertions=commit.stats.total["insertions"],
            lines=commit.stats.total["lines"],
            files_changed=commit.stats.total["files"],
            parents=[parent.hexsha for parent in commit.parents],
            authored_at=commit.authored_datetime,
            committed_at=commit.committed_datetime,
        )

    def fetch_files_for_commit(self, commit: Commit) -> Iterator[File]:
        # choose the parent commit to diff against
        # use *magic* empty tree sha for commits without parents
        parent = commit.parents[0] if commit.parents else EMPTY_TREE_SHA
        # diff against parent
        diff = commit.diff(parent, R=True)
        # only consider files that have been added to the repository
        # disregard modifications and deletions
        for diff_item in diff.iter_change_type(ChangeType.ADDED):
            # path for new files is stored in diff b_path
            yield File(name=Path(diff_item.b_path).name, path=diff_item.b_path, commit=commit.hexsha)

    def fetch_revisions_for_file(self, file: File) -> Iterator[FileRevision]:
        revs = []
        for path, hexsha, status in parse_log(
            self.repo.git.log(
                "--all",
                "--follow",
                "--name-status",
                "--pretty=format:%H",
                "--",
                file.path,
            )
        ):
            status = {"A": "added", "M": "modified", "D": "deleted"}.get(status, "modified")
            revs.append(
                FileRevision(
                    name=Path(path).name,
                    path=path,
                    commit=hexsha,
                    status=status,
                    insertions=0,
                    deletions=0,
                    lines=0,
                    score=0,
                    file=file,
                )
            )
        # revisions remember their predecessor (previous revision)
        for rev, prev in zip_longest(revs, revs[1:]):
            rev.previous = prev
            yield rev


def get_author(commit: Commit) -> User:
    return User(
        name=commit.author.name,
        email=commit.author.email,
        gitlab_username=None,
        gitlab_id=None,
        prov_role=ProvRole.AUTHOR,
    )


def get_committer(commit: Commit) -> User:
    return User(
        name=commit.committer.name,
        email=commit.committer.email,
        gitlab_username=None,
        gitlab_id=None,
        prov_role=ProvRole.COMMITTER,
    )


def parse_log(log: str) -> Iterator[tuple[str, str, str]]:
    """Parse 'git log' output into file paths, commit hexshas, file status (aka change type)."""
    # split the log into single entries using the delimiter
    for entry in log.split(f"{LOG_DELIMITER}\n"):
        # skip empty entries
        if not entry:
            continue
        # split the entry into lines, remove empty lines
        lines = [line.strip() for line in entry.split("\n") if line]
        # first line is always the commit hexsha
        hexsha = lines[0]
        for line in lines[1:]:
            # split the line by tab characters
            parts = line.split("\t")
            # status is the first character in the line
            status = parts[0][0]
            # path is always the last element when split by tab
            path = parts[-1]
            yield hexsha, status, path
