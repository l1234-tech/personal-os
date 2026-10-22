from pydantic import BaseModel, Field


class GitHubRepositoryLink(BaseModel):
    repository_id: int = Field(gt=0)
    full_name: str = Field(min_length=3, max_length=300)


class GitHubRepositorySummary(BaseModel):
    id: int
    name: str
    full_name: str
    html_url: str
    private: bool
    default_branch: str
    pushed_at: str | None = None
    linked_project_id: str | None = None


class GitHubActivitySummary(BaseModel):
    repository: str
    html_url: str
    default_branch: str
    latest_commit_sha: str | None = None
    latest_commit_message: str | None = None
    latest_commit_at: str | None = None
    open_pull_requests: int
    last_synced_at: str | None = None
