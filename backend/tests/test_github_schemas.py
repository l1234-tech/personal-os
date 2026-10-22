import pytest
from pydantic import ValidationError

from app.github_schemas import GitHubRepositoryLink


def test_repository_link_requires_positive_github_id() -> None:
    with pytest.raises(ValidationError):
        GitHubRepositoryLink(repository_id=0, full_name="owner/repository")


def test_repository_link_requires_owner_and_repository_name() -> None:
    with pytest.raises(ValidationError):
        GitHubRepositoryLink(repository_id=123, full_name="repo")


def test_repository_link_accepts_normal_full_name() -> None:
    link = GitHubRepositoryLink(repository_id=123, full_name="owner/repository")
    assert link.repository_id == 123
    assert link.full_name == "owner/repository"
